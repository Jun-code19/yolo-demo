"""
人群分析模块 - 定时采集多个监控画面进行人数分析
支持多摄像头同步采集，根据预设时间间隔进行分析，并将结果推送至外部平台
用于生成人数分布地图和人流统计
"""

import asyncio
import logging
import threading
import time
import uuid
from datetime import datetime, time as dt_time
import json
import cv2
import numpy as np
from typing import Dict, List, Optional, Union
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from models.database import (
    SessionLocal, DetectionConfig, Device, 
    DetectionModel, DetectionPerformance, Base, engine, CrowdAnalysisJob, CrowdAnalysisResult
)
from src.data_pusher import data_pusher

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CrowdAnalyzer:
    """人群分析类，管理多个摄像机的人数分析流程"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.running = False
        self.analysis_jobs = {}  # 存储所有分析任务 {job_id: job_details}
        self.model_cache = {}  # 缓存已加载的模型
        self.lock = threading.Lock()
        
    def start(self):
        """启动人群分析服务"""
        if not self.running:
            self.running = True
            self.scheduler.start()
            logger.info("人群分析服务已启动")
            
    def stop(self):
        """停止人群分析服务"""
        if self.running:
            self.running = False
            self.scheduler.shutdown()
            logger.info("人群分析服务已停止")
            
    def add_analysis_job(self, job_id: str, job_name: str, device_ids: List[str], 
                          models_id: str,
                          detect_classes: List[str] = None,
                          interval: int = 300, cron_expression: str = None, 
                          tags: List[str] = ["crowd_analysis"],
                          location_info: Dict = None):
        """
        添加人群分析任务
        
        Args:
            job_id: 任务ID
            job_name: 任务名称
            device_ids: 设备ID列表
            model_id: 检测模型ID
            interval: 分析间隔（秒），默认5分钟
            cron_expression: cron表达式，用于更精确的定时控制（优先于interval）
            tags: 标签列表，用于数据推送筛选
            location_info: 位置信息，如 {"name": "一楼大厅", "coordinates": [116.123, 39.456]}
        """
        job_details = {
            "job_id": job_id,
            "job_name": job_name,
            "device_ids": device_ids,
            "models_id": models_id,
            "detect_classes": detect_classes,
            "interval": interval,
            "cron_expression": cron_expression,
            "tags": tags,
            "location_info": location_info or {},
            "created_at": datetime.now(),
            "last_run": None,
            "status": "created"
        }
        
        # 定义任务触发器
        if cron_expression:
            trigger = CronTrigger.from_crontab(cron_expression)
        else:
            trigger = IntervalTrigger(seconds=interval)
        
        # 创建调度任务
        job = self.scheduler.add_job(
            self._run_analysis,
            trigger=trigger,
            args=[job_id, device_ids, models_id, tags, location_info, detect_classes],
            id=job_id,
            replace_existing=True
        )
        
        # 保存任务信息
        with self.lock:
            job_details["job"] = job
            job_details["status"] = "scheduled"
            self.analysis_jobs[job_id] = job_details
            
        logger.info(f"人群分析任务已添加: {job_id}")
        return job_details
    
    def remove_analysis_job(self, job_id: str):
        """移除人群分析任务"""
        with self.lock:
            if job_id in self.analysis_jobs:
                job_details = self.analysis_jobs[job_id]
                if "job" in job_details:
                    self.scheduler.remove_job(job_id)
                del self.analysis_jobs[job_id]
                logger.info(f"人群分析任务已移除: {job_id}")
                return True
            return False
    
    def get_analysis_jobs(self):
        """获取所有人群分析任务"""
        with self.lock:
            # 返回任务列表的复制，排除job对象
            return [{k: v for k, v in job.items() if k != 'job'} 
                   for job in self.analysis_jobs.values()]
    
    def _run_analysis(self, job_id: str, device_ids: List[str], 
                     models_id: str, tags: List[str], location_info: Dict, detect_classes: List[str]):
        """
        执行人群分析的具体逻辑
        
        Args:
            job_id: 任务ID
            device_ids: 设备ID列表
            models_id: 检测模型ID
            tags: 数据推送标签
            location_info: 位置信息
        """
        logger.info(f"开始执行人群分析: {job_id}")
        
        try:
            # 更新任务状态
            with self.lock:
                if job_id in self.analysis_jobs:
                    self.analysis_jobs[job_id]["status"] = "running"
                    self.analysis_jobs[job_id]["last_run"] = datetime.now()
            
            # 获取模型信息
            db = SessionLocal()
            model = db.query(DetectionModel).filter(DetectionModel.models_id == models_id).first()
            db.close()
            
            if not model:
                logger.error(f"未找到模型: {models_id}")
                with self.lock:
                    if job_id in self.analysis_jobs:
                        self.analysis_jobs[job_id]["status"] = "error"
                        self.analysis_jobs[job_id]["last_error"] = f"未找到模型: {models_id}"
                return None
            
            # 加载YOLO模型
            yolo_model = self._get_model(model.file_path, 0.5)  # 使用默认置信度
            if not yolo_model:
                logger.error(f"模型加载失败: {model.file_path}")
                with self.lock:
                    if job_id in self.analysis_jobs:
                        self.analysis_jobs[job_id]["status"] = "error"
                        self.analysis_jobs[job_id]["last_error"] = f"模型加载失败: {model.file_path}"
                return None
            
            # 初始化结果集
            analysis_results = {
                "job_id": job_id,
                "timestamp": datetime.now().isoformat(),
                "location_info": self._ensure_json_serializable(location_info),
                "camera_counts": []
            }
            
            total_person_count = 0
            
            # 遍历所有设备
            for device_id in device_ids:
                result = self._analyze_single_camera(device_id, yolo_model, 0.5, detect_classes)  # 使用默认置信度
                if result:
                    # 确保所有结果都可JSON序列化
                    result_serializable = self._ensure_json_serializable(result)
                    analysis_results["camera_counts"].append(result_serializable)
                    total_person_count += result.get("person_count", 0)
            
            # 添加总人数
            analysis_results["total_person_count"] = total_person_count
            
            # 检查是否需要发送预警
            self._check_warning(job_id, total_person_count, analysis_results)
            
            # 推送分析结果
            if tags:
                # 确保标签列表可序列化
                serializable_tags = [str(tag) for tag in tags] + ["crowd_analysis"]
                data_pusher.push_data(
                    data=analysis_results,
                    tags=serializable_tags  # 添加固定标签
                )
            
            # 保存结果到数据库
            self._save_analysis_result(job_id, total_person_count, location_info, analysis_results["camera_counts"])
            
            # 更新任务状态
            with self.lock:
                if job_id in self.analysis_jobs:
                    self.analysis_jobs[job_id]["status"] = "completed"
                    self.analysis_jobs[job_id]["last_result"] = {
                        "timestamp": datetime.now().isoformat(),
                        "total_person_count": total_person_count,
                        "camera_counts": analysis_results["camera_counts"]
                    }
            
            logger.info(f"人群分析完成: {job_id}, 总人数: {total_person_count}")
            return analysis_results
            
        except Exception as e:
            logger.error(f"人群分析任务异常: {e}")
            # 更新任务状态
            with self.lock:
                if job_id in self.analysis_jobs:
                    self.analysis_jobs[job_id]["status"] = "error"
                    self.analysis_jobs[job_id]["last_error"] = str(e)
            return None
    
    def _get_device_info(self, device_id: str):
        """
        获取设备信息
        
        Args:
            device_id: 设备ID
            
        Returns:
            (device, config, model) 元组，失败则返回None
        """
        try:
            db = SessionLocal()
            
            # 获取设备信息
            device = db.query(Device).filter(Device.device_id == device_id).first()
            if not device:
                logger.error(f"未找到设备: {device_id}")
                return None
            
            # 获取检测配置
            config = db.query(DetectionConfig).filter(DetectionConfig.device_id == device_id).first()
            if not config:
                logger.error(f"未找到检测配置: {device_id}")
                return None
            
            model = db.query(DetectionModel).filter(DetectionModel.model_id == config.model_id).first()
            if not model:
                logger.error(f"未找到模型: {config.model_id}")
                return None
                
            return (device, config, model)
        except Exception as e:
            logger.error(f"获取设备信息失败: {e}")
            return None
        finally:
            db.close()
    
    def _get_camera_frame(self, device):
        """
        从摄像机获取单帧图像
        
        Args:
            device: 设备对象
            
        Returns:
            图像帧，失败则返回None
        """
        try:
            # 构建RTSP URL
            rtsp_url = f"rtsp://{device.username}:{device.password}@{device.ip_address}:{device.port}/cam/realmonitor?channel=1&subtype=0"
            
            # 连接到摄像机
            cap = cv2.VideoCapture(rtsp_url)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if not cap.isOpened():
                logger.error(f"无法连接到摄像机: {device.device_id}")
                return None
           
            # 获取单帧图像
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                logger.error(f"无法获取摄像机画面: {device.device_id}")
                return None
                
            return frame
        except Exception as e:
            logger.error(f"获取摄像机帧失败: {e}")
            return None
    
    def _detect_persons(self, frame, model, confidence, detect_classes: List[str] = None):
        """
        检测图像中的人员
        
        Args:
            frame: 图像帧
            model: YOLO模型
            confidence: 置信度阈值
            detect_classes: 检测类别

        Returns:
            (person_count, person_boxes) 元组
        """
        try:
            # 使用YOLO模型进行检测
            results = model.predict(frame, conf=confidence, verbose=False)[0]
            
            # 统计人数
            person_count = 0
            person_boxes = []
            
            for det in results.boxes.data.cpu().numpy():
                x1, y1, x2, y2, conf, cls = det
                class_id = int(cls)
                if detect_classes and str(class_id) in detect_classes:
                    person_count += 1
                    person_boxes.append({
                        "class": class_id,
                        "class_name": results.names[class_id],
                        "box": [float(x1), float(y1), float(x2), float(y2)],
                        "confidence": float(conf)
                    })
                # if int(cls) == 0:  # person类别通常是0
                #     person_count += 1
                #     person_boxes.append({
                #         "box": [float(x1), float(y1), float(x2), float(y2)],
                #         "confidence": float(conf)
                #     })
                    
            return (person_count, person_boxes)
        except Exception as e:
            logger.error(f"人员检测失败: {e}")
            return (0, [])
            
    def _analyze_single_camera(self, device_id: str, yolo_model=None, confidence=0.5, detect_classes: List[str] = None):   
        """
        分析单个摄像头的画面
        
        Args:
            device_id: 设备ID
            yolo_model: 已加载的YOLO模型实例
            confidence: 置信度阈值
            
        Returns:
            包含分析结果的字典
        """
        try:
            # 获取设备信息
            db = SessionLocal()
            
            # 获取设备信息
            device = db.query(Device).filter(Device.device_id == device_id).first()
            if not device:
                logger.error(f"未找到设备: {device_id}")
                db.close()
                return None
            
            db.close()
            
            # 获取摄像机画面
            frame = self._get_camera_frame(device)
            if frame is None:
                return None
            
            # 如果未提供模型，则尝试使用设备配置的模型（向后兼容）
            if yolo_model is None:
                device_info = self._get_device_info(device_id)
                if not device_info:
                    return None
                    
                device, config, model = device_info
                
                # 加载YOLO模型
                yolo_model = self._get_model(model.model_path, config.confidence)
                if not yolo_model:
                    logger.error(f"模型加载失败: {model.model_path}")
                    return None
                
                confidence = config.confidence
            
            # 检测人员
            person_count, person_boxes = self._detect_persons(frame, yolo_model, confidence, detect_classes)
            
            # 构建结果
            camera_result = {
                "device_id": device_id,
                "device_name": device.device_name,
                "timestamp": datetime.now().isoformat(),
                "person_count": person_count,
                "location": device.location or "",
                "area": device.area or "",
                "person_detections": person_boxes
            }
            
            # 可选：添加预览图（缩小尺寸以减少数据量）
            if frame is not None:
                # 在原始图像上绘制检测框和人数标签
                frame_with_boxes = frame.copy()
                
                # 添加人员检测框
                for detection in person_boxes:
                    box = detection.get("box")
                    conf = detection.get("confidence", 0)
                    if box:
                        x1, y1, x2, y2 = [int(coord) for coord in box]
                        # 绘制矩形框
                        cv2.rectangle(frame_with_boxes, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        # 添加置信度标签
                        conf_text = f"{conf:.2f}"
                        cv2.putText(frame_with_boxes, conf_text, (x1, y1-5), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
                
                # 添加总人数标签
                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.putText(frame_with_boxes, f"People: {person_count}", (10, 30), 
                            font, 1, (0, 0, 255), 2, cv2.LINE_AA)
                
                # 调整图像大小以减少数据量
                preview_frame = cv2.resize(frame_with_boxes, (640, 360))
                
                # 将图像编码为JPEG，然后转换为base64字符串
                import base64
                _, buffer = cv2.imencode('.jpg', preview_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                image_base64 = base64.b64encode(buffer).decode('utf-8')
                camera_result["preview_image"] = image_base64
            
            return camera_result
            
        except Exception as e:
            logger.error(f"分析摄像头 {device_id} 失败: {e}")
            return None
    
    def _get_model(self, model_path: str, confidence: float):
        """
        获取YOLO模型（优先使用缓存）
        
        Args:
            model_path: 模型路径
            confidence: 置信度阈值
            
        Returns:
            YOLO模型实例
        """
        model_key = f"{model_path}_{confidence}"
        
        with self.lock:
            if model_key in self.model_cache:
                return self.model_cache[model_key]
        
        try:
            from ultralytics import YOLO
            import torch
            
            # 加载模型
            model = YOLO(model_path)
            
            # 设置设备
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            model.to(device)
            
            # 缓存模型
            with self.lock:
                self.model_cache[model_key] = model
                
            return model
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return None

    def update_job_status_in_db(self, job_id, status, result=None, error=None):
        """将任务状态更新到数据库"""
        try:
            db = SessionLocal()
            job = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.job_id == job_id).first()
            if job:
                job.last_run = datetime.now()
                
                if status:
                    # 只在运行时内部记录状态，不保存到数据库
                    pass
                    
                if result:
                    job.last_result = result
                    
                if error:
                    job.last_error = error
                    
                db.commit()
        except Exception as e:
            logger.error(f"更新任务状态失败: {e}")
        finally:
            db.close()

    def _check_warning(self, job_id: str, total_person_count: int, analysis_results: dict):
        """检查是否需要发送人数预警"""
        try:
            db = SessionLocal()
            job = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.job_id == job_id).first()
            
            if not job or not job.warning_threshold or job.warning_threshold <= 0:
                return
            
            # 如果人数超过预警阈值
            if total_person_count >= job.warning_threshold:
                # 生成预警消息
                warning_msg = job.warning_message or f"人群密度预警：{job.job_name} 区域人数达到 {total_person_count}人，超过预警阈值({job.warning_threshold}人)"
                
                # 发送预警（可以通过数据推送模块发送到外部系统）
                if job.tags:
                    data_pusher.push_data(
                        data={
                            "warning_type": "crowd_density",
                            "job_id": job_id,
                            "job_name": job.job_name,
                            "threshold": job.warning_threshold,
                            "current_count": total_person_count,
                            "message": warning_msg,
                            "timestamp": datetime.now().isoformat(),
                            "analysis_results": analysis_results
                        },
                        tags=job.tags + ["warning", "crowd_warning"]
                    )
                
                logger.warning(f"人群密度预警: {warning_msg}")
        except Exception as e:
            logger.error(f"处理人数预警时出错: {e}")
        finally:
            db.close()
            
    def generate_heatmap(self, person_detections: List[dict], image_shape: tuple):
        """根据人员检测框生成热力图"""
        import numpy as np
        import cv2
        
        # 创建空白热力图
        heatmap = np.zeros(image_shape[:2], dtype=np.float32)
        
        # 为每个人员检测框添加高斯模糊点
        for detection in person_detections:
            box = detection.get("box")
            if not box:
                continue
            
            x1, y1, x2, y2 = [int(coord) for coord in box]
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            
            # 添加高斯点
            cv2.circle(heatmap, (center_x, center_y), 30, 1.0, -1)
        
        # 应用高斯模糊
        heatmap = cv2.GaussianBlur(heatmap, (51, 51), 0)
        
        # 归一化到0-1范围
        if np.max(heatmap) > 0:
            heatmap = heatmap / np.max(heatmap)
        
        # 转换为彩色热力图
        heatmap_colored = cv2.applyColorMap(np.uint8(heatmap * 255), cv2.COLORMAP_JET)
        
        # 与原图混合
        return heatmap_colored

    def _ensure_json_serializable(self, data):
        """确保数据可以被JSON序列化"""
        if data is None:
            return None
        
        if isinstance(data, (str, int, float, bool)):
            return data
        
        if isinstance(data, bytes):
            # 将二进制数据转换为base64字符串
            import base64
            return base64.b64encode(data).decode('utf-8')
        
        if isinstance(data, datetime):
            # 将datetime转换为ISO格式字符串
            return data.isoformat()
        
        if isinstance(data, list):
            # 递归处理列表的每个元素
            return [self._ensure_json_serializable(item) for item in data]
        
        if isinstance(data, dict):
            # 递归处理字典的每个值
            result = {}
            for key, value in data.items():
                # 确保键是字符串
                string_key = str(key)
                result[string_key] = self._ensure_json_serializable(value)
            return result
        
        # 其他类型转换为字符串
        return str(data)

    def _save_analysis_result(self, job_id, total_person_count, location_info, camera_counts):
        """保存分析结果到数据库"""
        try:
            db = SessionLocal()
            
            # 在保存前移除每个camera_count中的preview_image字段
            processed_camera_counts = []
            for camera in camera_counts:
                camera_copy = camera.copy()
                if "preview_image" in camera_copy:
                    del camera_copy["preview_image"]
                processed_camera_counts.append(camera_copy)
            
            # 创建新的分析结果记录
            result = CrowdAnalysisResult(
                result_id=str(uuid.uuid4()),
                job_id=job_id,
                timestamp=datetime.now(),
                total_person_count=total_person_count,
                location_info=location_info,
                camera_counts=processed_camera_counts
            )
            
            # 保存到数据库
            db.add(result)
            db.commit()
            
            logger.info(f"分析结果已保存到数据库: {job_id}")
        except Exception as e:
            logger.error(f"保存分析结果失败: {e}")
            db.rollback()
        finally:
            db.close()
  
    def load_all_active_jobs(self):
        """加载所有活跃的人群分析任务"""        
        try:
            db = SessionLocal()
            # 加载所有活跃的人群分析任务
            active_jobs = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.is_active == True).all()
            for job in active_jobs:
                self.add_analysis_job(
                    job_id=job.job_id,
                    job_name=job.job_name,
                    device_ids=job.device_ids,
                    models_id=job.models_id,  # 添加模型ID
                    detect_classes=job.detect_classes,
                    interval=job.interval,
                    cron_expression=job.cron_expression,
                    tags=job.tags,
                    location_info=job.location_info
                )
                logger.info(f"已加载人群分析任务: {job.job_name} (ID: {job.job_id})")
        except Exception as e:
            logger.error(f"加载人群分析任务失败: {e}")
        finally:
            db.close()

# 创建全局实例
crowd_analyzer = CrowdAnalyzer() 