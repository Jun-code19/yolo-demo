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

from models.database import (
    SessionLocal, DetectionConfig, DetectionEvent, Device, 
    DetectionModel, DetectionPerformance, SaveMode,
    EventStatus, Base, engine, get_db
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DetectionTask:
    """检测任务类，管理单个摄像机的检测过程"""
    
    def __init__(self, device_id: str, config_id: str, model_path: str, 
                 confidence: float, save_mode: SaveMode, region_of_interest: Optional[List] = None):
        self.device_id = device_id
        self.config_id = config_id
        self.model_path = model_path
        self.confidence = confidence
        self.save_mode = save_mode
        self.region_of_interest = region_of_interest
        self.stop_event = threading.Event()
        self.model = None
        self.cap = None
        self.thread = None
        self.frame_buffer = deque(maxlen=5)  # 存储最近的帧
        self.last_detection_time = time.time()
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.clients = set()  # WebSocket客户端集合，用于实时预览
    
    def load_model(self):
        """加载YOLO模型"""
        try:
            logger.info(f"加载模型: {self.model_path}")
            self.model = YOLO(self.model_path)
            return True
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            return False
    
    def connect_to_camera(self):
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
    
    def run_detection(self):
        """执行检测的主循环"""
        if not self.load_model():
            logger.error(f"无法启动检测任务 {self.config_id}，模型加载失败")
            return
        
        if not self.connect_to_camera():
            logger.error(f"无法启动检测任务 {self.config_id}，摄像机连接失败")
            return
        
        logger.info(f"开始检测任务: {self.config_id} 设备: {self.device_id}")
        
        frame_count = 0
        error_count = 0
        cooldown_period = 10  # 检测事件的冷却时间（秒）
        
        while not self.stop_event.is_set():
            try:
                if not self.connected or error_count > 5:
                    if self.reconnect_attempts < self.max_reconnect_attempts:
                        logger.info(f"尝试重新连接摄像机: {self.device_id}")
                        self.reconnect_attempts += 1
                        if self.connect_to_camera():
                            error_count = 0
                        else:
                            time.sleep(2)  # 等待2秒后重试
                            continue
                    else:
                        logger.error(f"重连摄像机 {self.device_id} 失败，停止检测任务")
                        break
                
                ret, frame = self.cap.read()
                if not ret:
                    error_count += 1
                    logger.warning(f"从摄像机 {self.device_id} 获取帧失败 ({error_count}/5)")
                    time.sleep(0.1)  # 短暂暂停后重试
                    continue
                
                # 将帧添加到缓冲区
                self.frame_buffer.append(frame.copy())
                
                # 每5帧执行一次检测，减少计算负担
                frame_count += 1
                if frame_count % 5 == 0:
                    # 如果设置了感兴趣区域，裁剪帧
                    if self.region_of_interest and isinstance(self.region_of_interest, list) and len(self.region_of_interest) == 4:
                        try:
                            x1, y1, x2, y2 = self.region_of_interest
                            detect_frame = frame[y1:y2, x1:x2]
                        except Exception as e:
                            logger.warning(f"裁剪感兴趣区域失败: {e}，使用完整帧")
                            detect_frame = frame
                    else:
                        detect_frame = frame
                    
                    # 执行检测
                    current_time = time.time()
                    results = self.model(detect_frame, conf=self.confidence, verbose=False)
                    
                    # 处理检测结果
                    detections = []
                    for r in results:
                        boxes = r.boxes
                        for box in boxes:
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            confidence = box.conf.item()
                            class_id = int(box.cls.item())
                            class_name = r.names[class_id]
                            
                            detections.append({
                                "bbox": [x1, y1, x2, y2],
                                "confidence": confidence,
                                "class_id": class_id,
                                "class_name": class_name
                            })
                    
                    # 判断是否需要创建检测事件
                    if detections and (current_time - self.last_detection_time) > cooldown_period:
                        self.last_detection_time = current_time
                        self.save_detection_event(frame, detections)
                    
                    # 向WebSocket客户端推送检测结果
                    self.broadcast_detection_result(frame, detections)
                
                # 防止CPU过载
                time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"检测过程中出错: {e}")
                error_count += 1
                time.sleep(0.1)
        
        # 清理资源
        if self.cap:
            self.cap.release()
        logger.info(f"检测任务已停止: {self.config_id}")
    
    def start(self):
        """启动检测任务线程"""
        if self.thread and self.thread.is_alive():
            logger.info(f"检测任务已在运行: {self.config_id}")
            return
        
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run_detection)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        """停止检测任务"""
        logger.info(f"正在停止检测任务: {self.config_id}")
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
    
    def save_detection_event(self, frame, detections):
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
                event_type="object_detection",
                confidence=max([d["confidence"] for d in detections]) if detections else 0.0,
                bounding_box=detections,
                status=EventStatus.new,
                created_at=current_time
            )
            
            # 根据保存模式保存图像/视频
            save_dir = Path(f"storage/events/{current_time.strftime('%Y-%m-%d')}/{self.device_id}")
            save_dir.mkdir(parents=True, exist_ok=True)
            
            if self.save_mode in [SaveMode.screenshot, SaveMode.both]:
                # 保存截图
                thumbnail_path = save_dir / f"{event_id}.jpg"
                cv2.imwrite(str(thumbnail_path), frame)
                event.thumbnail_path = str(thumbnail_path)
            
            if self.save_mode in [SaveMode.video, SaveMode.both]:
                # 从帧缓冲区创建短视频
                snippet_path = save_dir / f"{event_id}.mp4"
                height, width = frame.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(str(snippet_path), fourcc, 5, (width, height))
                
                for f in self.frame_buffer:
                    out.write(f)
                out.release()
                event.snippet_path = str(snippet_path)
            
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
    
    def broadcast_detection_result(self, frame, detections):
        """向所有WebSocket客户端广播检测结果"""
        if not self.clients:
            return  # 没有客户端连接，跳过
        
        try:
            # 在帧上绘制检测框
            annotated_frame = frame.copy()
            for det in detections:
                x1, y1, x2, y2 = map(int, det["bbox"])
                class_name = det["class_name"]
                confidence = det["confidence"]
                
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(annotated_frame, f"{class_name} {confidence:.2f}", 
                           (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # 将帧转换为JPEG格式
            _, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
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
            
            # 异步广播消息
            asyncio.create_task(self._broadcast_message(message))
            
        except Exception as e:
            logger.error(f"广播检测结果失败: {e}")
    
    async def _broadcast_message(self, message):
        """异步广播消息到所有WebSocket客户端"""
        disconnected_clients = set()
        
        for client in self.clients:
            try:
                await client.send_json(message)
            except Exception:
                disconnected_clients.add(client)
        
        # 移除断开连接的客户端
        self.clients -= disconnected_clients
    
    def add_client(self, websocket):
        """添加WebSocket客户端到广播列表"""
        self.clients.add(websocket)
        logger.info(f"客户端已连接到检测任务 {self.config_id}, 当前客户端数: {len(self.clients)}")
    
    def remove_client(self, websocket):
        """从广播列表中移除WebSocket客户端"""
        if websocket in self.clients:
            self.clients.remove(websocket)
            logger.info(f"客户端已断开连接，检测任务 {self.config_id}, 当前客户端数: {len(self.clients)}")


class DetectionServer:
    """检测服务器类，管理所有检测任务"""
    
    def __init__(self):
        self.tasks = {}  # 存储所有检测任务，格式: {config_id: DetectionTask}
        self.models_cache = {}  # 缓存已加载的模型，格式: {model_path: model}
    
    async def start_detection(self, config_id: str, db: Session):
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
            
            # 创建检测任务
            task = DetectionTask(
                device_id=config.device_id,
                config_id=config_id,
                model_path=model.file_path,
                confidence=config.sensitivity,
                save_mode=config.save_mode,
                region_of_interest=None  # 暂时不使用区域参数，避免类型不匹配问题
            )
            
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
    
    async def stop_detection(self, config_id: str, db: Session):
        """停止特定配置的检测任务"""
        if config_id not in self.tasks:
            logger.warning(f"检测任务不存在: {config_id}")
            return {"status": "error", "message": "检测任务不存在"}
        
        try:
            # 停止任务
            self.tasks[config_id].stop()
            
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
    
    async def start_all_enabled(self, db: Session):
        """启动所有已启用的检测任务"""
        logger.info("正在启动所有已启用的检测任务...")
        enabled_configs = db.query(DetectionConfig).filter(DetectionConfig.enabled.is_(True)).all()
        
        for config in enabled_configs:
            await self.start_detection(config.config_id, db)
        
        logger.info(f"已启动 {len(enabled_configs)} 个检测任务")
    
    async def handle_preview(self, websocket: WebSocket, config_id: str):
        """处理检测预览WebSocket连接"""
        await websocket.accept()
        
        if config_id not in self.tasks:
            await websocket.send_json({
                "status": "error", 
                "message": "请求的检测任务不存在或未启动"
            })
            await websocket.close()
            return
        
        # 添加WebSocket客户端到检测任务
        self.tasks[config_id].add_client(websocket)
        
        try:
            # 保持连接，直到客户端断开
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            # 客户端断开连接时移除
            self.tasks[config_id].remove_client(websocket)
        except Exception as e:
            logger.error(f"WebSocket连接错误: {e}")
            # 确保客户端被移除
            self.tasks[config_id].remove_client(websocket)


# 创建检测服务器实例
detection_server = DetectionServer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用程序生命周期管理"""
    logger.info("检测服务器启动中...")
    
    # 创建数据库表（如果不存在）
    Base.metadata.create_all(bind=engine)
    
    # 启动已启用的检测任务
    db = SessionLocal()
    await detection_server.start_all_enabled(db)
    db.close()
    
    yield
    
    # 服务关闭时停止所有检测任务
    logger.info("检测服务器关闭中...")
    for config_id, task in list(detection_server.tasks.items()):
        task.stop()


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
@app.post("/api/detection/{config_id}/start")
async def start_detection_api(config_id: str, db: Session = Depends(get_db)):
    """启动检测任务API"""
    return await detection_server.start_detection(config_id, db)


@app.post("/api/detection/{config_id}/stop")
async def stop_detection_api(config_id: str, db: Session = Depends(get_db)):
    """停止检测任务API"""
    return await detection_server.stop_detection(config_id, db)


@app.get("/api/detection/status")
async def get_detection_status():
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
async def detection_preview_websocket(websocket: WebSocket, config_id: str):
    """检测预览WebSocket端点"""
    await detection_server.handle_preview(websocket, config_id)


if __name__ == "__main__":
    import uvicorn
    logger.info("正在启动检测服务器...")
    uvicorn.run(app, host="0.0.0.0", port=8003) 