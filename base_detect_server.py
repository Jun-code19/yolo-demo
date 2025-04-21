import asyncio
import json
import cv2
import numpy as np
import time
import threading
import logging
import uuid
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union
from collections import deque
import base64
from io import BytesIO
from PIL import Image
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from ultralytics import YOLO
import torch
from sqlalchemy.orm import Session
import concurrent.futures
from threading import Lock  # 导入锁
from src.tracker import ObjectTracker
import colorsys
# 导入独立的数据推送模块
from src.data_push import data_pusher
from pydantic import BaseModel

from models.database import (
    SessionLocal, DetectionConfig, DetectionEvent, Device, 
    DetectionModel, DetectionPerformance, SaveMode,
    EventStatus, Base, engine, get_db, DataPushConfig, PushMethod
)

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

            rtsp_url = f"rtsp://{device.username}:{device.password}@{device.ip_address}:{device.port}/cam/realmonitor?channel=1&subtype=0"
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

    async def get_push_stats(self): # 获取所有数据推送的统计信息
        """获取所有数据推送的统计信息"""
        return data_pusher.get_push_stats()

    async def reload_push_config(self, push_id: str, db: Session): # 重新加载指定的推送配置
        """重新加载指定的推送配置"""
        return data_pusher.reload_push_config(push_id, db)

# 创建检测服务器实例
detection_server = DetectionServer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用程序生命周期管理"""
    logger.info("检测服务器启动中...")
    
    # 创建数据库表（如果不存在）
    Base.metadata.create_all(bind=engine)
    
    await startup_push_service()

    # 启动已启用的检测任务
    db = SessionLocal()
    await detection_server.start_all_enabled(db)
    db.close()
    
    yield
    
    # 服务关闭时停止所有检测任务
    logger.info("检测服务器关闭中...")
    for config_id, task in list(detection_server.tasks.items()):
        task.stop()

    await shutdown_push_service()

    # 确保所有任务完成
    # tasks = asyncio.all_tasks()
    # for task in tasks:
    #     if task is not asyncio.current_task():
    #         task.cancel()
    
    # # 等待所有任务完成
    # await asyncio.gather(*tasks, return_exceptions=True)


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
async def start_detection_api(config_id: str, db: Session = Depends(get_db)): # 启动检测任务API
    """启动检测任务API"""
    return await detection_server.start_detection(config_id, db)


@app.post("/api/v2/detection/{config_id}/stop")
async def stop_detection_api(config_id: str, db: Session = Depends(get_db)): # 停止检测任务API
    """停止检测任务API"""
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

# 添加数据推送相关的API接口
class PushDataBase(BaseModel):
    push_name: str
    push_method: str
    config_id: str
    tags: List[str]
    http_url: str
    http_method: str
    tcp_host: str
    tcp_port: int
    mqtt_broker: str
    mqtt_port: int
    mqtt_topic: str
    mqtt_username: str
    mqtt_password: str
    mqtt_use_tls: bool
    include_image: bool

class PushCreate(PushDataBase):
    pass

class PushUpdate(PushDataBase):
    push_name: Optional[str] = None
    push_method: Optional[str] = None
    config_id: Optional[str] = None
    tags: Optional[List[str]] = None
    http_url: Optional[str] = None
    http_method: Optional[str] = None
    tcp_host: Optional[str] = None
    tcp_port: Optional[int] = None
    mqtt_broker: Optional[str] = None
    mqtt_port: Optional[int] = None
    mqtt_topic: Optional[str] = None
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_use_tls: Optional[bool] = None
    include_image: Optional[bool] = None
    enabled: Optional[bool] = None

class PushResponse(BaseModel):
    push_id: str
    push_name: str
    config_id: str
    tags: List[str]
    push_method: str
    http_url: str
    http_method: str
    tcp_host: str
    tcp_port: int
    mqtt_broker: str
    mqtt_port: int
    mqtt_topic: str
    mqtt_username: str
    mqtt_password: str
    mqtt_use_tls: bool
    include_image: bool
    created_at: datetime
    last_push_time: datetime

@app.get("/api/v2/push/stats")
async def get_push_stats(): # 获取所有数据推送的统计信息
    """获取所有数据推送的统计信息"""
    return await detection_server.get_push_stats()


@app.post("/api/v2/push/reload/{push_id}")
async def reload_push_config(push_id: str, db: Session = Depends(get_db)): # 重新加载指定的推送配置
    """重新加载指定的推送配置"""
    return await detection_server.reload_push_config(push_id, db)

@app.post("/api/v2/push/create")
async def create_push_config(pushdata: PushCreate, db: Session = Depends(get_db)): # 创建新的数据推送配置
    """创建新的数据推送配置"""
    try:
        # 验证推送方法
        try:
            method = PushMethod(pushdata.push_method.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的推送方法: {pushdata.push_method}")

        # 检查检测配置是否存在（如果指定了）
        if pushdata.config_id:
            config = db.query(DetectionConfig).filter(DetectionConfig.config_id == pushdata.config_id).first()
            if not config:
                raise HTTPException(status_code=404, detail=f"未找到检测配置: {pushdata.config_id}")
        else:
            pushdata.config_id = None

        # 根据推送方法验证必要的参数
        if method == PushMethod.http or method == PushMethod.https:
            if not pushdata.http_url:    
                raise HTTPException(status_code=400, detail="HTTP/HTTPS推送需要URL")
        elif method == PushMethod.tcp:
            if not pushdata.tcp_host or not pushdata.tcp_port:
                raise HTTPException(status_code=400, detail="TCP推送需要主机和端口")
        elif method == PushMethod.mqtt:
            if not pushdata.mqtt_broker or not pushdata.mqtt_topic:
                raise HTTPException(status_code=400, detail="MQTT推送需要代理和主题")

        # 创建新的推送配置
        push_config = DataPushConfig(
            push_name=pushdata.push_name,
            config_id=pushdata.config_id,  # 现在可以为空
            tags=pushdata.tags or [],  # 添加标签
            push_method=method,
            http_url=pushdata.http_url,
            http_method=pushdata.http_method,
            tcp_host=pushdata.tcp_host,
            tcp_port=pushdata.tcp_port,
            mqtt_broker=pushdata.mqtt_broker,
            mqtt_port=pushdata.mqtt_port,
            mqtt_topic=pushdata.mqtt_topic,
            mqtt_username=pushdata.mqtt_username,
            mqtt_password=pushdata.mqtt_password,
            mqtt_use_tls=pushdata.mqtt_use_tls,
            include_image=pushdata.include_image,
            http_headers={} if method in [PushMethod.http, PushMethod.https] else None
        )

        db.add(push_config)
        db.commit()
        db.refresh(push_config)

        # 重新加载推送配置
        data_pusher.reload_push_config(push_config.push_id, db)

        return {
            "status": "success",
            "message": "推送配置已创建",
            "push_id": push_config.push_id
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        logger.error(f"创建推送配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建推送配置失败: {str(e)}")

@app.get("/api/v2/push/list")
async def list_push_configs(config_id: str = None, tag: str = None, db: Session = Depends(get_db)): # 获取推送配置列表，支持按配置ID或标签筛选
    """获取推送配置列表，支持按配置ID或标签筛选"""
    try:
        query = db.query(DataPushConfig)
        
        # 根据配置ID筛选
        if config_id:
            query = query.filter(DataPushConfig.config_id == config_id)
        
        # 根据标签筛选
        if tag:
            query = query.filter(DataPushConfig.tags.any(tag))
        
        configs = query.all()
        return {
            "status": "success",
            "configs": [
                {
                    "push_id": config.push_id,
                    "push_name": config.push_name,
                    "config_id": config.config_id,
                    "tags": config.tags,  # 添加标签
                    "push_method": config.push_method.value,
                    "enabled": config.enabled,
                    "http_url": config.http_url,
                    "http_method": config.http_method,
                    "tcp_host": config.tcp_host,
                    "tcp_port": config.tcp_port,
                    "mqtt_broker": config.mqtt_broker,
                    "mqtt_port": config.mqtt_port,
                    "mqtt_topic": config.mqtt_topic,
                    "include_image": config.include_image,
                    "created_at": config.created_at.isoformat() if config.created_at else None,
                    "last_push_time": config.last_push_time.isoformat() if config.last_push_time else None
                }
                for config in configs
            ]
        }
    except Exception as e:
        logger.error(f"获取推送配置列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取推送配置列表失败: {str(e)}")

@app.put("/api/v2/push/{push_id}")
async def update_push_config(push_id: str, pushdata: PushUpdate, db: Session = Depends(get_db)): # 更新推送配置
    """更新推送配置"""
    try:
        # 查找推送配置
        push_config = db.query(DataPushConfig).filter(DataPushConfig.push_id == push_id).first()
        if not push_config:
            raise HTTPException(status_code=404, detail=f"未找到推送配置: {push_id}")

        # 更新字段
        if pushdata.push_name is not None:
            push_config.push_name = pushdata.push_name
        if pushdata.config_id is not None:  # 允许将config_id设置为None
            # 如果有config_id，检查是否存在
            if pushdata.config_id and not db.query(DetectionConfig).filter(DetectionConfig.config_id == pushdata.config_id).first():
                raise HTTPException(status_code=404, detail=f"未找到检测配置: {pushdata.config_id}")
            push_config.config_id = pushdata.config_id
        if pushdata.tags is not None:
            push_config.tags = pushdata.tags
        if pushdata.enabled is not None:
            push_config.enabled = pushdata.enabled
        if pushdata.http_url is not None:
            push_config.http_url = pushdata.http_url
        if pushdata.http_method is not None:
            push_config.http_method = pushdata.http_method
        if pushdata.tcp_host is not None:
            push_config.tcp_host = pushdata.tcp_host
        if pushdata.tcp_port is not None:
            push_config.tcp_port = pushdata.tcp_port
        if pushdata.mqtt_broker is not None:
            push_config.mqtt_broker = pushdata.mqtt_broker
        if pushdata.mqtt_port is not None:
            push_config.mqtt_port = pushdata.mqtt_port
        if pushdata.mqtt_topic is not None:
            push_config.mqtt_topic = pushdata.mqtt_topic
        if pushdata.mqtt_username is not None:
            push_config.mqtt_username = pushdata.mqtt_username
        if pushdata.mqtt_password is not None:
            push_config.mqtt_password = pushdata.mqtt_password
        if pushdata.mqtt_use_tls is not None:
            push_config.mqtt_use_tls = pushdata.mqtt_use_tls
        if pushdata.include_image is not None:
            push_config.include_image = pushdata.include_image

        push_config.updated_at = datetime.now()
        db.commit()

        # 重新加载推送配置
        data_pusher.reload_push_config(push_id, db)

        return {
            "status": "success",
            "message": "推送配置已更新"
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        logger.error(f"更新推送配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新推送配置失败: {str(e)}")

@app.delete("/api/v2/push/{push_id}")
async def delete_push_config(push_id: str, db: Session = Depends(get_db)): # 删除推送配置
    """删除推送配置"""
    try:
        # 查找推送配置
        push_config = db.query(DataPushConfig).filter(DataPushConfig.push_id == push_id).first()
        if not push_config:
            raise HTTPException(status_code=404, detail=f"未找到推送配置: {push_id}")

        db.delete(push_config)
        db.commit()

        # 从缓存中删除推送配置
        data_pusher.reload_push_config(push_id, db)

        return {
            "status": "success",
            "message": "推送配置已删除"
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        logger.error(f"删除推送配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除推送配置失败: {str(e)}")

@app.post("/api/v2/push/test/{push_id}")
async def test_push_config(push_id: str, db: Session = Depends(get_db)): # 测试推送配置
    """测试推送配置"""
    try:
        # 查找推送配置
        push_config = db.query(DataPushConfig).filter(DataPushConfig.push_id == push_id).first()
        if not push_config:
            raise HTTPException(status_code=404, detail=f"未找到推送配置: {push_id}")

        # 创建测试数据
        test_data = {
            "timestamp": datetime.now().isoformat(),
            "test": True,
            "message": "这是一条测试消息",
            "push_id": push_id
        }

        # 根据推送方法进行测试
        success = False
        if push_config.push_method == PushMethod.http or push_config.push_method == PushMethod.https:
            success = data_pusher._push_http(push_config, test_data)
        elif push_config.push_method == PushMethod.tcp:
            success = data_pusher._push_tcp(push_config, test_data)
        elif push_config.push_method == PushMethod.mqtt:
            success = data_pusher._push_mqtt(push_config, test_data)

        return {
            "status": "success" if success else "failure",
            "message": "推送测试成功" if success else "推送测试失败"
        }

    except Exception as e:
        logger.error(f"测试推送配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"测试推送配置失败: {str(e)}")

# 启动应用时加载已配置的推送任务
@app.on_event("startup")
async def startup_push_service(): # 启动时加载推送配置
    """启动时加载推送配置"""
    db = SessionLocal()
    try:
        data_pusher.load_push_configs(db)
        data_pusher.start()
        logger.info("数据推送服务已启动")
    finally:
        db.close()

# 停止应用时关闭推送服务
@app.on_event("shutdown")
async def shutdown_push_service(): # 停止时关闭推送服务
    """关闭推送服务"""
    data_pusher.stop()
    logger.info("数据推送服务已关闭")

if __name__ == "__main__":
    import uvicorn
    logger.info("正在启动检测服务器...")
    uvicorn.run(app, host="0.0.0.0", port=8000) 