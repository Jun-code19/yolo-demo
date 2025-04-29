import asyncio
import json
import cv2
import numpy as np
import time
import threading
import logging
import uuid
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict
from collections import deque
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from ultralytics import YOLO
import torch
from sqlalchemy.orm import Session
from threading import Lock  # 导入锁
from src.tracker import ObjectTracker
import colorsys
from concurrent.futures import ThreadPoolExecutor
import struct
from contextlib import nullcontext

# 导入独立的数据推送模块
from src.data_pusher import data_pusher
from src.crowd_analyzer import crowd_analyzer

from src.database import (
    SessionLocal, DetectionConfig, DetectionEvent, Device, 
    DetectionModel, DetectionPerformance, SaveMode,
    EventStatus, Base, engine, get_db 
)
from api.auth import get_current_user, User
from api.logger import log_action

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DetectionTask:
    """检测任务类，管理单个摄像机的检测过程"""
    
    def __init__(self, device_id: str, config_id: str, model_path: str, 
                 confidence: float, models_type: str, target_class: List[str], save_mode: SaveMode, area_coordinates:Optional[dict]=None):
        self.device_id = device_id
        self.config_id = config_id
        self.model_path = model_path
        self.confidence = confidence
        self.models_type = models_type
        self.target_class = target_class
        self.save_mode = save_mode
        # self.region_of_interest = region_of_interest
        # self.area_type = area_type  #区域或者拌线类型字段
        self.area_coordinates = area_coordinates  #点坐标值，前端生成的归一化坐标
        
        self.class_colors = {}  # 用于存储每个类别的固定颜色
        self.class_names = None  # 用于存储类别名称

        self.stop_event = threading.Event()
        self.model = None
        self.cap = None
        self.thread = None
        self.lock = Lock()  # 初始化锁
        self.frame_buffer = deque(maxlen=1)  # 存储最近的帧
        self.last_detection_time = time.time()
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.clients = set()  # WebSocket客户端集合，用于实时预览
        self.loop = None  # 添加事件循环引用
        self.message_queue = asyncio.Queue()  # 添加消息队列
        self.broadcast_task = None  # 添加广播任务引用

        # 初始化目标追踪参数
        self.max_trajectory_length = 30
        self.max_age = 10
        self.min_hits = 3
        self.iou_threshold = 0.3

        # 初始化 ObjectTracker
        self.object_tracker = ObjectTracker(max_age=self.max_age, min_hits=self.min_hits, iou_threshold=self.iou_threshold)
    
    def load_model(self): # 加载YOLO模型
        """加载YOLO模型"""
        try:
            # 获取模型的绝对路径并记录
            abs_model_path = os.path.abspath(self.model_path)
            logger.info(f"加载模型 - 路径: {self.model_path}")
            logger.info(f"模型绝对路径: {abs_model_path}")
            
            # 设置离线模式，避免连接GitHub
            os.environ["ULTRALYTICS_OFFLINE"] = "1"
            # 禁用所有自动更新和在线检查
            os.environ["YOLO_NO_ANALYTICS"] = "1"
            os.environ["NO_VERSION_CHECK"] = "1"
            
            # 确保模型文件存在
            if not os.path.exists(abs_model_path):
                logger.error(f"模型文件不存在: {abs_model_path}")
                # 尝试在当前目录下的models文件夹中查找
                base_name = os.path.basename(abs_model_path)
                alt_path = os.path.join("models", base_name)
                alt_abs_path = os.path.abspath(alt_path)
                logger.info(f"尝试在models文件夹中查找: {alt_abs_path}")
                
                if os.path.exists(alt_abs_path):
                    abs_model_path = alt_abs_path
                    self.model_path = alt_path
                    logger.info(f"找到模型文件: {abs_model_path}")
                else:
                    logger.error(f"无法找到模型文件")
                    return False
            
            # 使用绝对路径加载模型
            # 最新YOLO版本可能需要使用以下方式加载本地模型
            # 设置环境变量确保使用本地模型
            os.environ["YOLO_VERBOSE"] = "0"  # 减少冗余日志
            
            # 根据文件扩展名确定模型类型
            model_ext = os.path.splitext(abs_model_path)[1].lower()
            logger.info(f"模型文件扩展名: {model_ext}")
            
            # 直接使用本地文件路径加载
            try:
                logger.info("开始加载模型...")
                # 强制指定task类型
                task_type = 'detect'
                if hasattr(self, 'models_type') and self.models_type == 'pose':
                    task_type = 'pose'
                    
                self.model = YOLO(abs_model_path, task=task_type)
                logger.info(f"模型加载成功: {self.model}")
                # 使用GPU并进行优化
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
                self.device = torch.device(device)
                self.model.to(self.device)
                
                self.class_names = self.model.names
                logger.info(f"模型类别: {self.class_names}")

                if device == 'cuda': 
                    # 使用半精度浮点数以提高性能
                    if hasattr(self.model, 'model'):
                        self.model.model.half()
                    logger.info("使用GPU半精度浮点数处理")

                return True
            except Exception as e:
                logger.error(f"加载模型时出错: {e}")
                return False
                
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            return False
    
    def connect_to_camera(self): # 连接到RTSP摄像机
        """连接到RTSP摄像机"""
        try:
            db = SessionLocal()
            device = db.query(Device).filter(Device.device_id == self.device_id).first()
            db.close()
            
            if not device:
                logger.error(f"未找到设备: {self.device_id}")
                return False

            if device.device_type == 'nvr':
                stream_type = 1 if device.stream_type == 'sub' else 0
                rtsp_url = f"rtsp://{device.username}:{device.password}@{device.ip_address}:{device.port}/cam/realmonitor?channel={device.channel}&subtype={stream_type}"
            else:
                stream_type = 1 if device.stream_type == 'sub' else 0
                rtsp_url = f"rtsp://{device.username}:{device.password}@{device.ip_address}:{device.port}/cam/realmonitor?channel=1&subtype={stream_type}"
            logger.info(f"连接到摄像机: {rtsp_url}")
            
            # 设置OpenCV连接参数
            self.cap = cv2.VideoCapture(rtsp_url)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 设置缓冲区大小为1，减少延迟
            
            if self.cap.isOpened():
                self.fps = self.cap.get(cv2.CAP_PROP_FPS)
                self.connected = True
                self.reconnect_attempts = 0
                logger.info(f"成功连接到摄像机: {self.device_id}")
                return True
            else:
                logger.error(f"无法连接到摄像机: {self.device_id}")
                return False
                
        except Exception as e:
            logger.error(f"连接摄像机时出错: {e}")
            return False

    def read_frame(self): # 从摄像机读取帧的线程函数
        if not self.connect_to_camera():
            logger.error(f"无法启动检测任务 {self.config_id}，摄像机连接失败")
            return
        error_count = 0
        last_reconnect_time = time.time()
        """从摄像机读取帧的线程函数"""
        while not self.stop_event.is_set():
            try:
                # 改进重连逻辑，添加退避策略
                if not self.connected or error_count > 5:
                    current_time = time.time()
                    # 添加最小间隔时间，防止频繁重试
                    if current_time - last_reconnect_time > self.reconnect_attempts * 2:
                        if self.reconnect_attempts < self.max_reconnect_attempts:
                            logger.info(f"尝试重新连接摄像机: {self.device_id} (尝试 {self.reconnect_attempts + 1}/{self.max_reconnect_attempts})")
                            last_reconnect_time = current_time
                            self.reconnect_attempts += 1
                            if self.connect_to_camera():
                                error_count = 0
                            else:
                                time.sleep(min(2 * self.reconnect_attempts, 10))  # 指数退避策略，最长等待10秒
                                continue
                        else:
                            logger.error(f"重连摄像机 {self.device_id} 失败，停止检测任务")
                            break
                    else:
                        time.sleep(0.5)  # 短暂等待
                        continue
                ret, frame = self.cap.read()
                
                if not ret:
                    error_count += 1
                    logger.warning(f"从摄像机 {self.device_id} 获取帧失败 ({error_count}/5)")
                    time.sleep(0.1)  # 短暂暂停后重试
                    continue
                # 重置错误计数
                if error_count > 0:
                    error_count = 0

                # 使用锁来确保线程安全
                with self.lock:
                    # frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self.frame_buffer.append(frame)  # 将帧添加到缓冲区
            
            except Exception as e:
                logger.error(f"读取帧时出错: {e}")
                error_count += 1
                time.sleep(0.1)  # 短暂暂停后重试

    def run_detection(self): # 执行检测的主循环
        """执行检测的主循环"""
        # 为检测线程创建和设置事件循环
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)          
        except Exception as e:
            logger.error(f"为检测线程创建事件循环失败: {e}")
        
        try:
            # 如果模型已经加载，跳过加载步骤
            if not hasattr(self, 'model') or self.model is None:
                logger.info(f"开始加载模型: {self.config_id}")
                if not self.load_model():
                    logger.error(f"无法启动检测任务 {self.config_id}，模型加载失败")
                    return
            else:
                logger.info(f"模型已预加载: {self.config_id}")
            
            # 启动读取帧的线程
            self.thread = threading.Thread(target=self.read_frame)
            self.thread.daemon = True
            self.thread.start()

            frame_count = 0
            cooldown_period = 5  # 检测事件的冷却时间（秒）
            skip_frame_count = 5  # 每隔多少帧进行一次检测
            
            while not self.stop_event.is_set():
                try:                                  
                    # 使用锁来安全地访问帧缓存
                    with self.lock:
                        if self.frame_buffer:
                            frame_rgb = self.frame_buffer[-1]  # 获取最新的帧
                        else:
                            continue  # 如果没有帧，跳过

                    # 优化：每skip_frame_count帧执行一次检测，减少计算负担
                    frame_count += 1
                    if frame_count % skip_frame_count == 0:
                         # 执行检测
                        detect_frame = frame_rgb.copy()
                        img_result = frame_rgb.copy()
                        current_time = time.time()                        
                        # 使用 try-except 捕获模型推理过程中的错误
                        try:
                            results = self.model(detect_frame, conf=self.confidence,iou=0.45,max_det=300,device=self.device)

                            # 处理检测结果
                            detections = []
                            for r in results:
                                boxes = r.boxes
                                for box in boxes:
                                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                                    confidence = box.conf.item()
                                    class_id = int(box.cls.item())
                                    class_name = r.names[class_id]
                                    if str(class_id) in self.target_class:
                                        detections.append({
                                            "bbox": [x1, y1, x2, y2],
                                            "confidence": confidence,
                                            "class_id": class_id,
                                            "class_name": class_name
                                        })                          
                            
                            if detections:
                                if self.models_type == 'pose':
                                    # 向WebSocket客户端推送检测结果
                                    img_result = self.display_pose_results(detect_frame, results[0])
                                else:
                                    if self.area_coordinates and self.area_coordinates['subtype'] == 'directional':
                                        # 开启目标追踪功能
                                        self.object_tracker.update(detections)
                                            # 传递显示框的状态到draw_tracks方法
                                        img_result = self.object_tracker.draw_tracks(
                                            detect_frame.copy(), 
                                            max_trajectory_length=self.max_trajectory_length,
                                            show_boxes=True,  # 传递显示框的状态
                                        )
                                    elif self.area_coordinates and self.area_coordinates['subtype'] == 'simple':
                                        # 开启目标追踪功能
                                        self.object_tracker.update(detections)
                                            # 传递显示框的状态到draw_tracks方法
                                        img_result = self.object_tracker.draw_tracks(
                                            detect_frame.copy(), 
                                            max_trajectory_length=self.max_trajectory_length,
                                            show_boxes=False,  # 传递显示框的状态
                                        )
                                    else:
                                        img_result = self.display_detection_results(detect_frame,results[0])
                            
                            if detections and data_pusher.push_configs:
                                speed = results[0].speed
                                self.push_detection_data(detections, img_result, speed)

                            # 判断是否需要创建检测事件
                            if self.save_mode.value != 'none':
                                if detections and (current_time - self.last_detection_time) > cooldown_period:
                                    self.last_detection_time = current_time
                                    self.save_detection_event(img_result, detections)

                            if not self.clients:
                                continue  # 没有客户端连接，跳过下面步骤
                            else:
                                self.broadcast_img_result(img_result, detections) # 向WebSocket客户端推送检测结果                                                               
                            
                        except Exception as e:
                            logger.error(f"模型推理过程中出错: {e}")
                            # 不终止整个检测循环，仅记录错误
                    
                    # 动态调整检测频率，根据是否有客户端连接来决定
                    if self.clients:
                        # 有客户端连接时，更频繁地检测
                        skip_frame_count = 1
                        sleep_time = 0.01  # 短暂休眠防止CPU过载
                    else:
                        # 无客户端连接时，减少检测频率以节省资源
                        skip_frame_count = 10
                        sleep_time = 0.05  # 更长的休眠时间
                    
                    # 防止CPU过载
                    # time.sleep(sleep_time)
                    
                except Exception as e:
                    logger.error(f"检测过程中出错: {e}")
                    time.sleep(0.1)

        except Exception as e:
            logger.error(f"检测任务异常: {e}")
        finally:
            # 关闭事件循环（在子线程内执行）
            try:
                # 关闭异步生成器
                self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            finally:
                self.loop.close()
                logger.info(f"事件循环已关闭: {self.config_id}")  
    
    def push_detection_data(self, detections, frame_rgb, speed): # 推送检测数据
        """推送检测数据"""
        push_data = {
            "timestamp": datetime.now().isoformat(),
            "device_id": self.device_id,
            "config_id": self.config_id,
            "detections": detections
        }
        # 增加标签，使推送更灵活
        data_pusher.push_data(
            data=push_data, 
            image=frame_rgb, 
            tags=["detection", f"device_{self.device_id}"],
            config_id=self.config_id  # 为了兼容性保留
        )
        
        # 记录性能统计信息
        db = SessionLocal()
        try:
            perf = DetectionPerformance(
                device_id=self.device_id,
                config_id=self.config_id,
                detection_time=speed['inference'],
                preprocessing_time=speed['preprocess'],
                postprocessing_time=speed['postprocess'],
                frame_width=frame_rgb.shape[1],
                frame_height=frame_rgb.shape[0],
                objects_detected=len(detections)
            )
            db.add(perf)
            db.commit()
        except Exception as e:
            logger.error(f"保存性能数据失败: {e}")
            db.rollback()
        finally:
            db.close()

    def normalize_points(self, points, frame_shape): #归一化坐标转换
        """归一化坐标转换"""
        h,w = frame_shape[:2]
        return [(int(p['x']*w), int(p['y']*h)) for p in points]

    def draw_roi(self, frame, roi_type, roi_points, # 绘制线段/区域 ROI（支持line/area类型）
            line_color=(0,255,0), fill_color=(0,0,0,0), 
            thickness=2, line_type=cv2.LINE_AA): 
        """
        绘制线段/区域 ROI（支持line/area类型）
        :param frame: 输入图像
        :param roi_type: ROI类型（'line'或'area'）
        :param roi_points: ROI坐标列表 [[x1,y1], [x2,y2],...]
        :param line_color: 线段/边框颜色 (BGR格式)
        :param fill_color: 填充颜色 (BGR+Alpha格式)
        :param thickness: 线宽
        :param line_type: 线型（默认抗锯齿）
        """
        if roi_type not in ['line', 'area']:
            raise ValueError("Invalid ROI type. Must be 'line' or 'area'")
        
        line = self.normalize_points(roi_points, frame.shape)

        # 转换为整数坐标
        roi_array = np.array(line, np.int32)
        
        if roi_type == 'line':
            # 线段绘制（至少需要2个点）
            if len(roi_array) < 2:
                return
            # 绘制线段轮廓
            cv2.polylines(frame, [roi_array], False, line_color, thickness, line_type)
            # 绘制中间点标记（可选）
            for pt in roi_array:
                cv2.circle(frame, tuple(pt), 3, line_color, -1)
                
        elif roi_type == 'area':
            # 区域绘制
            if len(roi_array) < 3:
                # 最小包围矩形
                x_coords = [p[0] for p in roi_array]
                y_coords = [p[1] for p in roi_array]
                x1, x2 = int(min(x_coords)), int(max(x_coords))
                y1, y2 = int(min(y_coords)), int(max(y_coords))
                cv2.rectangle(frame, (x1, y1), (x2, y2), line_color, thickness)
            else:
                # 多边形绘制
                cv2.polylines(frame, [roi_array], True, line_color, thickness, line_type)
                # 区域填充（支持透明度）
                if fill_color[3]!= 0:
                    cv2.fillPoly(frame, [roi_array], fill_color[:3])  # 填充颜色（BGR）
                    # 绘制半透明覆盖层
                    overlay = frame.copy()
                    cv2.fillPoly(overlay, [roi_array], fill_color)
                    frame = cv2.addWeighted(frame, 0.7, overlay, 0.3, 0)

    def generate_colors(self, num_classes): # 生成颜色
        hsv_tuples = [(x / num_classes, 1., 1.) for x in range(num_classes)]
        colors = list(map(lambda x: colorsys.hsv_to_rgb(*x), hsv_tuples))
        colors = list(map(lambda x: (int(x[0] * 255), int(x[1] * 255), int(x[2] * 255)), colors))
        return colors

    def get_class_color(self, class_id): # 获取类别颜色
        if class_id not in self.class_colors:
            if not self.class_colors:
                colors = self.generate_colors(len(self.class_names))
                self.class_colors = {i: color for i, color in enumerate(colors)}
            else:
                self.class_colors[class_id] = tuple(np.random.randint(0, 255, 3).tolist())
        return self.class_colors[class_id]

    def display_detection_results(self, img, results): # 显示检测结果
        if not hasattr(results, 'boxes') or results.boxes is None:
            return img

        boxes = results.boxes
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            conf = box.conf.cpu().numpy()[0]
            cls = int(box.cls.cpu().numpy()[0])
            
            if str(cls) not in self.target_class:
                continue

            color = self.get_class_color(cls)
            # 只在复选框选中时绘制边界框
            # if self.show_boxes_checkbox.isChecked():
            cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
            class_name = self.class_names[cls] if self.class_names else f"Class {cls}"
            label = f"{class_name}: {conf:.2f}"
            cv2.putText(img, label, (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        return img

    def display_pose_results(self, img, results): # 显示姿态结果
        if not hasattr(results, 'keypoints') or results.keypoints is None:
            print("No keypoints found in pose results")
            return img

        keypoints = results.keypoints
        boxes = results.boxes

        # 定义不同身体部位的颜色
        colors = {
            'head': (255, 0, 0),    # 蓝色
            'body': (0, 255, 0),    # 绿色
            'arms': (255, 165, 0),  # 橙色
            'legs': (255, 0, 255)   # 紫色
        }

        for person_keypoints, box in zip(keypoints, boxes):
            kpts = person_keypoints.data[0]
            for kpt in kpts:
                x, y, conf = kpt
                if conf > 0.5:
                    cv2.circle(img, (int(x), int(y)), 5, (0, 255, 0), -1)

            connections = [
                ((0, 1), 'head'), ((0, 2), 'head'), ((1, 3), 'head'), ((2, 4), 'head'),
                ((0, 5), 'body'), ((0, 6), 'body'),
                ((5, 6), 'body'), ((5, 11), 'body'), ((6, 12), 'body'), ((11, 12), 'body'),
                ((5, 7), 'arms'), ((7, 9), 'arms'), ((6, 8), 'arms'), ((8, 10), 'arms'),
                ((11, 13), 'legs'), ((13, 15), 'legs'), ((12, 14), 'legs'), ((14, 16), 'legs')
            ]
            for (connection, body_part) in connections:
                pt1, pt2 = kpts[connection[0]], kpts[connection[1]]
                if pt1[2] > 0.5 and pt2[2] > 0.5:
                    cv2.line(img, (int(pt1[0]), int(pt1[1])), (int(pt2[0]), int(pt2[1])), colors[body_part], 2)

            x1, y1, x2, y2 = box.xyxy[0]
            conf = box.conf[0]
            cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            label = f"Person: {conf:.2f}"
            cv2.putText(img, label, (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        return img

    def start(self): # 启动检测任务线程
        """启动检测任务线程"""
        if self.thread and self.thread.is_alive():
            logger.info(f"检测任务已在运行: {self.config_id}")
            return
        
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run_detection)
        self.thread.daemon = True
        self.thread.start()
    
    async def stop(self): # 停止检测任务
        """停止检测任务"""
        logger.info(f"正在停止检测任务: {self.config_id}")
        self.stop_event.set()
        
        # 停止广播任务
        if self.broadcast_task:
            self.broadcast_task.cancel()
            try:
                await self.broadcast_task
            except asyncio.CancelledError:
                logger.info(f"广播任务已取消: {self.config_id}")
        # if self.broadcast_task and not self.broadcast_task.done():
        #     self.broadcast_task.cancel()
        #     self.broadcast_task = None
        
        # 发送停止信号到消息队列
        # 发送停止信号到消息队列
        try:
            if self.loop and not self.message_queue.empty():
                await self.message_queue.put(None)
        except Exception as e:
            logger.error(f"发送停止信号到消息队列失败: {e}")
        # if self.loop and self.loop.is_running():
        #     try:
        #         asyncio.run_coroutine_threadsafe(
        #             self.message_queue.put(None),
        #             self.loop
        #         )
        #     except Exception as e:
        #         logger.error(f"发送停止信号到消息队列失败: {e}")
        
        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                logger.warning(f"检测线程未能及时停止: {self.config_id}")

        # 释放摄像头资源
        if self.cap:
            self.cap.release()
            logger.info(f"摄像头资源已释放: {self.config_id}")
            
        # 清理事件循环
        # if self.loop and hasattr(self.loop, 'close'):
        #     try:
        #         if self.loop.is_running():
        #             # 停止事件循环
        #             self.loop.call_soon_threadsafe(self.loop.stop)
        #             logger.info(f"事件循环已停止: {self.config_id}")
        #     except Exception as e:
        #         logger.error(f"停止事件循环失败: {e}")
    
    def save_detection_event(self, frame, detections): # 保存检测事件到数据库并存储图像/视频
        """保存检测事件到数据库并存储图像/视频"""
        try:
            # 保存事件到数据库
            db = SessionLocal()
            event_id = str(uuid.uuid4())
            current_time = datetime.now()
            
            # 获取检测配置信息
            config = db.query(DetectionConfig).filter(DetectionConfig.config_id == self.config_id).first()
            
            if not config:
                logger.error(f"未找到检测配置: {self.config_id}")
                db.close()
                return
            
            # 创建检测事件记录
            event = DetectionEvent(
                event_id=event_id,
                config_id=self.config_id,
                device_id=self.device_id,
                timestamp=current_time,
                event_type=self.models_type,
                confidence=max([d["confidence"] for d in detections]) if detections else 0.0,
                bounding_box=detections,
                status=EventStatus.new,
                created_at=current_time
            )
            
            # 根据保存模式保存图像/视频
            save_dir = Path(f"storage/events/{current_time.strftime('%Y-%m-%d')}/{self.device_id}")
            save_dir.mkdir(parents=True, exist_ok=True)
            
            if self.save_mode in [SaveMode.screenshot, SaveMode.both]:
                # 绘制检测框和标签
                # annotated_frame = self.draw_detections(frame, detections)    
                # 保存带检测框的截图（原图）
                thumbnail_path = save_dir / f"{event_id}.jpg"
                cv2.imwrite(str(thumbnail_path), frame)
                event.thumbnail_path = str(thumbnail_path)

                # 保存带检测框的截图 (缩略图)
                # success, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 10])
                # height, width = frame.shape[:2]
                # if success:
                #     event.thumbnail_data = buffer.tobytes()
                #     event.is_compressed = True  # 设置压缩标记
                #     event.meta_data = {
                #         "resolution": f"{width}x{height}",
                #         "size": len(buffer.tobytes()),  # 存储图像大小
                #         # 其他元数据...
                #     }
                # else:
                #     logger.error("JPEG编码失败")
                            
            # if self.save_mode in [SaveMode.video, SaveMode.both]:
                # # 从帧缓冲区创建短视频
                # snippet_path = save_dir / f"{event_id}.mp4"
                # height, width = frame.shape[:2]
                # fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                # out = cv2.VideoWriter(str(snippet_path), fourcc, 5, (width, height))
                
                # # 处理视频中的每一帧并添加检测框
                # for f in self.frame_buffer:
                #     # 在每一帧上绘制检测框
                #     annotated_f = self.draw_detections(f, detections)
                #     out.write(annotated_f)
                # out.release()
                # event.snippet_path = str(snippet_path)
            
            # 提交事件
            db.add(event)
            db.commit()
            logger.info(f"已保存检测事件: {event_id}")
            
        except Exception as e:
            logger.error(f"保存检测事件失败: {e}")
            if 'db' in locals() and db:
                db.rollback()
        finally:
            if 'db' in locals() and db:
                db.close()
    
    def draw_detections(self, frame, detections): # 在图像上绘制检测框和标签
        """在图像上绘制检测框和标签"""
        annotated_frame = frame.copy()
        
        # 绘制每个检测框
        for detection in detections:
            # 获取边界框坐标
            bbox = detection["bbox"]
            x1, y1, x2, y2 = map(int, bbox)
            
            # 获取类别和置信度
            class_name = detection["class_name"]
            confidence = detection["confidence"]
            
            # 为不同类别选择不同颜色
            # 使用类别ID来确定颜色，确保同一类别总是相同颜色
            color_id = detection["class_id"] % 10
            colors = [
                (255, 0, 0),     # 红
                (0, 255, 0),     # 绿
                (0, 0, 255),     # 蓝
                (255, 255, 0),   # 黄
                (0, 255, 255),   # 青
                (255, 0, 255),   # 紫
                (255, 128, 0),   # 橙
                (128, 0, 255),   # 紫蓝
                (0, 128, 255),   # 浅蓝
                (255, 0, 128)    # 粉红
            ]
            color = colors[color_id]
            
            # 绘制边界框
            # cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
            cv2.rectangle(annotated_frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
            
            # 准备标签文本
            label = f"{class_name}: {confidence:.2f}"
            
            # 绘制背景和文本
            # 获取文本大小
            # (text_width, text_height), baseline = cv2.getTextSize(
            #     label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            
            # # 绘制标签背景
            # cv2.rectangle(
            #     annotated_frame, 
            #     (x1, y1 - text_height - 5), 
            #     (x1 + text_width, y1), 
            #     color, 
            #     -1  # 填充矩形
            # )
            
            # 绘制文本
            cv2.putText(
                annotated_frame, 
                label, 
                (x1, y1 - 5), 
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.5, 
                color, 
                1
            )
        
        return annotated_frame
    
    def broadcast_img_result(self, pose_frame, detections): # 向所有WebSocket客户端广播检测结果
        """向所有WebSocket客户端广播检测结果"""
        if not self.clients:
            return  # 没有客户端连接，跳过
        
        try:     
            if(self.area_coordinates): 
                roi_type = self.area_coordinates['type']
                roi_points = self.area_coordinates['points']
                if roi_type and roi_points:
                    self.draw_roi(pose_frame, roi_type, roi_points)               
            
            # 将帧转换为JPEG，增加质量参数
            _, buffer = cv2.imencode('.jpg', pose_frame, [cv2.IMWRITE_JPEG_QUALITY, 90])  # 提高JPEG质量
            jpg_bytes = buffer.tobytes()
            base64_image = base64.b64encode(jpg_bytes).decode('utf-8')
            
            # 创建消息
            message = {
                "device_id": self.device_id,
                "config_id": self.config_id,
                "timestamp": time.time(),
                "image": base64_image,
                "detections": detections
            }
            
            # 将消息放入队列（线程安全）
            if self.loop and self.loop.is_running():
                self.loop.call_soon_threadsafe(
                    lambda: self.message_queue.put_nowait(message)
                )
       
        except Exception as e:
            logger.error(f"广播检测结果失败: {e}")

    def broadcast_detection_result(self, frame, detections): # 向所有WebSocket客户端广播检测结果
        """向所有WebSocket客户端广播检测结果"""
        if not self.clients:
            return  # 没有客户端连接，跳过
        
        try:
            # 图像压缩处理
            h, w = frame.shape[:2]
            max_width = 1280  # 提高最大宽度以保持更高的分辨率
            scale = 1
            
            if w > max_width:
                scale = max_width / w
                new_w = int(w * scale)
                new_h = int(h * scale)
                frame_resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
            else:
                frame_resized = frame
            
            # 调整检测框坐标
            adjusted_detections = []
            for detection in detections:
                adjusted_detection = detection.copy()
                adjusted_detection["bbox"] = [
                    int(detection["bbox"][0] * scale),
                    int(detection["bbox"][1] * scale),
                    int(detection["bbox"][2] * scale),
                    int(detection["bbox"][3] * scale)
                ]
                adjusted_detections.append(adjusted_detection)

            # 绘制检测框和标签
            annotated_frame = self.draw_detections(frame_resized, adjusted_detections)
            
            # 将帧转换为JPEG，增加质量参数
            _, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 90])  # 提高JPEG质量
            jpg_bytes = buffer.tobytes()
            base64_image = base64.b64encode(jpg_bytes).decode('utf-8')
            
            # 创建消息
            message = {
                "device_id": self.device_id,
                "config_id": self.config_id,
                "timestamp": time.time(),
                "image": base64_image,
                "detections": adjusted_detections
            }
            
            # 将消息放入队列（线程安全）
            if self.loop and self.loop.is_running():
                self.loop.call_soon_threadsafe(
                    lambda: self.message_queue.put_nowait(message)
                )
        
        except Exception as e:
            logger.error(f"广播检测结果失败: {e}")
            
    async def broadcast_worker(self): # 处理消息广播的工作协程
        """处理消息广播的工作协程"""
        logger.info(f"广播工作协程已启动: {self.config_id}")
        try:
            while not self.stop_event.is_set():
                try:
                    # 设置超时，避免永久阻塞
                    message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                    
                    if message is None:  # 停止信号
                        break
                    
                    # 调试日志
                    logger.debug(f"准备向 {len(self.clients)} 个客户端广播消息")
                    
                    # 获取当前活跃的客户端列表
                    clients = list(self.clients)
                    for client in clients:
                        try:
                            await client.send_json(message)
                            # 可选：添加成功发送日志
                            # logger.debug(f"成功向客户端 {id(client)} 发送消息")
                        except Exception as e:
                            logger.error(f"向客户端 {id(client)} 发送消息失败: {e}")
                            # 移除断开连接的客户端
                            if client in self.clients:
                                self.clients.remove(client)
                                logger.info(f"客户端已断开连接，检测任务 {self.config_id}, 当前客户端数: {len(self.clients)}")
                    
                    self.message_queue.task_done()
                except asyncio.TimeoutError:
                    # 超时但不影响循环继续
                    continue
                except Exception as e:
                    logger.error(f"广播工作协程错误: {e}")
                    # await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info(f"广播任务被取消: {self.config_id}")
        finally:
            logger.info(f"广播工作协程已停止: {self.config_id}")
    
    def add_client(self, websocket): # 添加WebSocket客户端到广播列表
        """添加WebSocket客户端到广播列表"""
        self.clients.add(websocket)
        logger.info(f"客户端已连接到检测任务 {self.config_id}, 当前客户端数: {len(self.clients)}")
        
        # 如果没有广播任务，立即启动一个
        if not self.broadcast_task or self.broadcast_task.done():
            try:
                # 确保在正确的事件循环中创建任务
                if self.loop and self.loop.is_running():
                    self.broadcast_task = asyncio.run_coroutine_threadsafe(
                        self.broadcast_worker(),
                        self.loop
                    )
                else:
                    self.loop = asyncio.get_event_loop()
                    self.broadcast_task = asyncio.create_task(self.broadcast_worker())
                    logger.info(f"为检测任务 {self.config_id} 创建了新的广播任务")
            except Exception as e:
                logger.error(f"创建广播任务失败: {e}")
    
    def remove_client(self, websocket): # 从广播列表中移除WebSocket客户端
        """从广播列表中移除WebSocket客户端"""
        if websocket in self.clients:
            self.clients.remove(websocket)
            logger.info(f"客户端已断开连接，检测任务 {self.config_id}, 当前客户端数: {len(self.clients)}")
            
            # 如果没有客户端了，停止广播任务
            if not self.clients and self.broadcast_task:
                self.broadcast_task.cancel()
                self.broadcast_task = None

class DetectionServer:
    """检测服务器类，管理所有检测任务"""
    
    def __init__(self): # 初始化检测服务器
        self.tasks = {}  # 存储所有检测任务，格式: {config_id: DetectionTask}
        self.models_cache = {}  # 缓存已加载的模型，格式: {model_path: model}
    
    async def start_detection(self, config_id: str, db: Session): # 启动特定配置的检测任务
        """启动特定配置的检测任务"""
        # 检查任务是否已在运行
        if config_id in self.tasks and self.tasks[config_id].thread and self.tasks[config_id].thread.is_alive():
            logger.info(f"检测任务已在运行: {config_id}")
            return {"status": "success", "message": "检测任务已在运行"}
        
        try:
            # 获取检测配置
            config = db.query(DetectionConfig).filter(DetectionConfig.config_id == config_id).first()
            if not config:
                logger.error(f"未找到检测配置: {config_id}")
                return {"status": "error", "message": "未找到检测配置"}
            
            # 获取模型信息
            model = db.query(DetectionModel).filter(DetectionModel.models_id == config.models_id).first()
            if not model:
                logger.error(f"未找到模型: {config.models_id}")
                return {"status": "error", "message": "未找到模型"}
            
            # 检查模型文件是否存在
            model_path = model.file_path
            abs_model_path = os.path.abspath(model_path)
            logger.info(f"模型路径: {model_path}, 绝对路径: {abs_model_path}")
            
            if not os.path.exists(abs_model_path):
                # 尝试在models目录中查找
                base_name = os.path.basename(model_path)
                alternative_path = os.path.join("models", base_name)
                alt_abs_path = os.path.abspath(alternative_path)
                logger.info(f"原始模型文件不存在，尝试替代路径: {alt_abs_path}")
                
                if os.path.exists(alt_abs_path):
                    model_path = alternative_path
                    logger.info(f"找到模型文件，使用替代路径: {model_path}")
                else:
                    logger.error(f"模型文件不存在: {abs_model_path} 或 {alt_abs_path}")
                    return {"status": "error", "message": f"模型文件不存在: {os.path.basename(model_path)}"}
            
            # 预加载模型到缓存中
            if model_path not in self.models_cache:
                try:
                    # 设置离线模式
                    os.environ["ULTRALYTICS_OFFLINE"] = "1"
                    os.environ["YOLO_NO_ANALYTICS"] = "1"
                    os.environ["NO_VERSION_CHECK"] = "1"
                    
                    # 确定模型类型
                    task_type = 'detect'
                    if model.models_type == 'pose':
                        task_type = 'pose'
                    
                    logger.info(f"预加载模型到缓存: {model_path}, 任务类型: {task_type}")
                    # 尝试加载模型到缓存
                    cached_model = YOLO(model_path, task=task_type)
                    self.models_cache[model_path] = cached_model
                    logger.info(f"模型已加载到缓存: {model_path}")
                except Exception as e:
                    logger.error(f"预加载模型到缓存失败: {e}")
                    # 失败但不中断流程，让任务自己尝试加载
            else:
                logger.info(f"使用缓存的模型: {model_path}")
            
            # 创建检测任务
            task = DetectionTask(
                device_id=config.device_id,
                config_id=config_id,
                model_path=model_path,  # 使用可能已更新的模型路径
                confidence=config.sensitivity,  
                models_type=model.models_type,
                target_class=config.target_classes,
                save_mode=config.save_mode,
                area_coordinates=config.area_coordinates
            )
            
            # 如果模型已缓存，直接设置
            if model_path in self.models_cache:
                task.model = self.models_cache[model_path]
                # 设置其他必要属性
                task.class_names = task.model.names
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
                task.device = torch.device(device)
                if device == 'cuda' and hasattr(task.model, 'model'):
                    task.model.model.half()
                logger.info(f"使用缓存模型设置任务: {config_id}")
            
            # 设置事件循环
            task.loop = asyncio.get_event_loop()
            
            # 启动任务
            task.start()
            
            # 保存任务
            self.tasks[config_id] = task
            
            # 更新数据库中的任务状态
            config.enabled = True
            config.updated_at = datetime.now()
            db.commit()
            
            logger.info(f"检测任务已启动: {config_id}")
            return {"status": "success", "message": "检测任务已启动"}
            
        except Exception as e:
            logger.error(f"启动检测任务失败: {e}")
            db.rollback()
            return {"status": "error", "message": f"启动检测任务失败: {str(e)}"}
    
    async def stop_detection(self, config_id: str, db: Session): # 停止特定配置的检测任务
        """停止特定配置的检测任务"""
        if config_id not in self.tasks:
            logger.warning(f"检测任务不存在: {config_id}")
            return {"status": "error", "message": "检测任务不存在"}
        
        try:
            # 停止任务
            await self.tasks[config_id].stop()
            
            # 更新数据库中的任务状态
            config = db.query(DetectionConfig).filter(DetectionConfig.config_id == config_id).first()
            if config:
                config.enabled = False
                config.updated_at = datetime.now()
                db.commit()
            
            # 移除任务
            del self.tasks[config_id]
            
            logger.info(f"检测任务已停止: {config_id}")
            return {"status": "success", "message": "检测任务已停止"}
            
        except Exception as e:
            logger.error(f"停止检测任务失败: {e}")
            db.rollback()
            return {"status": "error", "message": f"停止检测任务失败: {str(e)}"}
    
    async def start_all_enabled(self, db: Session): # 启动所有已启用的检测任务
        """启动所有已启用的检测任务"""
        logger.info("正在启动所有已启用的检测任务...")
        enabled_configs = db.query(DetectionConfig).filter(DetectionConfig.enabled.is_(True)).all()
        
        for config in enabled_configs:
            await self.start_detection(config.config_id, db)
        
        logger.info(f"已启动 {len(enabled_configs)} 个检测任务")
    
    async def handle_preview(self, websocket: WebSocket, config_id: str): # 处理检测预览WebSocket连接
        """处理检测预览WebSocket连接"""
        await websocket.accept()
        
        if config_id not in self.tasks:
            await websocket.send_json({
                "status": "error", 
                "message": "请求的检测任务不存在或未启动"
            })
            await websocket.close()
            return
        
        try:
            # 获取当前的事件循环并设置到任务中
            self.tasks[config_id].loop = asyncio.get_event_loop()
            
            # 添加WebSocket客户端到检测任务
            self.tasks[config_id].add_client(websocket)
            
            # 发送初始连接成功消息
            await websocket.send_json({
                "status": "success",
                "message": "已连接到检测服务",
                "config_id": config_id
            })
            
            # 保持连接，直到客户端断开
            while True:
                try:
                    await websocket.receive_text()
                except WebSocketDisconnect:
                    logger.info(f"WebSocket客户端断开连接: {id(websocket)}")
                    break
                except Exception as e:
                    logger.error(f"WebSocket接收消息错误: {e}")
                    break
        except Exception as e:
            logger.error(f"WebSocket连接处理异常: {e}")
        finally:
            # 确保客户端被移除
            if config_id in self.tasks:
                self.tasks[config_id].remove_client(websocket)

# 创建检测服务器实例
detection_server = DetectionServer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用程序生命周期管理"""
    logger.info("检测服务器启动中...")
    
    # 创建数据库表（如果不存在）
    Base.metadata.create_all(bind=engine)
    
    # 1.启动数据推送服务
    try:
        data_pusher.startup_push_service()
    except Exception as e:
        logger.error(f"启动数据推送服务失败: {e}")

    # 2. 启动检测服务
    try:
        db = SessionLocal()
        await detection_server.start_all_enabled(db)
        db.close()
    except Exception as e:
        logger.error(f"启动检测服务失败: {e}")

    # 3. 启动人群分析服务
    try:       
        # 加载所有活跃的人群分析任务
        crowd_analyzer.load_all_active_jobs()
        # 启动人群分析服务
        crowd_analyzer.start()
    except Exception as e:
        logger.error(f"启动人群分析服务失败: {e}")
    
    yield
    
    # 关闭服务（顺序与启动相反）
    logger.info("检测服务器关闭中...")
    
    # 1. 停止人群分析服务
    try:
        crowd_analyzer.stop()
    except Exception as e:
        logger.error(f"停止人群分析服务失败: {e}")
    
    # 2. 停止检测任务
    for config_id, task in list(detection_server.tasks.items()):
        try:
            task.stop()
        except Exception as e:
            logger.error(f"停止检测任务 {config_id} 失败: {e}")
    
    # 3. 停止数据推送服务
    try:
        data_pusher.shutdown_push_service()
    except Exception as e:
        logger.error(f"停止数据推送服务失败: {e}")
    
    logger.info("所有服务已停止")

# 创建FastAPI应用
app = FastAPI(
    title="检测服务器",
    description="用于管理对象检测任务的API",
    version="1.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API路由
@app.post("/api/v2/detection/{config_id}/start")
async def start_detection_api(config_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)): # 启动检测任务API
    """启动检测任务API"""
    log_action(db, current_user.user_id, 'start_detection', config_id, f"启动检测任务: {config_id}")
    return await detection_server.start_detection(config_id, db)


@app.post("/api/v2/detection/{config_id}/stop")
async def stop_detection_api(config_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)): # 停止检测任务API
    """停止检测任务API"""
    log_action(db, current_user.user_id, 'stop_detection', config_id, f"停止检测任务: {config_id}")
    return await detection_server.stop_detection(config_id, db)


@app.get("/api/v2/detection/status")
async def get_detection_status(): # 获取所有检测任务的状态
    """获取所有检测任务的状态"""
    tasks_status = {}
    for config_id, task in detection_server.tasks.items():
        tasks_status[config_id] = {
            "device_id": task.device_id,
            "is_running": task.thread is not None and task.thread.is_alive(),
            "connected": task.connected,
            "clients_count": len(task.clients)
        }
    
    return {"status": "success", "tasks": tasks_status}


@app.websocket("/ws/detection/preview/{config_id}")
async def detection_preview_websocket(websocket: WebSocket, config_id: str): # 检测预览WebSocket端点
    """检测预览WebSocket端点"""
    await websocket.accept()
    
    # 检查检测任务是否存在
    if config_id not in detection_server.tasks:
        # 先尝试启动任务
        logger.info(f"WebSocket请求的检测任务不存在，尝试启动: {config_id}")
        db = SessionLocal()
        result = await detection_server.start_detection(config_id, db)
        db.close()
        
        if result["status"] == "error" or config_id not in detection_server.tasks:
            # 启动失败，发送错误消息并关闭连接
            await websocket.send_json({
                "status": "error", 
                "message": result.get("message") or "请求的检测任务不存在或无法启动"
            })
            await websocket.close()
            return
    
    # 任务存在或已成功启动
    task = detection_server.tasks[config_id]
    
    try:
        # 确保任务的事件循环已设置
        if not task.loop:
            loop = asyncio.get_event_loop()
            task.loop = loop
            logger.info(f"为检测任务 {config_id} 设置主事件循环")
        
        # 发送初始连接成功消息
        await websocket.send_json({
            "status": "success",
            "message": "已连接到检测服务",
            "config_id": config_id,
            "device_id": task.device_id
        })
        
        # 添加WebSocket客户端到检测任务
        task.add_client(websocket)
        logger.info(f"WebSocket客户端已添加到检测任务: {config_id}")
        
        # 保持连接，直到客户端断开
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                logger.info(f"WebSocket客户端断开连接: {id(websocket)}")
                break
            except Exception as e:
                logger.error(f"WebSocket接收消息错误: {e}")
                break
    except Exception as e:
        logger.error(f"WebSocket连接处理异常: {e}")
    finally:
        # 确保客户端被移除
        if config_id in detection_server.tasks:
            detection_server.tasks[config_id].remove_client(websocket)
            logger.info(f"WebSocket客户端已从检测任务移除: {config_id}")

# 注册人群分析API路由
from api.crowd_analysis import router as crowd_analysis_router
app.include_router(crowd_analysis_router, prefix="/api/v2")

# 添加数据推送相关的API接口
from api.data_push import router as data_push_router
app.include_router(data_push_router, prefix="/api/v2")

# 全局变量
models_cache = {}
frame_queues = {}
max_queue_size = 1  # 减小队列大小以降低延迟
executor = ThreadPoolExecutor(max_workers=2)  # 减少线程数以避免资源竞争
previous_boxes = {}
box_smooth_factor = 0.2  # 减小平滑因子以降低延迟
max_latency = 1000  # 增加最大延迟阈值(ms)，避免跳过太多帧
max_size = 320  # 减小处理尺寸以提高性能

# 添加 WebSocket 连接管理
active_connections: Dict[str, WebSocket] = {}
rtsp_sessions: Dict[str, dict] = {}

class RTSPManager:
    """管理RTSP流的类"""
    
    def __init__(self):
        self.active_streams = {}
        self.stop_events = {}
        self.frame_buffers = {}
        self.frame_ready_events = {}
        self.thread_executors = ThreadPoolExecutor(max_workers=4)  # 专用于RTSP的线程池
        self.stream_status = {}  # 用于线程和异步任务间通信
    
    async def start_stream(self, connection_id: str, stream_url: str) -> bool:
        """启动RTSP流处理"""
        if connection_id in self.active_streams:
            return False
        
        # 设置停止事件和帧缓冲
        stop_event = threading.Event()
        self.stop_events[connection_id] = stop_event
        self.frame_buffers[connection_id] = deque(maxlen=5)  # 存储最多5帧
        self.stream_status[connection_id] = {"status": "connecting", "info": None, "error": None}
        
        # 在单独的线程中运行RTSP捕获
        self.thread_executors.submit(
            self._capture_rtsp_frames,
            connection_id,
            stream_url,
            stop_event
        )
        
        # 创建异步任务处理流
        task = asyncio.create_task(
            self._process_frames_async(connection_id)
        )
        self.active_streams[connection_id] = task
        
        return True
    
    async def stop_stream(self, connection_id: str) -> bool:
        """停止RTSP流处理"""
        if connection_id not in self.active_streams:
            return False
        
        # 设置停止事件
        if connection_id in self.stop_events:
            self.stop_events[connection_id].set()
        
        # 等待任务结束
        task = self.active_streams[connection_id]
        if not task.done():
            await asyncio.wait([task], timeout=5)
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # 清理资源
        self.active_streams.pop(connection_id, None)
        self.stop_events.pop(connection_id, None)
        if connection_id in self.frame_buffers:
            self.frame_buffers.pop(connection_id)
        if connection_id in self.stream_status:
            self.stream_status.pop(connection_id)
        
        return True
    
    def _capture_rtsp_frames(self, connection_id: str, stream_url: str, stop_event):
        """在单独的线程中从RTSP流捕获帧"""
        logger.info(f"开始RTSP捕获线程: {stream_url}")
        frame_count = 0
        frame_buffer = self.frame_buffers.get(connection_id)
        skip_frame_count = 0
        
        try:
            # 尝试从RTSP连接视频源
            try:
                cap = cv2.VideoCapture(stream_url)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 设置缓冲区大小为1，减少延迟

                if cap.isOpened():
                    logger.info(f"成功连接到摄像机: {stream_url}")
                else:
                    logger.error(f"无法连接到摄像机: {stream_url}")
                    return False
                
                fps = cap.get(cv2.CAP_PROP_FPS)
                width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                        
                if connection_id in self.stream_status:
                    self.stream_status[connection_id] = {
                        "status": "connected",
                        "info": {
                            "width": width,
                            "height": height,
                            "fps": float(fps) if fps else 30.0
                        },
                        "error": None
                    }
                
                logger.info(f"视频流信息: 分辨率={width}x{height}, FPS={fps}")
                
                target_fps = min(30, fps if fps else 30)
                frame_interval = 1.0 / target_fps
                
                last_frame_time = time.time()
                
                # 循环处理视频帧
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    if stop_event.is_set():
                        logger.info(f"收到停止事件，结束RTSP捕获线程: {connection_id}")
                        break
                    
                    current_time = time.time()
                    elapsed = current_time - last_frame_time
                    
                    # 控制帧率，避免缓冲区溢出
                    if elapsed < frame_interval * 0.5:  # 如果时间间隔过短，跳过该帧
                        skip_frame_count += 1
                        if skip_frame_count % 30 == 0:
                            logger.debug(f"跳过帧以控制帧率，已跳过: {skip_frame_count}")
                        continue
                    
                    # 将PyAV帧转换为OpenCV格式
                    # img = frame.to_ndarray(format='bgr24')
                    img = frame
                    # 添加帧信息
                    frame_data = {
                        "frame": img,
                        "frame_id": frame_count,
                        "timestamp": current_time,
                        "width": img.shape[1],
                        "height": img.shape[0]
                    }
                    
                    # 将帧放入共享缓冲区
                    if frame_buffer is not None:
                        if len(frame_buffer) >= frame_buffer.maxlen:
                            frame_buffer.popleft()  # 移除最老的帧，避免延迟累积
                        frame_buffer.append(frame_data)
                    
                    frame_count += 1
                    last_frame_time = current_time
                    
                    # 避免CPU占用过高
                    time.sleep(0.001)
                
                logger.info(f"RTSP捕获完成，共捕获 {frame_count} 帧，跳过 {skip_frame_count} 帧")
                
            except Exception as e:
                logger.error(f"无法打开RTSP流: {e}")
                # 设置错误状态
                if connection_id in self.stream_status:
                    self.stream_status[connection_id] = {
                        "status": "error", 
                        "error": f"无法连接到RTSP流: {str(e)}"
                    }
                return
                
        except Exception as e:
            logger.error(f"RTSP捕获线程错误: {e}")
            # 设置错误状态
            if connection_id in self.stream_status:
                self.stream_status[connection_id] = {
                    "status": "error", 
                    "error": f"视频流处理错误: {str(e)}"
                }
        finally:
            # 关闭容器
            try:
                if 'cap' in locals():
                    cap.release()
            except Exception as e:
                logger.error(f"关闭RTSP容器时发生错误: {e}")
            
            logger.info(f"RTSP捕获线程已结束: {connection_id}")
    
    async def _process_frames_async(self, connection_id: str):
        """异步处理并发送捕获的帧"""
        logger.info(f"开始帧处理任务: {connection_id}")
        frame_buffer = self.frame_buffers.get(connection_id)
        stop_event = self.stop_events.get(connection_id)
        last_send_time = time.time()
        send_interval = 1.0 / 30.0  # 控制发送帧率，最高30fps
        processed_frames = 0
        
        # 通知参数
        stream_notified = False
        retry_count = 0
        max_retry = 50  # 最多等待5秒
        
        try:
            # 等待RTSP连接成功或失败
            while retry_count < max_retry:
                if connection_id in self.stream_status:
                    status = self.stream_status[connection_id]
                    
                    # 检查是否有错误
                    if status.get("status") == "error":
                        websocket = active_connections.get(connection_id)
                        if websocket:
                            await websocket.send_json({
                                "type": "error",
                                "message": status.get("error", "未知错误")
                            })
                        return
                    
                    # 检查是否已连接
                    if status.get("status") == "connected" and status.get("info"):
                        websocket = active_connections.get(connection_id)
                        if websocket:
                            # 发送流信息
                            await websocket.send_json({
                                "type": "stream_info",
                                "width": status["info"].get("width"),
                                "height": status["info"].get("height"),
                                "fps": status["info"].get("fps")
                            })
                            
                            # 发送预览开始通知
                            await websocket.send_json({
                                "type": "preview_start",
                                "width": status["info"].get("width"),
                                "height": status["info"].get("height")
                            })
                            stream_notified = True
                        break
                
                retry_count += 1
                await asyncio.sleep(0.1)
            
            # 主循环处理帧
            while not stop_event.is_set():
                # 检查是否有新帧
                if frame_buffer and len(frame_buffer) > 0:
                    # 获取最新的帧
                    frame_data = frame_buffer[-1]  # 总是处理最新的帧
                    img = frame_data["frame"]
                    frame_id = frame_data["frame_id"]
                    
                    current_time = time.time()
                    elapsed = current_time - last_send_time
                    
                    # 控制发送频率
                    if elapsed >= send_interval:
                        # 处理图像质量
                        try:
                            # 原始分辨率
                            orig_h, orig_w = img.shape[:2]
                            
                            # 调整尺寸（可选，保持高质量）
                            max_dim = 1920  # 增加到1920以提高质量
                            resized = False
                            processed_img = img
                            
                            if max(orig_h, orig_w) > max_dim:
                                scale = max_dim / max(orig_h, orig_w)
                                new_width = int(orig_w * scale)
                                new_height = int(orig_h * scale)
                                processed_img = cv2.resize(img, (new_width, new_height), 
                                                         interpolation=cv2.INTER_AREA)
                                resized = True
                                
                            # 使用更高的JPEG质量
                            _, buffer = cv2.imencode('.jpg', processed_img, 
                                                   [cv2.IMWRITE_JPEG_QUALITY, 95])
                            jpeg_data = base64.b64encode(buffer).decode('utf-8')
                            
                            # 获取当前帧的宽高
                            current_width = processed_img.shape[1]
                            current_height = processed_img.shape[0]
                            
                            # 发送数据到WebSocket
                            websocket = active_connections.get(connection_id)
                            if websocket:
                                # 发送帧数据
                                await websocket.send_json({
                                    "type": "stream_data",
                                    "format": "jpeg",
                                    "data": jpeg_data,
                                    "frame_id": frame_id,
                                    "width": current_width,
                                    "height": current_height,
                                    "original_width": orig_w,
                                    "original_height": orig_h,
                                    "resized": resized
                                })
                                
                                processed_frames += 1
                                last_send_time = current_time
                            else:
                                logger.info(f"WebSocket连接已关闭，停止流处理: {connection_id}")
                                break
                                
                        except Exception as e:
                            logger.error(f"处理帧时发生错误: {e}")
                    
                # 检查WebSocket连接是否仍然活跃
                if connection_id not in active_connections:
                    logger.info(f"WebSocket连接已关闭，停止帧处理: {connection_id}")
                    break
                    
                # 短暂休眠，让出控制权
                await asyncio.sleep(0.01)
                
            logger.info(f"帧处理任务完成，共处理 {processed_frames} 帧")
            
        except asyncio.CancelledError:
            logger.info(f"帧处理任务被取消: {connection_id}")
        except Exception as e:
            logger.error(f"帧处理任务错误: {e}")
            # 通知客户端发生错误
            websocket = active_connections.get(connection_id)
            if websocket:
                await websocket.send_json({
                    "type": "error",
                    "message": f"帧处理错误: {str(e)}"
                })
        finally:
            logger.info(f"帧处理任务已结束: {connection_id}")
# 创建RTSP管理器实例
rtsp_manager = RTSPManager()

class FrameProcessor:
    def __init__(self):
        self.processing_times = deque(maxlen=50)  # 存储最近50次处理时间
        self.last_predictions = {}  # 存储每个目标的上一次预测结果
    
    def get_avg_processing_time(self):
        if not self.processing_times:
            return 0
        return sum(self.processing_times) / len(self.processing_times)
    
    def smooth_boxes(self, current_boxes, frame_id):
        """平滑检测框的位置"""
        if frame_id not in previous_boxes:
            previous_boxes[frame_id] = current_boxes
            return current_boxes
        
        smoothed_boxes = []
        prev_boxes = previous_boxes[frame_id]
        
        # 对每个当前检测框
        for curr_box in current_boxes:
            # 在上一帧中找到最匹配的框
            best_match = None
            min_dist = float('inf')
            
            for prev_box in prev_boxes:
                if prev_box["class"] == curr_box["class"]:
                    # 计算框中心点距离
                    curr_center = (curr_box["bbox"][0] + curr_box["bbox"][2]/2,
                                 curr_box["bbox"][1] + curr_box["bbox"][3]/2)
                    prev_center = (prev_box["bbox"][0] + prev_box["bbox"][2]/2,
                                 prev_box["bbox"][1] + prev_box["bbox"][3]/2)
                    
                    dist = ((curr_center[0] - prev_center[0])**2 +
                           (curr_center[1] - prev_center[1])**2)**0.5
                    
                    if dist < min_dist:
                        min_dist = dist
                        best_match = prev_box
            
            # 如果找到匹配的框，进行平滑处理
            if best_match and min_dist < 100:  # 设置最大匹配距离阈值
                smooth_box = {
                    "class": curr_box["class"],
                    "confidence": curr_box["confidence"],
                    "bbox": [
                        best_match["bbox"][0] * box_smooth_factor + curr_box["bbox"][0] * (1 - box_smooth_factor),
                        best_match["bbox"][1] * box_smooth_factor + curr_box["bbox"][1] * (1 - box_smooth_factor),
                        best_match["bbox"][2] * box_smooth_factor + curr_box["bbox"][2] * (1 - box_smooth_factor),
                        best_match["bbox"][3] * box_smooth_factor + curr_box["bbox"][3] * (1 - box_smooth_factor)
                    ]
                }
                smoothed_boxes.append(smooth_box)
            else:
                smoothed_boxes.append(curr_box)
        
        previous_boxes[frame_id] = smoothed_boxes
        return smoothed_boxes
frame_processor = FrameProcessor()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_tasks: Dict[str, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        connection_id = str(id(websocket))
        self.active_connections[connection_id] = websocket
        return connection_id

    async def disconnect(self, connection_id: str):
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            del self.active_connections[connection_id]
            try:
                await websocket.close()
            except Exception:
                pass

        # 取消并清理相关任务
        if connection_id in self.connection_tasks:
            task = self.connection_tasks[connection_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            del self.connection_tasks[connection_id]

    async def send_json(self, connection_id: str, message: dict):
        if connection_id in self.active_connections:
            try:
                await self.active_connections[connection_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                await self.disconnect(connection_id)
# 创建连接管理器实例
manager = ConnectionManager()

def get_model(models_name):
    """获取或加载YOLO模型"""
    if models_name not in models_cache:
        models_path = f"models/{models_name}.pt"
        try:
            if not Path(models_path).exists():
                logger.error(f"Model file not found: {models_path}")
                return None
            
            model = YOLO(models_path)
            
            # 使用GPU并进行优化
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            if device == 'cuda':
                model.to(device)
                # 使用半精度浮点数以提高性能
                if hasattr(model, 'model'):
                    model.model.half()
                logger.info("Using half precision on GPU")
            
            # 导出ONNX模型以提高性能
            try:
                onnx_path = f"models/{models_name}.onnx"
                if not Path(onnx_path).exists():
                    model.export(format='onnx', dynamic=True, half=True)
                    logger.info(f"Model exported to ONNX: {onnx_path}")
                    
                    # 尝试使用ONNX Runtime
                    import onnxruntime as ort
                    providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if device == 'cuda' else ['CPUExecutionProvider']
                    session = ort.InferenceSession(onnx_path, providers=providers)
                    models_cache[models_name] = {
                        'type': 'onnx',
                        'session': session,
                        'model': model
                    }
                    logger.info("Using ONNX Runtime for inference")
                    return models_cache[models_name]
            except Exception as e:
                logger.warning(f"ONNX optimization failed: {e}")
            
            models_cache[models_name] = {
                'type': 'pytorch',
                'model': model
            }
            logger.info(f"Model {models_name} loaded successfully on {device}")
        except Exception as e:
            logger.error(f"Error loading model {models_name}: {e}")
            return None
    return models_cache.get(models_name)

def process_frame(frame, models_info, frame_id, timestamp, total_frames=None, start_time=None):
    """处理单帧图像"""
    start_process_time = time.time()
    
    try:
        # 预处理图像
        orig_h, orig_w = frame.shape[:2]
        scale = min(max_size / orig_h, max_size / orig_w)
        
        if scale < 1:
            new_h, new_w = int(orig_h * scale), int(orig_w * scale)
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)  # 使用INTER_AREA以提高性能
        
        # 运行检测
        if models_info['type'] == 'onnx':
            # 使用ONNX Runtime进行推理
            session = models_info['session']
            # 预处理图像
            input_name = session.get_inputs()[0].name
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = frame.transpose(2, 0, 1)
            frame = np.expand_dims(frame, axis=0)
            frame = frame.astype(np.float32) / 255.0
            
            # 运行推理
            outputs = session.run(None, {input_name: frame})
            # 处理输出
            boxes = outputs[0]
            scores = outputs[1]
            classes = outputs[2]
            
            detections = []
            for i in range(len(boxes)):
                if scores[i] > 0.5:
                    box = boxes[i]
                    x1, y1, x2, y2 = box
                    w = x2 - x1
                    h = y2 - y1
                    
                    if scale < 1:
                        x1, x2 = x1 / scale, x2 / scale
                        y1, y2 = y1 / scale, y2 / scale
                        w = w / scale
                        h = h / scale
                    
                    class_id = int(classes[i])
                    class_name = models_info['model'].names[class_id]
                    
                    detections.append({
                        "class": class_name,
                        "confidence": float(scores[i]),
                        "bbox": [float(x1), float(y1), float(w), float(h)],
                        "x1": float(x1),
                        "y1": float(y1),
                        "x2": float(x2),
                        "y2": float(y2)
                    })
        else:
            # 使用PyTorch模型
            with torch.cuda.amp.autocast() if torch.cuda.is_available() else nullcontext():
                results = models_info['model'](frame, conf=0.5)[0]
            
            detections = []
            for r in results.boxes.data.tolist():
                x1, y1, x2, y2, conf, cls = r
                
                if scale < 1:
                    x1, x2 = x1 / scale, x2 / scale
                    y1, y2 = y1 / scale, y2 / scale
                
                w = x2 - x1
                h = y2 - y1
                
                class_name = results.names[int(cls)]
                
                detections.append({
                    "class": class_name,
                    "confidence": round(conf, 3),
                    "bbox": [float(x1), float(y1), float(w), float(h)],
                    "x1": float(x1),
                    "y1": float(y1),
                    "x2": float(x2),
                    "y2": float(y2)
                })
        
        # 应用框平滑
        smoothed_detections = frame_processor.smooth_boxes(detections, frame_id)
        
        processing_time = time.time() - start_process_time
        frame_processor.processing_times.append(processing_time)

        # 计算进度和剩余时间
        progress = None
        remaining_time = None
        if total_frames and start_time:
            progress = (frame_id + 1) / total_frames * 100
            elapsed_time = time.time() - start_time
            avg_time_per_frame = elapsed_time / (frame_id + 1)
            remaining_frames = total_frames - (frame_id + 1)
            remaining_time = remaining_frames * avg_time_per_frame
        
        return {
            "type": "detection_result",
            "objects": smoothed_detections,
            "frame_id": frame_id,
            "timestamp": timestamp,
            "processing_time": processing_time,
            "avg_processing_time": frame_processor.get_avg_processing_time(),
            "progress": progress,
            "remaining_time": remaining_time,
            "total_frames": total_frames,
            "image_width": orig_w,
            "image_height": orig_h
        }
    
    except Exception as e:
        logger.error(f"Error processing frame: {e}")
        return None

async def process_frame_queue(connection_id: str):
    """异步处理帧队列"""
    queue = frame_queues.get(connection_id)
    if not queue:
        return
        
    last_processed_time = 0
    skip_count = 0
    
    try:
        while connection_id in frame_queues and connection_id in manager.active_connections:
            try:
                if queue.empty():
                    await asyncio.sleep(0.01)
                    continue
                
                current_time = time.time()
                
                # 智能帧选择
                if queue.qsize() > 1:
                    while queue.qsize() > 1:
                        queue.get_nowait()
                        skip_count += 1
                    
                    if skip_count >= 10:
                        logger.info(f"Skipped {skip_count} frames for client {connection_id} to reduce latency")
                        skip_count = 0
                
                frame_data = queue.get_nowait()
                
                # 检查延迟
                latency = (current_time - frame_data["timestamp"]/1000) * 1000
                if latency > max_latency:
                    logger.debug(f"Dropping frame {frame_data['frame_id']} for client {connection_id} due to high latency: {latency:.0f}ms")
                    continue
                
                # 控制处理频率
                if current_time - last_processed_time < 0.033:
                    continue
                
                result = await asyncio.get_event_loop().run_in_executor(
                    executor,
                    process_frame,
                    frame_data["frame"],
                    frame_data["model"],
                    frame_data["frame_id"],
                    frame_data["timestamp"],
                    frame_data.get("total_frames"),
                    frame_data.get("start_time")
                )
                
                if result:
                    await manager.send_json(connection_id, result)
                    last_processed_time = current_time
            
            except Exception as e:
                logger.error(f"Error in frame queue processing for client {connection_id}: {e}")
                await asyncio.sleep(0.1)
    
    except asyncio.CancelledError:
        logger.info(f"Frame queue processing cancelled for client {connection_id}")
    except Exception as e:
        logger.error(f"Unexpected error in frame queue processing for client {connection_id}: {e}")
    finally:
        logger.info(f"Frame queue processing ended for client {connection_id}")

def non_max_suppression(boxes, scores, iou_threshold=0.45):
    """
    执行非极大值抑制(NMS)，去除重叠的检测框
    
    参数:
        boxes: 边界框列表 [[x, y, w, h], ...]
        scores: 对应的置信度分数
        iou_threshold: IoU阈值，高于此值的框会被抑制
        
    返回:
        保留的检测框的索引列表
    """
    try:
        # 检查输入有效性
        if len(boxes) == 0 or len(scores) != len(boxes):
            return []
        
        # 转换成numpy数组
        boxes = np.array(boxes)
        scores = np.array(scores)
        
        # 计算每个框的面积和右下角坐标
        x1 = boxes[:, 0]
        y1 = boxes[:, 1]
        w = boxes[:, 2]
        h = boxes[:, 3]
        x2 = x1 + w
        y2 = y1 + h
        area = w * h
        
        # 按照分数从高到低排序
        idxs = np.argsort(scores)[::-1]
        
        # 保留的框的索引
        keep = []
        
        while len(idxs) > 0:
            # 取分数最高的框
            i = idxs[0]
            keep.append(i)
            
            # 计算其他框与当前框的IoU
            xx1 = np.maximum(x1[i], x1[idxs[1:]])
            yy1 = np.maximum(y1[i], y1[idxs[1:]])
            xx2 = np.minimum(x2[i], x2[idxs[1:]])
            yy2 = np.minimum(y2[i], y2[idxs[1:]])
            
            # 计算重叠区域的宽和高
            w_inter = np.maximum(0, xx2 - xx1)
            h_inter = np.maximum(0, yy2 - yy1)
            
            # 计算重叠区域的面积
            intersection = w_inter * h_inter
            
            # 计算IoU
            union = area[i] + area[idxs[1:]] - intersection
            iou = intersection / (union + 1e-8)  # 避免除以0
            
            # 保留IoU小于阈值的框
            idxs = idxs[1:][iou < iou_threshold]
        
        return keep
    except Exception as e:
        logger.error(f"Error in NMS: {e}")
        return list(range(len(boxes)))  # 出错时返回所有框

@app.websocket("/ws/rtsp/preview")
async def websocket_endpoint(websocket: WebSocket):
    connection_id = await manager.connect(websocket)
    rtsp_sessions[connection_id] = {"status": "connected"}
    models_info = None
    
    try:
        # 等待客户端的连接请求
        while True:
            message = await websocket.receive_json()
            
            if message["type"] == "connect":
                # 发送连接确认
                await websocket.send_json({
                    "type": "connect_confirm"
                })
                logger.info(f"Client {connection_id} connected")
                continue
            
            # 处理RTSP预览请求
            elif message["type"] == "preview_request":
                # 获取RTSP URL
                stream_url = message.get("stream_url")
                device_id = message.get("device_id")
                
                if not stream_url:
                    await websocket.send_json({
                        "type": "error",
                        "message": "缺少流URL"
                    })
                    continue
                
                logger.info(f"收到预览请求: {device_id}, URL: {stream_url}")
                
                # 将WebSocket连接添加到活动连接字典
                active_connections[connection_id] = websocket
                
                # 启动RTSP流处理
                await websocket.send_json({
                    "type": "preview_connecting",
                    "message": "正在连接RTSP流，请稍候..."
                })
                
                result = await rtsp_manager.start_stream(connection_id, stream_url)
                
                if not result:
                    await websocket.send_json({
                        "type": "error",
                        "message": "启动流处理失败，可能该流已在处理中"
                    })
                continue
                
            elif message["type"] == "config":
                # 处理模型配置
                models_name = message.get("models_name")
                if not models_name:
                    await websocket.send_json({
                        "type": "error",
                        "message": "No model specified in configuration"
                    })
                    continue

                try:
                    logger.info(f"Loading model {models_name} for client {connection_id}")
                    models_info = get_model(message.get("models_id"))
                    
                    if not models_info:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Failed to load model: {models_name}"
                        })
                        continue
                                        
                    # 发送配置确认
                    await websocket.send_json({
                        "type": "config_confirm",
                        "model": models_name
                    })
                    logger.info(f"Model {models_name} configured successfully for client {connection_id}")
                
                except Exception as e:
                    error_msg = f"Error configuring model {models_name}: {str(e)}"
                    logger.error(error_msg)
                    await websocket.send_json({
                        "type": "error",
                        "message": error_msg
                    })
                continue
            
            # 增加处理图片检测请求的逻辑
            elif message["type"] == "image":
                # 处理单张图片检测请求
                if not models_info:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Model not configured. Please configure model first."
                    })
                    continue
                
                start_time = time.time()
                try:
                    # 获取图片信息
                    image_id = message.get("image_id", 0)
                    image_name = message.get("image_name", f"image_{image_id}")
                    timestamp = message.get("timestamp", time.time())
                    width = message.get("width", 0)
                    height = message.get("height", 0)
                    original_width = message.get("original_width", width)
                    original_height = message.get("original_height", height)
                    scale = message.get("scale", 1.0)
                    
                    logger.info(f"Processing image {image_name} (ID: {image_id}) for client {connection_id}")
                    
                    # 解码图像
                    decode_start_time = time.time()
                    try:
                        img_data = base64.b64decode(message.get("frame"))
                        nparr = np.frombuffer(img_data, np.uint8)
                        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        
                        if frame is None:
                            raise ValueError("Failed to decode image")
                        
                        decode_time = time.time() - decode_start_time
                        logger.info(f"Image decoded successfully in {decode_time:.3f}s, shape: {frame.shape}")
                    except Exception as e:
                        error_msg = f"Error decoding image: {str(e)}"
                        logger.error(error_msg)
                        await websocket.send_json({
                            "type": "error",
                            "message": error_msg
                        })
                        continue
                    
                    # 处理图片
                    try:
                        # 性能优化：如果图像尺寸过大，可以缩小后处理
                        max_dim = 1280  # 最大尺寸
                        orig_h, orig_w = frame.shape[:2]
                        target_frame = frame
                        target_scale = 1.0
                        
                        # 如果原始图像过大，先缩小进行检测，再缩放结果
                        if max(orig_h, orig_w) > max_dim:
                            resize_scale = max_dim / max(orig_h, orig_w)
                            new_h, new_w = int(orig_h * resize_scale), int(orig_w * resize_scale)
                            target_frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
                            target_scale = resize_scale
                            logger.info(f"Resized image for detection: {orig_w}x{orig_h} -> {new_w}x{new_h}")
                        
                        # 检测开始时间
                        detect_start_time = time.time()
                        
                        # 使用process_frame函数处理图片
                        result = process_frame(
                            frame=target_frame,
                            models_info=models_info,
                            frame_id=image_id,
                            timestamp=timestamp
                        )
                        
                        # 检测时间
                        detect_time = time.time() - detect_start_time
                        
                        if not result:
                            raise ValueError("Failed to process image")
                        
                        # 处理缩放以匹配原始尺寸
                        if target_scale < 1.0:
                            for obj in result["objects"]:
                                if "bbox" in obj:
                                    x, y, w, h = obj["bbox"]
                                    obj["bbox"] = [
                                        x / target_scale,
                                        y / target_scale,
                                        w / target_scale,
                                        h / target_scale
                                    ]
                                if all(k in obj for k in ["x1", "y1", "x2", "y2"]):
                                    obj["x1"] /= target_scale
                                    obj["y1"] /= target_scale
                                    obj["x2"] /= target_scale
                                    obj["y2"] /= target_scale
                        
                        # 应用非极大值抑制(NMS)处理重叠检测框
                        nms_start_time = time.time()
                        nms_applied = False
                        try:
                            if len(result["objects"]) > 1:
                                logger.info(f"Applying NMS on {len(result['objects'])} detections")
                                
                                # 提取边界框和分数
                                boxes = []
                                scores = []
                                for obj in result["objects"]:
                                    if "bbox" in obj:
                                        boxes.append(obj["bbox"])
                                        scores.append(obj["confidence"])
                                
                                # 应用NMS
                                if boxes and scores:
                                    keep_indices = non_max_suppression(boxes, scores, iou_threshold=0.45)
                                    
                                    # 仅保留NMS后的检测结果
                                    filtered_objects = [result["objects"][i] for i in keep_indices]
                                    logger.info(f"NMS reduced detections from {len(result['objects'])} to {len(filtered_objects)}")
                                    result["objects"] = filtered_objects
                                    nms_applied = True
                        except Exception as e:
                            logger.error(f"Error applying NMS: {e}")
                            # 继续使用原始检测结果
                        
                        nms_time = time.time() - nms_start_time
                        
                        # 如果图片进行了缩放，需要调整检测框坐标
                        if scale != 1.0 and original_width > 0 and original_height > 0:
                            scale_factor = 1.0 / scale
                            for obj in result["objects"]:
                                # 调整检测框坐标和尺寸
                                if "bbox" in obj:
                                    x, y, w, h = obj["bbox"]
                                    obj["bbox"] = [
                                        x * scale_factor,
                                        y * scale_factor,
                                        w * scale_factor,
                                        h * scale_factor
                                    ]
                                # 更新x1, y1, x2, y2坐标(如果存在)
                                if all(k in obj for k in ["x1", "y1", "x2", "y2"]):
                                    obj["x1"] *= scale_factor
                                    obj["y1"] *= scale_factor
                                    obj["x2"] *= scale_factor
                                    obj["y2"] *= scale_factor
                        
                        # 添加图片ID和名称到结果
                        result["image_id"] = image_id
                        result["image_name"] = image_name
                        result["original_width"] = original_width
                        result["original_height"] = original_height
                        
                        # 添加性能信息
                        total_time = time.time() - start_time
                        result["performance"] = {
                            "decode_time": round(decode_time * 1000, 2),  # ms
                            "detection_time": round(detect_time * 1000, 2),  # ms
                            "nms_time": round(nms_time * 1000, 2),  # ms
                            "total_time": round(total_time * 1000, 2),  # ms
                            "nms_applied": nms_applied
                        }
                        
                        logger.info(f"Image {image_name} processed in {total_time:.3f}s, found {len(result['objects'])} objects")
                        
                        # 发送检测结果
                        await websocket.send_json(result)
                        
                    except Exception as e:
                        error_msg = f"Error processing image: {str(e)}"
                        logger.error(error_msg)
                        await websocket.send_json({
                            "type": "error",
                            "message": error_msg
                        })
                except Exception as e:
                    error_msg = f"Error handling image detection request: {str(e)}"
                    logger.error(error_msg)
                    await websocket.send_json({
                        "type": "error",
                        "message": error_msg
                    })
                continue
                
            elif message["type"] == "video_info":
                # 处理视频信息
                if not models_info:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Model not configured. Please configure model first."
                    })
                    continue
                                        
                frame_queues[connection_id] = asyncio.Queue(maxsize=max_queue_size)
                logger.info(f"Video info received from client {connection_id}")
                
                # 启动帧处理任务
                task = asyncio.create_task(process_frame_queue(connection_id))
                manager.connection_tasks[connection_id] = task
                
            elif message["type"] == "frame":
                # 处理视频帧
                if not models_info:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Model not configured. Please configure model first."
                    })
                    continue
                                        
                try:
                    frame_data = message.get("frame")
                    frame_id = message.get("frame_id", 0)
                    current_time = time.time()
                    
                    # 检查帧延迟
                    frame_timestamp = message.get("timestamp", current_time)
                    latency = (current_time - frame_timestamp) * 1000
                    
                    if latency > max_latency:
                        logger.debug(f"Skipping frame {frame_id} for client {connection_id} due to high latency: {latency:.0f}ms")
                        continue
                    
                    if not frame_data:
                        continue
                                        
                    # 解码图像
                    img_data = base64.b64decode(frame_data)
                    nparr = np.frombuffer(img_data, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    if frame is None:
                        raise ValueError("Failed to decode image")
                    
                    # 将帧数据放入队列
                    results = await frame_queues[connection_id].put({
                        "frame": frame,
                        "model": models_info,
                        "frame_id": frame_id,
                        "timestamp": frame_timestamp,
                        "total_frames": message.get("total_frames"),
                        "start_time": message.get("start_time")
                    })
                    if results:
                        # 添加延迟信息到结果中
                        results["latency"] = latency
                        await websocket.send_json(results)
                    
                except Exception as e:
                    logger.error(f"Error processing frame: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Failed to process frame: {str(e)}"
                    })
            
            # 处理特定命令
            elif message["type"] == "start_stream":
                stream_url = message.get("url", "")
                device_id = message.get("device_id", None)  # 添加设备ID参数
                
                if not stream_url:
                    await manager.send_json(connection_id, {
                        "error": "未提供有效的流URL"
                    })
                    continue
                
                # 存储设备ID（如果有）
                if device_id:
                    rtsp_sessions[connection_id]["device_id"] = device_id
                
                # 启动RTSP流
                success = await rtsp_manager.start_stream(connection_id, stream_url)
                
                if success:
                    await manager.send_json(connection_id, {
                        "message": "RTSP流已启动",
                        "status": "started"
                    })
                else:
                    await manager.send_json(connection_id, {
                        "error": "无法启动RTSP流",
                        "status": "error"
                    })
            
            elif message["type"] == "stop_stream":
                await rtsp_manager.stop_stream(connection_id)
                await manager.send_json(connection_id, {
                    "message": "RTSP流已停止",
                    "status": "stopped"
                })
            
            else:
                # 处理其他现有命令...
                pass

    except WebSocketDisconnect:
        logger.info(f"Client {connection_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for client {connection_id}: {str(e)}")
    finally:
        # 确保断开连接时停止所有流处理
        if connection_id in active_connections:
            await rtsp_manager.stop_stream(connection_id)
        await manager.disconnect(connection_id)

@app.post("/api/v2/model/load")
async def load_model_api(model_data: dict):
    """加载模型API端点"""
    try:
        model_path = model_data.get("model_path")
        
        if not model_path:
            return {"status": "error", "message": "缺少必要参数"}
            
        model = YOLO(model_path)  # 加载模型
        classes = model.names  # 获取类别名称
        
        if model:
            return {
                "status": "success", 
                "message": "模型加载成功",                                  
                "classes": classes
            }
        else:
            return {"status": "error", "message": "模型加载失败"}
            
    except Exception as e:
        logger.error(f"加载模型失败: {e}")
        return {"status": "error", "message": f"加载模型失败: {str(e)}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 