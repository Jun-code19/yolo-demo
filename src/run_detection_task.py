import asyncio
import cv2
import numpy as np
import time
import threading
import logging
from collections import deque
from typing import List, Optional, Dict, Any
import os
import torch
from ultralytics import YOLO

import uuid
import colorsys
import base64 # 导入base64编码
from pathlib import Path # 导入路径模块
from threading import Lock # 导入锁
from datetime import datetime, timedelta # 导入日期时间模块

# 导入数据库模块
from src.database import (
    SessionLocal, DetectionConfig, DetectionEvent, Device, 
    DetectionPerformance, SaveMode, EventStatus
)
# 导入目标追踪模块
from src.tracker import ObjectTracker
# 导入数据推送模块
from src.data_pusher import data_pusher

logger = logging.getLogger(__name__)
# 导入GPU解码器
try:
    # from src.ffmpeg_decoder_docker_gpu import FFmpegGPUDecoder
    from src.ffmpeg_decoder_docker import FFmpegDecoderDocker
    # from src.ffmpeg_decoder import FFmpegDecoder
    GPU_DECODER_AVAILABLE = False
except ImportError:
    GPU_DECODER_AVAILABLE = False
    logger.warning("GPU解码器不可用，将使用OpenCV解码")

class DetectionTask:
    """优化后的检测任务类"""
    
    def __init__(self, device_id: str, device_name: str, device_ip: str, config_id: str, model_path: str, 
                 confidence: float, models_type: str, target_class: List[str], save_mode: SaveMode, area_coordinates:Optional[dict]=None):
        self.device_id = device_id
        self.device_name = device_name
        self.device_ip = device_ip
        self.config_id = config_id
        self.model_path = model_path       
        self.confidence = confidence
        self.models_type = models_type
        self.target_class = target_class
        self.save_mode = save_mode
        self.area_coordinates = area_coordinates  #点坐标值，前端生成的归一化坐标  
        self.class_colors = {}  # 用于存储每个类别的固定颜色
        self.class_names = None  # 用于存储类别名称
        self.stream_type = None

        self.stop_event = threading.Event()
        self.model = None
        self.device = None
        self.cap = None
        self.ffmpeg_decoder = None  # 添加GPU解码器
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
        
        # 设置智能分析区域坐标
        if self.area_coordinates:
            # 这里需要等到有实际帧时才能设置，因为需要frame_shape
            self.area_coordinates_set = False
        else:
            self.area_coordinates_set = True
            
        # 性能优化参数
        self.use_gpu_decoder = GPU_DECODER_AVAILABLE and torch.cuda.is_available()
        self.skip_frame_count = 5  # 跳帧数，可根据CPU负载动态调整
        self.last_performance_check = time.time()
        self.performance_check_interval = 3600  # 每3600秒检查一次性能
    
    def load_model(self): # 加载YOLO模型
        """加载YOLO模型"""
        try:
            # 获取模型的绝对路径并记录
            abs_model_path = os.path.abspath(self.model_path)
            logger.info(f"加载模型 - 路径: {abs_model_path}")
            
            # 设置离线模式，避免连接GitHub
            os.environ["ULTRALYTICS_OFFLINE"] = "1"
            # 禁用所有自动更新和在线检查
            os.environ["YOLO_NO_ANALYTICS"] = "1"
            os.environ["NO_VERSION_CHECK"] = "1"
            
            # 确保模型文件存在
            if not os.path.exists(abs_model_path):
                # 尝试在当前目录下的models文件夹中查找
                base_name = os.path.basename(abs_model_path)
                alt_path = os.path.join("models", base_name)
                alt_abs_path = os.path.abspath(alt_path)
                
                if os.path.exists(alt_abs_path):
                    abs_model_path = alt_abs_path
                    self.model_path = alt_path
                else:
                    logger.error(f"无法找到模型文件")
                    return False
            
            # 使用绝对路径加载模型
            # 最新YOLO版本可能需要使用以下方式加载本地模型
            # 设置环境变量确保使用本地模型
            os.environ["YOLO_VERBOSE"] = "0"  # 减少冗余日志
            
            # 根据文件扩展名确定模型类型
            model_ext = os.path.splitext(abs_model_path)[1].lower()
            
            # 直接使用本地文件路径加载
            try:
                # 强制指定task类型
                task_type = 'detect'
                if hasattr(self, 'models_type') and self.models_type == 'pose':
                    task_type = 'pose'
                    
                self.model = YOLO(abs_model_path, task=task_type)
   
                # 使用GPU并进行优化
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
                self.device = torch.device(device)
                self.model.to(self.device)
                
                self.class_names = self.model.names

                if device == 'cuda' and hasattr(self.model, 'model'): 
                    # 使用半精度浮点数以提高性能
                    if hasattr(self.model.model, 'dtype'):
                        self.model.model.half()

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
                logger.error(f"设备信息不存在: {self.device_id}")
                return False

            if device.device_type == 'nvr':
                stream_type = 1 if device.stream_type == 'sub' else 0
                rtsp_url = f"rtsp://{device.username}:{device.password}@{device.ip_address}:{device.port}/cam/realmonitor?channel={device.channel}&subtype={stream_type}"
            else:
                stream_type = 1 if device.stream_type == 'sub' else 0
                rtsp_url = f"rtsp://{device.username}:{device.password}@{device.ip_address}:{device.port}/cam/realmonitor?channel=1&subtype={stream_type}"
            
            self.stream_type = device.stream_type

            # 优先使用GPU解码器
            if self.use_gpu_decoder:
                try:
                    self.ffmpeg_decoder = FFmpegDecoderDocker(rtsp_url)
                    if self.ffmpeg_decoder.start():
                        self.connected = True
                        self.reconnect_attempts = 0
                        return True
                   
                except Exception as e:
                    logger.warning(f"GPU解码器初始化失败，回退到OpenCV: {e}")
            
            # 回退到OpenCV解码
            logger.info(f"使用OpenCV解码器连接: {self.device_id}")
            self.cap = cv2.VideoCapture(rtsp_url)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 设置缓冲区大小为1，减少延迟
            self.cap.set(cv2.CAP_PROP_FPS, 25)  # 设置帧率

            if self.cap.isOpened():
                self.fps = self.cap.get(cv2.CAP_PROP_FPS)
                self.connected = True
                self.reconnect_attempts = 0
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
                if not self.connected or error_count > 30:
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
                
                # 根据解码器类型读取帧
                if self.ffmpeg_decoder:
                    # 使用GPU解码器
                    try:
                        # 完全关闭调试信息，提高性能
                        ret, frame = self.ffmpeg_decoder.read()
                        
                    except Exception as e:
                        ret, frame = False, None
                else:
                    # 使用OpenCV解码器
                    ret, frame = self.cap.read()
                
                if not ret:
                    error_count += 1
                    logger.warning(f"从摄像机 {self.device_id} 获取帧失败 ({error_count}/30)")
                    
                    # 完全关闭调试信息，提高性能
                    time.sleep(0.01)  # 最小化等待时间，最大化实时性
                    continue
                
                # 重置错误计数
                if error_count > 0:
                    error_count = 0

                # 使用锁来确保线程安全
                with self.lock:
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
                if not self.load_model():
                    return
            
            # 启动读取帧的线程
            self.thread = threading.Thread(target=self.read_frame)
            self.thread.daemon = True
            self.thread.start()

            frame_count = 0

            if self.area_coordinates and self.area_coordinates.get('alarm_interval'):
                cooldown_period = self.area_coordinates.get('alarm_interval')
            else:
                cooldown_period = 10  # 检测事件的冷却时间（秒）

            # 动态调整参数
            skip_frame_count = self.skip_frame_count
            last_performance_check = time.time()
            
            while not self.stop_event.is_set():
                try:
                    # 性能监控和动态调整
                    current_time = time.time()
                    if current_time - last_performance_check > self.performance_check_interval:
                        self._adjust_performance_parameters()
                        last_performance_check = current_time
                        skip_frame_count = self.skip_frame_count
                                  
                    # 使用锁来安全地访问帧缓存
                    with self.lock:
                        if self.frame_buffer:
                            frame_rgb = self.frame_buffer[-1]  # 获取最新的帧
                        else:
                            time.sleep(0.01)  # 短暂等待
                            continue  # 如果没有帧，跳过

                    # 优化：每skip_frame_count帧执行一次检测，减少计算负担
                    frame_count += 1
                    if frame_count % skip_frame_count == 0:
                         # 执行检测
                        detect_frame = frame_rgb.copy()
                        img_result = frame_rgb.copy()                      
                        # 使用 try-except 捕获模型推理过程中的错误
                        try:
                            results = self.model(detect_frame, conf=self.confidence,iou=0.45,max_det=300,device=self.device)
                            # 获取速度
                            speed = results[0].speed
                            # 处理检测结果
                            detections = self.process_detection_results(results)                    
                            
                            # 首次设置区域坐标
                            if self.area_coordinates and not self.area_coordinates_set:
                                self.object_tracker.set_area_coordinates(self.area_coordinates, detect_frame.shape)
                                self.area_coordinates_set = True
                            
                            # 绘制区域框提示
                            self.draw_roi(detect_frame)

                            if detections:
                                if self.models_type == 'pose':
                                    # 姿态检测结果
                                    img_result = self.display_pose_results(detect_frame, results[0])
                                else:
                                    # 智能分析处理
                                    if self.area_coordinates and self.area_coordinates.get('analysisType'):
                                        # 开启目标追踪功能进行智能分析
                                        self.object_tracker.update(detections)
                                        img_result = self.object_tracker.draw_tracks(
                                            detect_frame.copy(), 
                                            max_trajectory_length=self.max_trajectory_length,
                                            show_boxes=True,
                                        )
                                        # 处理智能分析事件
                                        self._process_smart_analysis_events(img_result, detections, speed, cooldown_period)
                                    else:
                                        # 普通检测：仅显示检测结果，没有智能分析
                                        img_result = self.display_detection_results(detect_frame, results[0],show_boxes=True)
                                        # 处理检测事件
                                        self._process_detection_events(img_result, detections, speed, cooldown_period)                            

                            if not self.clients:
                                continue  # 没有客户端连接，跳过下面步骤
                            else:
                                self.broadcast_img_result(img_result, detections) # 向WebSocket客户端推送检测结果                                                               
                            
                        except Exception as e:
                            logger.error(f"模型推理过程中出错: {e}")
                            # 不终止整个检测循环，仅记录错误
                    
                    # 动态休眠，根据客户端连接情况调整
                    if self.clients:
                        time.sleep(0.01)  # 有客户端时短暂休眠
                    else:
                        time.sleep(0.05)  # 无客户端时较长休眠
                    
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
    
    def _adjust_performance_parameters(self):
        """动态调整性能参数"""
        try:
            import psutil
            
            # 获取系统资源使用情况
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            
            # 根据CPU使用率调整跳帧数
            if cpu_percent > 80:
                # 高CPU负载，增加跳帧数
                new_skip_frames = min(self.skip_frame_count + 2, 10)
                if new_skip_frames != self.skip_frame_count:
                    logger.info(f"CPU负载高({cpu_percent:.1f}%)，调整跳帧数: {self.skip_frame_count} -> {new_skip_frames}")
                    self.skip_frame_count = new_skip_frames
            elif cpu_percent < 50 and self.skip_frame_count > 3:
                # 低CPU负载，减少跳帧数
                new_skip_frames = max(self.skip_frame_count - 1, 4)
                if new_skip_frames != self.skip_frame_count:
                    logger.info(f"CPU负载低({cpu_percent:.1f}%)，调整跳帧数: {self.skip_frame_count} -> {new_skip_frames}")
                    self.skip_frame_count = new_skip_frames
                    
        except ImportError:
            # psutil不可用，使用默认参数
            pass
        except Exception as e:
            logger.warning(f"性能参数调整失败: {e}")

    def process_detection_results(self, results):
        """处理检测结果"""
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
        
        return detections
    # 显示检测结果
    def display_detection_results(self, img, results,show_boxes=True): # 显示检测结果
        if not hasattr(results, 'boxes') or results.boxes is None:
            return img
        
        if not show_boxes:
            return img

        boxes = results.boxes
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            conf = box.conf.cpu().numpy()[0]
            cls = int(box.cls.cpu().numpy()[0])
            
            if str(cls) not in self.target_class:
                continue

            color = self.get_class_color(cls)
            
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

    def get_class_color(self, class_id): # 获取类别颜色
        if class_id not in self.class_colors:
            if not self.class_colors:
                colors = self.generate_colors(len(self.class_names))
                self.class_colors = {i: color for i, color in enumerate(colors)}
            else:
                self.class_colors[class_id] = tuple(np.random.randint(0, 255, 3).tolist())
        return self.class_colors[class_id]

    def generate_colors(self, num_classes): # 生成颜色
        hsv_tuples = [(x / num_classes, 1., 1.) for x in range(num_classes)]
        colors = list(map(lambda x: colorsys.hsv_to_rgb(*x), hsv_tuples))
        colors = list(map(lambda x: (int(x[0] * 255), int(x[1] * 255), int(x[2] * 255)), colors))
        return colors

    # 启动/停止检测任务线程
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
        
        # 发送停止信号到消息队列
        try:
            if self.loop and not self.message_queue.empty():
                await self.message_queue.put(None)
        except Exception as e:
            logger.error(f"发送停止信号到消息队列失败: {e}")
        
        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                logger.warning(f"检测线程未能及时停止: {self.config_id}")

        # 释放摄像头资源
        if self.cap:
            self.cap.release()
            logger.info(f"OpenCV摄像头资源已释放: {self.config_id}")
            
        # 释放GPU解码器资源
        if self.ffmpeg_decoder:
            try:
                self.ffmpeg_decoder.stop()
                logger.info(f"GPU解码器资源已释放: {self.config_id}")
            except Exception as e:
                logger.error(f"释放GPU解码器资源失败: {e}")
    
    # 保存检测事件到数据库并存储图像/视频
    def _process_detection_events(self, img_result, detections, speed, cooldown_period): # 处理检测事件
        """处理检测事件"""
        # 判断是否需要创建检测事件
        current_time = time.time() # 当前时间
        if detections and (current_time - self.last_detection_time) > cooldown_period:
            self.last_detection_time = current_time
            self.push_detection_data(detections, img_result, speed)
            if self.save_mode.value != 'none':
                self.save_detection_event(img_result, detections)
            
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

            # 保存事件元数据
            event.meta_data = {
                "current_count": len(detections),
                "target_class": self.target_class
            }
            
            # 根据保存模式保存图像/视频
            save_dir = Path(f"storage/events/{current_time.strftime('%Y-%m-%d')}/{self.device_id}")
            save_dir.mkdir(parents=True, exist_ok=True)
            
            if self.save_mode in [SaveMode.screenshot, SaveMode.both]:
                # 绘制检测框和标签
                # annotated_frame = self.draw_detections(frame, detections)    
                # 保存带检测框的截图（原图）
                thumbnail_path = save_dir / f"{event_id}.jpg"
                if self.stream_type == 'sub':
                    cv2.imwrite(str(thumbnail_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
                else:
                    cv2.imwrite(str(thumbnail_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                event.thumbnail_path = str(thumbnail_path)
            
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
    
    def push_detection_data(self, detections, frame_rgb, speed): # 推送检测数据
        """推送检测数据"""
        if not data_pusher.push_configs:
            return
        
        if self.area_coordinates and self.area_coordinates.get('pushLabel'):
            push_label = self.area_coordinates.get('pushLabel')
        
            push_data = {
                "cameraInfo": self.device_name + ":" + self.device_ip,
                "deviceId": self.device_id,
                "enteredCount":0,
                "exitedCount":0,
                "stayingCount": len(detections),
                "passedCount":0,
                "recordTime": datetime.now().isoformat() + '+08:00',
                "event_description": "目标检测",
                "target_class": self.target_class
            }
            # 增加标签，使推送更灵活
            data_pusher.push_data(
                data=push_data, 
                image=frame_rgb, 
                tags=[push_label, f"device_{self.device_id}"],
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

    # 处理智能分析事件
    def _process_smart_analysis_events(self, img_result, detections, speed, cooldown_period): # 处理智能分析事件
        """处理智能分析事件"""
        try:
            # 获取触发的行为事件
            triggered_events = self.object_tracker.triggered_events
            current_time = time.time() # 当前时间

            for event_key, event_info in triggered_events.items():
                # 创建检测事件记录（用于行为分析）
                if self.area_coordinates.get('analysisType') == 'behavior':
                    self._create_behavior_event(event_info, img_result, detections)
                    self.push_behavior_event(event_info, img_result, detections, speed)
                elif self.area_coordinates.get('analysisType') == 'counting':                    
                    if self.area_coordinates.get('countingType') == 'occupancy':
                        self._check_alert(event_info['current_count'])
                        if (current_time - self.last_detection_time) > cooldown_period:
                            self.last_detection_time = current_time
                            self._create_counting_event(event_info, img_result, detections)
                            self.push_counting_event(event_info, img_result, detections, speed)             
                    else:
                        self._create_counting_event(event_info, img_result, detections)
                        self.push_counting_event(event_info, img_result, detections, speed)
                # 输出日志
                # logger.info(f"智能分析事件: {event_info['event_type']}, 轨迹ID: {event_info['track_id']}")
            
            # 清空已处理的事件
            self.object_tracker.triggered_events.clear()
            
        except Exception as e:
            logger.error(f"处理智能分析事件失败: {e}")
    
    def _create_behavior_event(self, event_info, frame, detections): # 创建行为事件记录
        """创建行为事件记录"""
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
                event_type='smart_behavior',# 智能行为事件
                confidence=max([d["confidence"] for d in detections]) if detections else 0.0,
                bounding_box=detections,
                status=EventStatus.new,
                created_at=current_time
            )

            # 保存事件元数据
            event.meta_data = {
                "analysis_type": self.area_coordinates.get('analysisType'),
                "behavior_type": self.area_coordinates.get('behaviorType'),
                "behavior_subtype": self.area_coordinates.get('behaviorSubtype'),
                "event_type": event_info['event_type'],
                "event_description": self._get_event_description(event_info['event_type']),
                "target_class": self.target_class           
            }
            
            # 根据保存模式保存图像/视频
            save_dir = Path(f"storage/events/{current_time.strftime('%Y-%m-%d')}/{self.device_id}")
            save_dir.mkdir(parents=True, exist_ok=True)
            
            if self.save_mode in [SaveMode.screenshot, SaveMode.both]:   
                # 保存带检测框的截图（原图）
                thumbnail_path = save_dir / f"{event_id}.jpg"
                if self.stream_type == 'sub':
                    cv2.imwrite(str(thumbnail_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
                else:
                    cv2.imwrite(str(thumbnail_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                event.thumbnail_path = str(thumbnail_path)
          
            # 提交事件
            db.add(event)
            db.commit()
            logger.info(f"已保存智能行为事件: {event_id}")
            
        except Exception as e:
            logger.error(f"保存智能行为事件失败: {e}")
            if 'db' in locals() and db:
                db.rollback()
        finally:
            if 'db' in locals() and db:
                db.close()
        
    def _create_counting_event(self, event_info, frame, detections): # 创建人数统计事件记录
        """创建人数统计事件记录"""
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
                event_type='smart_counting',# 智能人数统计事件
                confidence=max([d["confidence"] for d in detections]) if detections else 0.0,
                bounding_box=detections,
                status=EventStatus.new,
                created_at=current_time
            )

            # 保存事件元数据
            event.meta_data = {
                "analysis_type": self.area_coordinates.get('analysisType'),
                "counting_type": self.area_coordinates.get('countingType'),
                "counting_subtype": 'area_counting' if self.area_coordinates.get('countingType') == 'occupancy' else 'flow_counting',
                "event_type": event_info['event_type'],
                "event_description": self._get_event_description(event_info['event_type']),
                "target_class": self.target_class,
                "current_count": event_info['current_count'],
                "today_in_count": event_info['today_in_count'],
                "today_out_count": event_info['today_out_count']
            }
            
            # 根据保存模式保存图像/视频
            save_dir = Path(f"storage/events/{current_time.strftime('%Y-%m-%d')}/{self.device_id}")
            save_dir.mkdir(parents=True, exist_ok=True)
            
            if self.save_mode in [SaveMode.screenshot, SaveMode.both]:   
                # 保存带检测框的截图（原图）
                thumbnail_path = save_dir / f"{event_id}.jpg"
                if self.stream_type == 'sub':
                    cv2.imwrite(str(thumbnail_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
                else:
                    cv2.imwrite(str(thumbnail_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                event.thumbnail_path = str(thumbnail_path)
          
            # 提交事件
            db.add(event)
            db.commit()
            logger.info(f"已保存智能人数统计事件: {event_id}")
            
        except Exception as e:
            logger.error(f"保存智能人数统计事件失败: {e}")
            if 'db' in locals() and db:
                db.rollback()
        finally:
            if 'db' in locals() and db:
                db.close()

    def push_behavior_event(self, event_info, frame, detections, speed): # 推送行为事件
        """推送行为事件"""
        if not data_pusher.push_configs:
            return
        
        if self.area_coordinates and self.area_coordinates.get('pushLabel'):
            push_label = self.area_coordinates.get('pushLabel')
       
            push_data = {
                "cameraInfo": self.device_name + ":" + self.device_ip,
                "deviceId": self.device_id,
                "enteredCount":0,
                "exitedCount":0,
                "stayingCount": event_info['current_count'],
                "passedCount":0,
                "recordTime": datetime.now().isoformat() + '+08:00',
                "event_description": self._get_event_description(event_info['event_type']),
                "target_class": self.target_class
            }
            # 增加标签，使推送更灵活
            data_pusher.push_data(
                data=push_data, 
                image=frame, 
                tags=[push_label, f"device_{self.device_id}"],
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
                    frame_width=frame.shape[1],
                    frame_height=frame.shape[0],
                    objects_detected=len(detections)
                )
                db.add(perf)
                db.commit()
            except Exception as e:
                logger.error(f"保存性能数据失败: {e}")
                db.rollback()
            finally:
                db.close()

    def push_counting_event(self, event_info, frame, detections, speed): # 推送人数统计事件
        """推送人数统计事件"""
        if not data_pusher.push_configs:
            return
        
        if self.area_coordinates and self.area_coordinates.get('pushLabel'):
            push_label = self.area_coordinates.get('pushLabel')
       
            push_data = {
                "cameraInfo": self.device_name + ":" + self.device_ip,
                "deviceId": self.device_id,
                "enteredCount": event_info['today_in_count'],
                "exitedCount": event_info['today_out_count'],
                "stayingCount": event_info['current_count'],
                "passedCount":0,
                "recordTime": datetime.now().isoformat() + '+08:00',
                "event_description": self._get_event_description(event_info['event_type']),
                "target_class": self.target_class
            }
            # 增加标签，使推送更灵活
            data_pusher.push_data(
                data=push_data, 
                image=frame, 
                tags=[push_label, f"device_{self.device_id}"],
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
                    frame_width=frame.shape[1],
                    frame_height=frame.shape[0],
                    objects_detected=len(detections)
                )
                db.add(perf)
                db.commit()
            except Exception as e:
                logger.error(f"保存性能数据失败: {e}")
                db.rollback()
            finally:
                db.close()

    def _check_alert(self, current_count):
        """检查人数是否超过预警阈值"""

        if self.area_coordinates.get('enableAlert') == False or self.area_coordinates.get('alertThreshold') == None:
            return
        
        if not data_pusher.push_configs:
            return

        if current_count >= self.area_coordinates.get('alertThreshold'):
            # 生成预警消息
            warning_msg = f"人群密度预警：{self.device_id} 区域人数达到 {current_count}人，超过预警阈值({self.area_coordinates.get('alertThreshold')}人)"
            
            # 发送预警（可以通过数据推送模块发送到外部系统）
            if self.area_coordinates.get('pushLabel'):
                push_label = self.area_coordinates.get('pushLabel')
                data_pusher.push_data(
                    data={
                        "analysis_type": 'counting',
                        "counting_type": 'occupancy',
                        "config_id": self.config_id,
                        "device_id": self.device_id,
                        "alert_threshold": self.area_coordinates.get('alertThreshold'),
                        "current_count": current_count,
                        "message": warning_msg,
                        "timestamp": datetime.now().isoformat()
                    },
                    tags=[push_label, f"device_{self.device_id}"],
                )
            
            logger.warning(f"人群密度预警: {warning_msg}")

    def _get_event_description(self, event_type): # 获取事件描述
        """获取事件描述"""
        descriptions = {
            'area_enter': '进入检测区域',
            'area_exit': '离开检测区域',
            'line_cross': '穿越检测线',
            'line_cross_in': '穿越检测线（进入方向）',
            'line_cross_out': '穿越检测线（离开方向）',
            'enter_area': '进入统计区域',
            'exit_area': '离开统计区域',
            'occupancy_change_increase': '区域内人数增加',
            'occupancy_change_decrease': '区域内人数减少'
        }
        return descriptions.get(event_type, '未知事件')

    # 向所有WebSocket客户端广播检测结果
    def broadcast_img_result(self, pose_frame, detections): # 向所有WebSocket客户端广播检测结果
        """向所有WebSocket客户端广播检测结果"""
        if not self.clients:
            return  # 没有客户端连接，跳过
        
        try:            
            
            # 将帧转换为JPEG，增加质量参数
            if self.stream_type == 'sub':
                _, buffer = cv2.imencode('.jpg', pose_frame, [cv2.IMWRITE_JPEG_QUALITY, 100])  # 提高JPEG质量
            else:
                _, buffer = cv2.imencode('.jpg', pose_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])  # 提高JPEG质量
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

    def normalize_points(self, points, frame_shape): #归一化坐标转换
        """归一化坐标转换"""
        h,w = frame_shape[:2]
        return [(int(p['x']*w), int(p['y']*h)) for p in points]

    def draw_roi(self, frame, line_color=(0,255,0), fill_color=(0,0,0,0), thickness=2, line_type=cv2.LINE_AA): # 绘制线段/区域 ROI（支持line/area类型）
        """
        绘制线段/区域 ROI（支持line/area类型）
        :param frame: 输入图像
        :param roi_type: ROI类型（'line'或'area'或'occupancy'或'flow'） 
        :param roi_points: ROI坐标列表 [[x1,y1], [x2,y2],...]
        :param line_color: 线段/边框颜色 (BGR格式)
        :param fill_color: 填充颜色 (BGR+Alpha格式)
        :param thickness: 线宽
        :param line_type: 线型（默认抗锯齿）
        """
        roi_type = None
        roi_points = None
        # 获取区域配置
        if(self.area_coordinates and self.area_coordinates['analysisType']): 
            roi_type = self.area_coordinates['behaviorType'] if self.area_coordinates['analysisType'] == 'behavior' else self.area_coordinates['countingType']
            roi_points = self.area_coordinates['points']
        else:
            return

        if roi_type not in ['line', 'area', 'occupancy', 'flow']:
            raise ValueError("Invalid ROI type. Must be 'line' or 'area' or 'occupancy' or 'flow'")
        
        line = self.normalize_points(roi_points, frame.shape)

        # 转换为整数坐标
        roi_array = np.array(line, np.int32)
        
        if roi_type == 'line' or roi_type == 'flow':
            # 线段绘制（至少需要2个点）
            if len(roi_array) < 2:
                return
            # 绘制线段轮廓
            cv2.polylines(frame, [roi_array], False, line_color, thickness, line_type)
            # 绘制中间点标记（可选）
            for pt in roi_array:
                cv2.circle(frame, tuple(pt), 3, line_color, -1)
                
        elif roi_type == 'area' or roi_type == 'occupancy':
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