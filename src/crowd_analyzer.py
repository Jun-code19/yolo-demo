"""
人群分析模块 - 定时采集多个监控画面进行人数分析
支持多摄像头同步采集，根据预设时间间隔进行分析，并将结果推送至外部平台
用于生成人数分布地图和人流统计
"""
from pathlib import Path # 导入路径模块
import asyncio # 导入异步I/O模块
import logging # 导入日志模块
import threading # 导入线程模块
import time # 导入时间模块
import uuid # 导入UUID模块
from datetime import datetime, time as dt_time # 导入日期时间模块
import json # 导入JSON模块
import cv2 # 导入OpenCV模块
import numpy as np # 导入NumPy模块
from typing import Dict, List, Optional, Union # 导入类型提示
from sqlalchemy.orm import Session # 导入数据库会话
from apscheduler.schedulers.background import BackgroundScheduler # 导入调度器
from apscheduler.triggers.interval import IntervalTrigger # 导入间隔触发器
from apscheduler.triggers.cron import CronTrigger # 导入Cron触发器
import os # 导入操作系统模块
import psutil # 导入系统监控模块
from collections import OrderedDict # 导入有序字典
# 导入数据库模型
from src.database import (
    SessionLocal, Device, 
    DetectionModel, Base, engine, CrowdAnalysisJob, CrowdAnalysisResult
)
# 导入数据推送模块
from src.data_pusher import data_pusher
from src.device_roi import get_device_roi_pixels
from src.frame_acquisition import frame_acquisition, DEFAULT_GROUP_SETTINGS
from src.detection_runtime import extract_runtime_config, is_within_active_period
from src.crowd_job_utils import resolve_crowd_job_devices

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ModelCache:
    """模型缓存管理类，实现LRU策略和内存监控"""
    
    def __init__(self, max_size: int = 10, max_memory_mb: int = 2048):
        """
        初始化模型缓存
        
        Args:
            max_size: 最大缓存模型数量
            max_memory_mb: 最大内存使用量（MB）
        """
        self.max_size = max_size
        self.max_memory_mb = max_memory_mb
        self.cache = OrderedDict()  # 使用有序字典实现LRU
        self.lock = threading.RLock()
        self.model_info = {}  # 存储模型信息：{model_key: {size_mb, last_used, load_time}}
        
    def get(self, model_key: str):
        """获取模型，如果存在则移动到末尾（最近使用）"""
        with self.lock:
            if model_key in self.cache:
                # 移动到末尾（最近使用）
                self.cache.move_to_end(model_key)
                # 更新最后使用时间
                if model_key in self.model_info:
                    self.model_info[model_key]['last_used'] = time.time()
                return self.cache[model_key]
            return None
    
    def put(self, model_key: str, model, model_size_mb: float = None):
        """添加模型到缓存"""
        with self.lock:
            # 如果模型已存在，先移除
            if model_key in self.cache:
                self.cache.pop(model_key)
                if model_key in self.model_info:
                    del self.model_info[model_key]
            
            # 检查内存使用量
            if self._check_memory_limit(model_size_mb):
                # 移除最久未使用的模型
                self._evict_oldest()
            
            # 添加新模型
            self.cache[model_key] = model
            self.model_info[model_key] = {
                'size_mb': model_size_mb or 0,
                'last_used': time.time(),
                'load_time': time.time()
            }
            
            logger.info(f"模型已缓存: {model_key}, 当前缓存大小: {len(self.cache)}/{self.max_size}")
    
    def _check_memory_limit(self, new_model_size_mb: float = None) -> bool:
        """检查是否超过内存限制"""
        if new_model_size_mb is None:
            new_model_size_mb = 0
            
        # 计算当前内存使用量
        current_memory = sum(info['size_mb'] for info in self.model_info.values())
        total_memory = current_memory + new_model_size_mb
        
        # 检查模型数量限制
        if len(self.cache) >= self.max_size:
            return True
            
        # 检查内存限制
        if total_memory > self.max_memory_mb:
            return True
            
        return False
    
    def _evict_oldest(self):
        """移除最久未使用的模型"""
        if not self.cache:
            return
            
        # 移除第一个（最久未使用）
        oldest_key = next(iter(self.cache))
        removed_model = self.cache.pop(oldest_key)
        
        if oldest_key in self.model_info:
            del self.model_info[oldest_key]
        
        # 尝试释放GPU内存
        try:
            if hasattr(removed_model, 'model'):
                del removed_model.model
            del removed_model
            import gc
            gc.collect()
            # logger.info(f"已移除最久未使用的模型: {oldest_key}")
        except Exception as e:
            logger.warning(f"释放模型内存时出错: {e}")
    
    def clear(self):
        """清空所有缓存"""
        with self.lock:
            for model in self.cache.values():
                try:
                    if hasattr(model, 'model'):
                        del model.model
                    del model
                except:
                    pass
            
            self.cache.clear()
            self.model_info.clear()
            
            import gc
            gc.collect()
            # logger.info("模型缓存已清空")
    
    def get_stats(self) -> Dict:
        """获取缓存统计信息"""
        with self.lock:
            total_size = sum(info['size_mb'] for info in self.model_info.values())
            return {
                'cache_size': len(self.cache),
                'max_size': self.max_size,
                'total_memory_mb': total_size,
                'max_memory_mb': self.max_memory_mb,
                'models': list(self.model_info.keys())
            }
    
    def cleanup(self):
        """清理过期或未使用的模型"""
        with self.lock:
            current_time = time.time()
            expired_keys = []
            
            for key, info in self.model_info.items():
                # 如果模型超过1小时未使用，标记为过期
                if current_time - info['last_used'] > 3600:  # 1小时
                    expired_keys.append(key)
            
            # 移除过期的模型
            for key in expired_keys:
                if key in self.cache:
                    removed_model = self.cache.pop(key)
                    try:
                        if hasattr(removed_model, 'model'):
                            del removed_model.model
                        del removed_model
                    except:
                        pass
                
                if key in self.model_info:
                    del self.model_info[key]
            
            if expired_keys:
                import gc
                gc.collect()
                # logger.info(f"已清理 {len(expired_keys)} 个过期模型")

class CrowdAnalyzer:
    """人群分析类，管理多个摄像机的人数分析流程"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        # 配置APScheduler日志
        logging.getLogger('apscheduler').setLevel(logging.WARNING)
        self.running = False
        self.analysis_jobs = {}  # 存储所有分析任务 {job_id: job_details}
        self.model_cache = ModelCache(max_size=10, max_memory_mb=2048)  # 使用新的模型缓存类
        self.lock = threading.Lock()
        self.usedevice = 'cpu'
        # 启动缓存清理定时任务
        self._start_cache_cleanup()
        
    def _start_cache_cleanup(self):
        """启动缓存清理定时任务"""
        def cleanup_task():
            while self.running:
                try:
                    time.sleep(3600)  # 每小时清理一次
                    if self.running:
                        self.model_cache.cleanup()
                except Exception as e:
                    logger.error(f"缓存清理任务出错: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()
        
    def start(self):
        """启动人群分析服务"""
        if not self.running:
            self.running = True
            self.scheduler.start()
            
    def stop(self):
        """停止人群分析服务"""
        if self.running:
            self.running = False
            self.model_cache.clear()  # 清空模型缓存
            self.scheduler.shutdown()
            
    def add_analysis_job(self, job_id: str):
        """将数据库中的人群分析任务加入调度器"""
        db = SessionLocal()
        try:
            job = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.job_id == job_id).first()
            if not job:
                logger.error(f"未找到人群分析任务: {job_id}")
                return None

            if job.cron_expression:
                trigger = CronTrigger.from_crontab(job.cron_expression)
            else:
                trigger = IntervalTrigger(seconds=job.interval or 300)

            self.scheduler.add_job(
                self._run_analysis,
                trigger=trigger,
                args=[job_id],
                id=job_id,
                replace_existing=True,
            )

            job_details = {
                "job_id": job_id,
                "job_name": job.job_name,
                "interval": job.interval or 300,
                "cron_expression": job.cron_expression,
                "created_at": job.created_at,
                "last_run": None,
                "status": "scheduled",
            }

            with self.lock:
                self.analysis_jobs[job_id] = job_details

            logger.info(f"人群分析任务已添加: {job_id}")
            return job_details
        finally:
            db.close()
    
    def remove_analysis_job(self, job_id: str):
        """移除人群分析任务（停止调度；已在跑的一轮会在下一台设备前退出）"""
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass

        with self.lock:
            if job_id in self.analysis_jobs:
                self.analysis_jobs[job_id]["status"] = "paused"
                del self.analysis_jobs[job_id]
                logger.info(f"人群分析任务已移除: {job_id}")
                return True
        logger.info(f"人群分析任务已从调度器移除: {job_id}")
        return True
    
    def get_analysis_jobs(self):
        """获取所有人群分析任务"""
        with self.lock:
            # 返回任务列表的复制，排除job对象
            return [{k: v for k, v in job.items() if k != 'job'} 
                   for job in self.analysis_jobs.values()]
    
    def get_cache_stats(self):
        """获取模型缓存统计信息"""
        return self.model_cache.get_stats()
    
    def clear_model_cache(self):
        """清空模型缓存"""
        self.model_cache.clear()
        logger.info("模型缓存已手动清空")
    
    def reload_model(self, model_path: str, confidence: float):
        """重新加载指定模型"""
        model_key = f"{model_path}_{confidence}"
        
        # 从缓存中移除旧模型
        with self.lock:
            # 使用缓存类的内部方法移除模型
            if model_key in self.model_cache.cache:
                old_model = self.model_cache.cache.pop(model_key)
                if model_key in self.model_cache.model_info:
                    del self.model_cache.model_info[model_key]
                
                # 尝试释放GPU内存
                try:
                    if hasattr(old_model, 'model'):
                        del old_model.model
                    del old_model
                    import gc
                    gc.collect()
                except Exception as e:
                    logger.warning(f"释放旧模型内存时出错: {e}")
        
        # 重新加载模型
        logger.info(f"重新加载模型: {model_path}")
        return self._get_model(model_path, confidence)
    
    def _is_job_stopped(self, db: Session, job_id: str) -> bool:
        """判断任务是否应停止（DB 已停用或已从运行时队列移除）"""
        job = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.job_id == job_id).first()
        if not job or not job.is_active:
            return True
        with self.lock:
            return job_id not in self.analysis_jobs

    def _run_analysis(self, job_id: str, manual: bool = False):
        """执行人群分析：从数据库加载配置，校验生效时段后逐台取帧检测"""
        start_time = time.time()
        db = SessionLocal()
        try:
            job = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.job_id == job_id).first()
            if not job:
                logger.error(f"未找到人群分析任务: {job_id}")
                return None

            if not manual and self._is_job_stopped(db, job_id):
                logger.info(f"人群分析任务未启用或已停止，跳过: {job_id}")
                return None

            runtime = extract_runtime_config(job.schedule_config)
            if not is_within_active_period(datetime.now(), runtime):
                with self.lock:
                    if job_id in self.analysis_jobs:
                        self.analysis_jobs[job_id]["status"] = "scheduled"
                return None

            device_ids = resolve_crowd_job_devices(db, job)
            if not device_ids:
                error_msg = "没有可用的监控设备"
                with self.lock:
                    if job_id in self.analysis_jobs:
                        self.analysis_jobs[job_id]["status"] = "error"
                        self.analysis_jobs[job_id]["last_error"] = error_msg
                self.update_job_status_in_db(job_id, None, error=error_msg)
                return None

            models_id = job.models_id
            tags = job.tags or ["crowd_analysis"]
            location_info = job.location_info or {}
            detect_classes = job.detect_classes or []
            confidence_threshold = job.confidence_threshold or 0.5
            group_settings = job.group_settings or DEFAULT_GROUP_SETTINGS
            device_interval = float(group_settings.get("device_interval_sec") or 0)

            with self.lock:
                if job_id in self.analysis_jobs:
                    self.analysis_jobs[job_id]["status"] = "running"
                    self.analysis_jobs[job_id]["last_run"] = datetime.now()

            model = db.query(DetectionModel).filter(DetectionModel.models_id == models_id).first()
            if not model:
                logger.error(f"未找到模型: {models_id}")
                with self.lock:
                    if job_id in self.analysis_jobs:
                        self.analysis_jobs[job_id]["status"] = "error"
                        self.analysis_jobs[job_id]["last_error"] = f"未找到模型: {models_id}"
                return None

            yolo_model = self._get_model(model.file_path, confidence_threshold, model.is_gpu)
            if not yolo_model:
                logger.error(f"模型加载失败: {model.file_path}")
                with self.lock:
                    if job_id in self.analysis_jobs:
                        self.analysis_jobs[job_id]["status"] = "error"
                        self.analysis_jobs[job_id]["last_error"] = f"模型加载失败: {model.file_path}"
                return None

            analysis_results = {
                "job_id": job_id,
                "timestamp": datetime.now().isoformat(),
                "location_info": self._ensure_json_serializable(location_info),
                "camera_counts": [],
            }

            total_person_count = 0
            for index, device_id in enumerate(device_ids):
                if not manual and self._is_job_stopped(db, job_id):
                    logger.info(f"人群分析任务已停止，中断本轮: {job_id}")
                    with self.lock:
                        if job_id in self.analysis_jobs:
                            self.analysis_jobs[job_id]["status"] = "paused"
                    return None

                if index > 0 and device_interval > 0:
                    time.sleep(device_interval)
                result = self._analyze_single_camera(
                    device_id,
                    yolo_model,
                    confidence_threshold,
                    detect_classes,
                    tags,
                    group_settings,
                )
                if result:
                    result_serializable = self._ensure_json_serializable(result)
                    analysis_results["camera_counts"].append(result_serializable)
                    total_person_count += result.get("person_count", 0)

            analysis_results["total_person_count"] = total_person_count

            push_mode = self._get_push_mode(group_settings)
            if push_mode == "bundled" and analysis_results["camera_counts"]:
                try:
                    bundled_payload = self._build_bundled_push_payload(
                        job_id=job_id,
                        job_name=job.job_name,
                        location_info=location_info,
                        camera_counts=analysis_results["camera_counts"],
                        total_person_count=total_person_count,
                    )
                    self._push_crowd_data(tags, bundled_payload)
                except Exception as e:
                    logger.error(f"打包推送人群分析结果时出错: {e}")

            def remove_preview_image(camera_counts):
                processed_camera_counts = []
                for camera in camera_counts:
                    camera_copy = camera.copy()
                    if "preview_image" in camera_copy:
                        del camera_copy["preview_image"]
                    processed_camera_counts.append(camera_copy)
                return processed_camera_counts

            processed_camera_counts = remove_preview_image(analysis_results["camera_counts"])
            self._check_warning(job_id, total_person_count, processed_camera_counts)
            self._save_analysis_result(job_id, total_person_count, location_info, processed_camera_counts)

            analysis_time = time.time() - start_time
            with self.lock:
                if job_id in self.analysis_jobs:
                    self.analysis_jobs[job_id]["status"] = "completed"
                    self.analysis_jobs[job_id]["last_result"] = {
                        "timestamp": datetime.now().isoformat(),
                        "total_person_count": total_person_count,
                        "camera_counts": analysis_results["camera_counts"],
                        "analysis_time": analysis_time,
                    }
                    if "time_stats" not in self.analysis_jobs[job_id]:
                        self.analysis_jobs[job_id]["time_stats"] = []
                    self.analysis_jobs[job_id]["time_stats"].append({
                        "timestamp": datetime.now().isoformat(),
                        "analysis_time": analysis_time,
                        "device_count": len(device_ids),
                    })
                    if len(self.analysis_jobs[job_id]["time_stats"]) > 10:
                        self.analysis_jobs[job_id]["time_stats"] = self.analysis_jobs[job_id]["time_stats"][-10:]

            self._check_and_adjust_interval(job_id, analysis_time)
            return analysis_results
        except Exception as e:
            analysis_time = time.time() - start_time
            logger.error(f"人群分析任务异常: {e}")
            with self.lock:
                if job_id in self.analysis_jobs:
                    self.analysis_jobs[job_id]["status"] = "error"
                    self.analysis_jobs[job_id]["last_error"] = str(e)
                    if "time_stats" not in self.analysis_jobs[job_id]:
                        self.analysis_jobs[job_id]["time_stats"] = []
                    self.analysis_jobs[job_id]["time_stats"].append({
                        "timestamp": datetime.now().isoformat(),
                        "analysis_time": analysis_time,
                        "device_count": 0,
                        "status": "error",
                    })
                    if len(self.analysis_jobs[job_id]["time_stats"]) > 10:
                        self.analysis_jobs[job_id]["time_stats"] = self.analysis_jobs[job_id]["time_stats"][-10:]
            logger.error(f"人群分析任务失败: {job_id}, 耗时: {analysis_time:.2f}秒")
            return None
        finally:
            db.close()
    
    def _check_and_adjust_interval(self, job_id: str, analysis_time: float):
        """
        检查分析时间并自动调整任务间隔
        
        Args:
            job_id: 任务ID
            analysis_time: 分析耗时（秒）
        """
        try:
            with self.lock:
                if job_id not in self.analysis_jobs:
                    return
                
                job_details = self.analysis_jobs[job_id]
                current_interval = job_details.get("interval", 300)  # 默认5分钟
                
                # 计算建议的最小间隔（分析时间的3倍，确保有足够缓冲）
                suggested_interval = max(int(analysis_time + 10), 10)  # 最少10秒
                
                # 如果当前间隔明显不足，自动调整
                if current_interval < suggested_interval:
                    # 计算新的间隔（向上取整到最近的10秒倍数）
                    new_interval = ((suggested_interval + 9) // 10) * 10
                    
                    # 更新任务间隔
                    old_interval = current_interval
                    job_details["interval"] = new_interval
                    job_details["auto_adjusted"] = True
                    job_details["adjustment_reason"] = f"分析耗时{analysis_time:.1f}秒，原间隔{old_interval}秒不足，自动调整为{new_interval}秒"
                    
                    # 重新调度任务
                    self.scheduler.remove_job(job_id)
                    new_job = self.scheduler.add_job(
                        self._run_analysis,
                        trigger=IntervalTrigger(seconds=new_interval),
                        args=[job_id],
                        id=job_id,
                        replace_existing=True,
                    )
                    job_details["job"] = new_job

                    logger.warning(
                        f"任务 {job_id} 间隔自动调整: {old_interval}秒 → {new_interval}秒 (分析耗时: {analysis_time:.1f}秒)"
                    )

                    if "interval_adjustments" not in job_details:
                        job_details["interval_adjustments"] = []
                    job_details["interval_adjustments"].append({
                        "timestamp": datetime.now().isoformat(),
                        "old_interval": old_interval,
                        "new_interval": new_interval,
                        "analysis_time": analysis_time,
                        "reason": "自动调整",
                    })
                    if len(job_details["interval_adjustments"]) > 5:
                        job_details["interval_adjustments"] = job_details["interval_adjustments"][-5:]
                
                # 如果分析时间明显短于间隔，可以考虑缩短间隔（可选功能）
                elif current_interval > suggested_interval * 2 and analysis_time < current_interval * 0.1:
                    # 只有当分析时间远小于间隔时才考虑缩短
                    potential_interval = max(int(current_interval * 0.8), suggested_interval)
                    if potential_interval < current_interval:
                        logger.info(f"任务 {job_id} 分析效率较高，可考虑缩短间隔: {current_interval}秒 → {potential_interval}秒")
                        
        except Exception as e:
            logger.error(f"自动调整任务间隔时出错: {e}")
    
    def _detect_persons(self, frame, model, confidence, area_points, detect_classes: List[str] = None):
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
            # results = model.predict(frame, conf=confidence, verbose=False)[0]
            results = model(frame, conf=confidence,iou=0.45,max_det=300,device=self.usedevice)           

            # 统计人数
            person_count = 0
            person_boxes = []
            
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    confidence = box.conf.item()
                    class_id = int(box.cls.item())
                    class_name = r.names[class_id]
                    
                    if str(class_id) in detect_classes:
                        person_boxes.append({
                            "bbox": [x1, y1, x2, y2],
                            "confidence": confidence,
                            "class_id": class_id,
                            "class_name": class_name
                        })

            if area_points:
                for bbox in person_boxes:
                    center = self._get_center(bbox['bbox'])
                    if self._point_in_polygon(center, area_points):
                        person_count += 1
            else:
                for bbox in person_boxes:   
                    person_count += 1

            return (person_count, person_boxes)
        except Exception as e:
            logger.error(f"人员检测失败: {e}")
            return (0, [])
            
    def _get_push_mode(self, group_settings: Optional[Dict] = None) -> str:
        mode = (group_settings or DEFAULT_GROUP_SETTINGS).get("push_mode", "per_device")
        return mode if mode in ("per_device", "bundled") else "per_device"

    def _push_crowd_data(self, tags: Optional[List[str]], data: dict):
        if not data_pusher.push_configs or not tags:
            return
        serializable_tags = [str(tag) for tag in tags]
        data_pusher.push_data(data=data, tags=serializable_tags)

    def _build_device_push_payload(self, device, device_id: str, person_count: int) -> dict:
        return {
            "cameraInfo": f"{device.device_name}:{device.ip_address}",
            "deviceId": device_id,
            "enteredCount": 0,
            "exitedCount": 0,
            "stayingCount": person_count,
            "passedCount": 0,
            "recordTime": datetime.now().isoformat() + "+08:00",
            "event_description": f"区域内人数={person_count}",
        }

    def _build_bundled_push_payload(
        self,
        job_id: str,
        job_name: str,
        location_info: dict,
        camera_counts: list,
        total_person_count: int,
    ) -> dict:
        devices = []
        for cam in camera_counts:
            person_count = cam.get("person_count", 0)
            device_name = cam.get("device_name", "")
            ip_address = cam.get("ip_address", "")
            device_id = cam.get("device_id", "")
            timestamp = cam.get("timestamp") or datetime.now().isoformat()
            record_time = timestamp if "+08:00" in timestamp else f"{timestamp}+08:00"
            devices.append({
                "cameraInfo": f"{device_name}:{ip_address}",
                "deviceId": device_id,
                "enteredCount": 0,
                "exitedCount": 0,
                "stayingCount": person_count,
                "passedCount": 0,
                "recordTime": record_time,
                "event_description": f"区域内人数={person_count}",
            })
        return {
            "jobId": job_id,
            "jobName": job_name,
            "recordTime": datetime.now().isoformat() + "+08:00",
            "totalStayingCount": total_person_count,
            "deviceCount": len(devices),
            "locationInfo": self._ensure_json_serializable(location_info),
            "devices": devices,
        }

    def _analyze_single_camera(
        self,
        device_id: str,
        yolo_model=None,
        confidence=0.5,
        detect_classes: List[str] = None,
        tags: List[str] = None,
        group_settings: Optional[Dict] = None,
    ):
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
            
            settings = group_settings or DEFAULT_GROUP_SETTINGS
            stream_type = getattr(device, "stream_type", None) or "main"
            frame = frame_acquisition.get_frame(device, settings=settings, stream_type=stream_type)
            if frame is None:
                return None
            
            # 如果未提供模型，则尝试使用设备配置的模型（向后兼容）
            if yolo_model is None:               
                return None
            
            area_coordinates = device.area_coordinates
            area_points = get_device_roi_pixels(area_coordinates, frame.shape)

            # 检测人员
            person_count, person_boxes = self._detect_persons(frame, yolo_model, confidence, area_points, detect_classes)
            
            # 构建结果
            camera_result = {
                "device_id": device_id,
                "device_name": device.device_name,
                "ip_address": device.ip_address or "",
                "timestamp": datetime.now().isoformat(),
                "person_count": person_count,
                "location": device.location or "",
                "area": device.area or "",
                "person_detections": person_boxes
            }

            # 逐设备推送
            try:
                if self._get_push_mode(group_settings) == "per_device":
                    self._push_crowd_data(
                        tags,
                        self._build_device_push_payload(device, device_id, person_count),
                    )
            except Exception as e:
                logger.error(f"推送分析结果时出错: {e}")
            
            # 可选：添加预览图（缩小尺寸以减少数据量）
            if frame is not None:
                # 在原始图像上绘制检测框和人数标签
                frame_with_boxes = frame.copy()
                
                self.draw_roi(frame_with_boxes, area_points)

                # 添加人员检测框
                for detection in person_boxes:
                    box = detection.get("bbox")
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
                            font, 0.5, (0, 0, 255), 1, cv2.LINE_AA)

                # 调整图像大小以减少数据量
                preview_frame = cv2.resize(frame_with_boxes, (640, 360))
                
                # 将图像编码为JPEG，然后转换为base64字符串
                import base64
                _, buffer = cv2.imencode('.jpg', preview_frame, [cv2.IMWRITE_JPEG_QUALITY, 100])
                image_base64 = base64.b64encode(buffer).decode('utf-8')
                camera_result["preview_image"] = image_base64
            
            return camera_result
            
        except Exception as e:
            logger.error(f"分析摄像头 {device_id} 失败: {e}")
            return None
    
    def _get_model(self, model_path: str, confidence: float, is_gpu: bool):
        """
        获取YOLO模型（优先使用缓存）
        
        Args:
            model_path: 模型路径
            confidence: 置信度阈值
            
        Returns:
            YOLO模型实例
        """
        model_key = f"{model_path}_{confidence}"
        
        # 从缓存获取模型
        cached_model = self.model_cache.get(model_key)
        if cached_model:
            return cached_model
        
        try:
            from ultralytics import YOLO
            import torch
            
            # 加载模型
            model = YOLO(model_path)
            
            # 设置设备
            # device = 'cuda' if torch.cuda.is_available() and is_gpu else 'cpu'
            device = 'cpu'
            model.to(torch.device(device))

            if device == 'cuda' and hasattr(model, 'model'): 
                # 使用半精度浮点数以提高性能
                if hasattr(model.model, 'dtype'):
                    model.model.half()

            self.usedevice = device

            # 估算模型大小（MB）
            try:
                # 尝试获取模型文件大小
                if os.path.exists(model_path):
                    model_size_mb = os.path.getsize(model_path) / (1024 * 1024)
                else:
                    # 如果文件不存在，使用默认大小
                    model_size_mb = 100  # 默认100MB
            except:
                model_size_mb = 100
            
            # 缓存模型
            self.model_cache.put(model_key, model, model_size_mb)
                
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

            # 更新分析任务最新一次的记录
            result1 = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.job_id == job_id).first()
            if result1:
                result1.last_result = { "total_person_count": total_person_count }
                result1.last_run = datetime.now()
                db.commit()
            
            # 创建新的分析结果记录
            result = CrowdAnalysisResult(
                result_id=str(uuid.uuid4()),
                job_id=job_id,
                timestamp=datetime.now(),
                total_person_count=total_person_count,
                location_info=location_info,
                camera_counts=camera_counts
            )
            
            # 保存到数据库
            db.add(result)
            db.commit()
            
            # logger.info(f"分析结果已保存到数据库: {job_id}")
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
                self.add_analysis_job(job.job_id)
                logger.info(f"已加载人群分析任务: {job.job_name} (ID: {job.job_id})")
        except Exception as e:
            logger.error(f"加载人群分析任务失败: {e}")
        finally:
            db.close()

    def draw_roi(self, frame, area_points, line_color=(0,255,0), fill_color=(0,0,0,0), thickness=2, line_type=cv2.LINE_AA): # 绘制线段/区域 ROI（支持line/area类型）
        """
        绘制线段/区域 ROI（支持line/area类型）
        :param frame: 输入图像
        :param area_points: ROI坐标列表
        :param line_color: 线段/边框颜色 (BGR格式)
        :param fill_color: 填充颜色 (BGR+Alpha格式)
        :param thickness: 线宽
        :param line_type: 线型（默认抗锯齿）
        """
        if not area_points: 
            return
        # 转换为整数坐标
        roi_array = np.array(area_points, np.int32)      
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

    def _point_in_polygon(self, point, polygon):
        """判断点是否在多边形内（Ray casting算法）"""
        if not polygon or len(polygon) < 3:
            return False
            
        x, y = point
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def _get_center(self, bbox):
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    def normalize_points(self, points, frame_shape): #归一化坐标转换
        """归一化坐标转换"""
        h,w = frame_shape[:2]
        return [(int(p['x']*w), int(p['y']*h)) for p in points]
# 创建全局实例
crowd_analyzer = CrowdAnalyzer() 