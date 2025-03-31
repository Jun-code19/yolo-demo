import asyncio
import threading
import time
import logging
import cv2
import numpy as np
import uuid
import os
from datetime import datetime
from sqlalchemy.orm import Session
from pathlib import Path
from ultralytics import YOLO

from models.database import (
    SessionLocal, DetectionConfig, DetectionEvent, Device, 
    DetectionModel, DetectionPerformance, SaveMode,
    EventStatus
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DetectionManager:
    """管理设备检测任务的类"""
    
    def __init__(self):
        self.active_tasks = {}  # 存储活跃的检测任务 {device_id: task}
        self.stop_events = {}   # 停止事件 {device_id: event}
        self.device_configs = {}  # 设备检测配置 {device_id: config}
        self.loaded_models = {}  # 加载的模型 {model_id: model}
        self.thread_pool = {}   # 线程池 {device_id: thread}
        self.frame_buffers = {}  # 帧缓冲区 {device_id: deque}
        
        # 存储路径
        self.base_storage_path = Path("storage/detection")
        self.base_storage_path.mkdir(parents=True, exist_ok=True)
    
    def get_active_devices(self):
        """获取所有活跃的检测设备"""
        return list(self.active_tasks.keys())
    
    async def start_detection(self, device_id: str, config_id: str = None):
        """为设备启动检测任务"""
        if device_id in self.active_tasks:
            logger.info(f"设备 {device_id} 的检测任务已在运行")
            return False
        
        # 获取检测配置
        db = SessionLocal()
        try:
            # 获取设备
            device = db.query(Device).filter(Device.device_id == device_id).first()
            if not device:
                logger.error(f"设备 {device_id} 不存在")
                return False
            
            # 获取设备的检测配置
            if config_id:
                config = db.query(DetectionConfig).filter(
                    DetectionConfig.config_id == config_id,
                    DetectionConfig.device_id == device_id,
                    DetectionConfig.enabled == True
                ).first()
            else:
                # 如果没有指定config_id，获取设备的第一个启用的配置
                config = db.query(DetectionConfig).filter(
                    DetectionConfig.device_id == device_id,
                    DetectionConfig.enabled == True
                ).first()
            
            if not config:
                logger.error(f"设备 {device_id} 没有可用的检测配置")
                return False
            
            # 获取模型信息
            model_info = db.query(DetectionModel).filter(
                DetectionModel.models_id == config.models_id,
                DetectionModel.is_active == True
            ).first()
            
            if not model_info:
                logger.error(f"模型 {config.models_id} 不存在或未激活")
                return False
            
            # 存储配置信息
            self.device_configs[device_id] = {
                "config": config,
                "model_info": model_info,
                "device_info": device
            }
            
            # 加载模型(如果尚未加载)
            if config.models_id not in self.loaded_models:
                try:
                    model_path = model_info.file_path
                    logger.info(f"加载模型: {model_path}")
                    model = YOLO(model_path)
                    self.loaded_models[config.models_id] = model
                except Exception as e:
                    logger.error(f"加载模型失败: {e}")
                    return False
            
            # 创建停止事件
            stop_event = threading.Event()
            self.stop_events[device_id] = stop_event
            
            # 启动检测线程
            detection_thread = threading.Thread(
                target=self._run_detection,
                args=(device_id, stop_event),
                daemon=True
            )
            self.thread_pool[device_id] = detection_thread
            detection_thread.start()
            
            logger.info(f"设备 {device_id} 的检测任务已启动")
            return True
            
        except Exception as e:
            logger.error(f"启动检测任务时发生错误: {e}")
            return False
        finally:
            db.close()
    
    async def stop_detection(self, device_id: str):
        """停止设备的检测任务"""
        if device_id not in self.active_tasks:
            logger.warning(f"设备 {device_id} 没有运行中的检测任务")
            return False
        
        # 设置停止事件
        if device_id in self.stop_events:
            self.stop_events[device_id].set()
        
        # 等待线程结束
        if device_id in self.thread_pool:
            thread = self.thread_pool[device_id]
            if thread.is_alive():
                thread.join(timeout=5)
        
        # 清理资源
        self.active_tasks.pop(device_id, None)
        self.stop_events.pop(device_id, None)
        self.thread_pool.pop(device_id, None)
        self.device_configs.pop(device_id, None)
        
        logger.info(f"设备 {device_id} 的检测任务已停止")
        return True
    
    def add_frame(self, device_id: str, frame, frame_info=None):
        """向设备的帧缓冲区添加帧"""
        if device_id not in self.frame_buffers:
            from collections import deque
            self.frame_buffers[device_id] = deque(maxlen=10)
        
        if frame_info is None:
            frame_info = {}
        
        frame_data = {
            "frame": frame,
            "timestamp": time.time(),
            "info": frame_info
        }
        
        self.frame_buffers[device_id].append(frame_data)
    
    def _run_detection(self, device_id, stop_event):
        """检测线程的主函数"""
        logger.info(f"设备 {device_id} 的检测线程已启动")
        
        config_data = self.device_configs.get(device_id)
        if not config_data:
            logger.error(f"未找到设备 {device_id} 的配置信息")
            return
        
        config = config_data["config"]
        model_info = config_data["model_info"]
        device_info = config_data["device_info"]
        
        # 获取模型
        model = self.loaded_models.get(config.models_id)
        if not model:
            logger.error(f"未找到模型 {config.models_id}")
            return
        
        # 创建帧缓冲区
        if device_id not in self.frame_buffers:
            from collections import deque
            self.frame_buffers[device_id] = deque(maxlen=10)
        
        # 处理计数
        frame_count = 0
        event_count = 0
        last_save_time = time.time()
        min_save_interval = 1.0  # 最小保存间隔(秒)
        
        try:
            while not stop_event.is_set():
                # 检查是否有新帧
                if not self.frame_buffers.get(device_id) or len(self.frame_buffers[device_id]) == 0:
                    time.sleep(0.01)
                    continue
                
                # 获取最新帧
                frame_data = self.frame_buffers[device_id].popleft()
                frame = frame_data["frame"]
                timestamp = frame_data["timestamp"]
                frame_info = frame_data["info"]
                
                # 运行检测
                t_start = time.time()
                
                # 前处理时间
                t_preprocess_start = time.time()
                
                # 检测前处理 - 调整大小以加速处理
                height, width = frame.shape[:2]
                max_dim = 640  # 根据模型需求可能需要调整
                
                # 计算缩放比例
                scale = min(max_dim / width, max_dim / height)
                if scale < 1:
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    resized_frame = cv2.resize(frame, (new_width, new_height))
                else:
                    resized_frame = frame
                    scale = 1.0
                
                t_preprocess_end = time.time()
                preprocess_time = (t_preprocess_end - t_preprocess_start) * 1000  # ms
                
                # 运行检测
                t_detect_start = time.time()
                results = model(resized_frame, conf=config.sensitivity)
                t_detect_end = time.time()
                detection_time = (t_detect_end - t_detect_start) * 1000  # ms
                
                # 后处理
                t_postprocess_start = time.time()
                
                # 过滤检测结果
                detections = []
                has_detection = False
                target_classes = config.target_classes
                
                if len(results) > 0:
                    result = results[0]  # 获取第一个结果
                    boxes = result.boxes
                    
                    for i, box in enumerate(boxes):
                        cls_id = int(box.cls.item())
                        cls_name = model.names[cls_id]
                        conf = box.conf.item()
                        
                        # 检查是否为目标类别
                        if target_classes and cls_name not in target_classes:
                            continue
                        
                        # 获取边界框并还原到原始尺寸
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        if scale != 1.0:
                            x1 /= scale
                            y1 /= scale
                            x2 /= scale
                            y2 /= scale
                        
                        detections.append({
                            "class": cls_name,
                            "confidence": conf,
                            "box": [x1, y1, x2, y2]
                        })
                        has_detection = True
                
                t_postprocess_end = time.time()
                postprocess_time = (t_postprocess_end - t_postprocess_start) * 1000  # ms
                
                t_end = time.time()
                total_time = (t_end - t_start) * 1000  # ms
                
                # 记录处理性能
                frame_count += 1
                if frame_count % 100 == 0 or (frame_count < 100 and frame_count % 10 == 0):
                    logger.info(f"设备 {device_id} 已处理 {frame_count} 帧, 检测到事件: {event_count}")
                    
                    # 记录性能数据
                    try:
                        db = SessionLocal()
                        perf = DetectionPerformance(
                            performance_id=str(uuid.uuid4()),
                            device_id=device_id,
                            config_id=config.config_id,
                            timestamp=datetime.now(),
                            detection_time=detection_time,
                            preprocessing_time=preprocess_time,
                            postprocessing_time=postprocess_time,
                            frame_width=width,
                            frame_height=height,
                            objects_detected=len(detections)
                        )
                        db.add(perf)
                        db.commit()
                    except Exception as e:
                        logger.error(f"记录性能数据时出错: {e}")
                    finally:
                        db.close()
                
                # 处理检测结果
                if has_detection:
                    current_time = time.time()
                    time_elapsed = current_time - last_save_time
                    
                    # 控制保存频率，避免过多事件
                    if time_elapsed >= min_save_interval:
                        # 处理检测事件
                        self._handle_detection_event(
                            device_id, frame, detections, 
                            timestamp, frame_info, config
                        )
                        event_count += 1
                        last_save_time = current_time
                
                # 避免占用太多CPU
                time.sleep(0.001)
        
        except Exception as e:
            logger.error(f"检测线程发生错误: {e}")
        finally:
            logger.info(f"设备 {device_id} 的检测线程已退出，共处理 {frame_count} 帧，检测到 {event_count} 个事件")
    
    def _handle_detection_event(self, device_id, frame, detections, timestamp, frame_info, config):
        """处理检测事件，保存图像和视频，记录事件"""
        try:
            # 创建存储目录
            device_dir = self.base_storage_path / device_id
            device_dir.mkdir(exist_ok=True)
            
            date_str = datetime.now().strftime("%Y%m%d")
            today_dir = device_dir / date_str
            today_dir.mkdir(exist_ok=True)
            
            # 生成事件ID
            event_id = str(uuid.uuid4())
            event_dir = today_dir / event_id
            event_dir.mkdir(exist_ok=True)
            
            # 保存原始帧
            frame_path = event_dir / "original.jpg"
            cv2.imwrite(str(frame_path), frame)
            
            # 创建带标记的帧
            marked_frame = frame.copy()
            for detection in detections:
                box = detection["box"]
                cls = detection["class"]
                conf = detection["confidence"]
                
                x1, y1, x2, y2 = [int(coord) for coord in box]
                cv2.rectangle(marked_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(marked_frame, f"{cls} {conf:.2f}", (x1, y1 - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # 保存标记的帧
            marked_path = event_dir / "marked.jpg"
            cv2.imwrite(str(marked_path), marked_frame)
            
            # 创建缩略图
            height, width = frame.shape[:2]
            scale = min(100 / width, 100 / height)
            thumbnail_width = int(width * scale)
            thumbnail_height = int(height * scale)
            thumbnail = cv2.resize(marked_frame, (thumbnail_width, thumbnail_height))
            thumbnail_path = event_dir / "thumbnail.jpg"
            cv2.imwrite(str(thumbnail_path), thumbnail)
            
            # 保存视频片段(如果需要)
            video_path = None
            if config.save_mode in [SaveMode.video, SaveMode.both]:
                # 视频功能需要实现，暂时仅保存图像
                pass
            
            # 记录事件到数据库
            db = SessionLocal()
            try:
                for detection in detections:
                    cls = detection["class"]
                    conf = detection["confidence"]
                    box = detection["box"]
                    
                    # 创建事件记录
                    event = DetectionEvent(
                        event_id=str(uuid.uuid4()),
                        device_id=device_id,
                        config_id=config.config_id,
                        timestamp=datetime.now(),
                        event_type=cls,
                        confidence=conf,
                        bounding_box={"xyxy": box},
                        snippet_path=str(event_dir),
                        thumbnail_path=str(thumbnail_path),
                        status=EventStatus.new,
                        created_at=datetime.now()
                    )
                    db.add(event)
                
                db.commit()
                logger.info(f"设备 {device_id} 检测到事件，已保存: {event_id}")
                
            except Exception as e:
                logger.error(f"保存检测事件到数据库时出错: {e}")
                db.rollback()
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"处理检测事件时出错: {e}")

# 创建单例
detection_manager = DetectionManager()

# 辅助函数：启动所有启用的设备检测
async def start_enabled_detections():
    db = SessionLocal()
    try:
        # 获取所有启用的检测配置
        configs = db.query(DetectionConfig).filter(DetectionConfig.enabled == True).all()
        
        started_count = 0
        for config in configs:
            # 检查设备状态
            device = db.query(Device).filter(Device.device_id == config.device_id).first()
            if device and device.status:
                # 启动检测
                success = await detection_manager.start_detection(config.device_id, config.config_id)
                if success:
                    started_count += 1
                    logger.info(f"自动启动设备 {device.device_name} ({device.device_id}) 的检测")
        
        return started_count
    except Exception as e:
        logger.error(f"启动启用的检测时出错: {e}")
        return 0
    finally:
        db.close()

# API函数：连接RTSP检测与流处理
def add_frame_to_detection(device_id: str, frame, frame_info=None):
    """将帧添加到检测队列"""
    if device_id in detection_manager.get_active_devices():
        detection_manager.add_frame(device_id, frame, frame_info)
        return True
    return False 