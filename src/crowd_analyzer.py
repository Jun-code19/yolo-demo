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
import requests # 导入HTTP请求模块
from collections import OrderedDict # 导入有序字典
# 导入数据库模型
from src.database import (
    SessionLocal, Device, 
    DetectionModel, Base, engine, CrowdAnalysisJob, CrowdAnalysisResult
)
# 导入数据推送模块
from src.data_pusher import data_pusher

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
        self.device_get_frame_method = {}
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
                        # 清理设备图片获取方法记录
                        self._cleanup_device_frame_methods()
                except Exception as e:
                    logger.error(f"缓存清理任务出错: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()
    
    def _cleanup_device_frame_methods(self):
        """清理设备图片获取方法记录"""
        try:
            with self.lock:
                if self.device_get_frame_method:
                    old_count = len(self.device_get_frame_method)
                    self.device_get_frame_method.clear()
                    logger.info(f"已清理 {old_count} 个设备的图片获取方法记录")
        except Exception as e:
            logger.error(f"清理设备图片获取方法记录时出错: {e}")
        
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
            
    def add_analysis_job(self, job_id: str, job_name: str, device_ids: List[str], 
                          models_id: str,
                          detect_classes: List[str] = None,
                          confidence_threshold: float = 0.5,
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
            "confidence_threshold": confidence_threshold,
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
            args=[job_id, device_ids, models_id, tags, location_info, detect_classes, confidence_threshold],
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
    
    def _run_analysis(self, job_id: str, device_ids: List[str], 
                     models_id: str, tags: List[str], location_info: Dict, detect_classes: List[str], 
                     confidence_threshold: float = 0.5):
        """
        执行人群分析的具体逻辑
        
        Args:
            job_id: 任务ID
            device_ids: 设备ID列表
            models_id: 检测模型ID
            tags: 数据推送标签
            location_info: 位置信息
        """
        start_time = time.time()
        # logger.info(f"开始执行人群分析: {job_id}")
        
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
            yolo_model = self._get_model(model.file_path, confidence_threshold)  # 使用任务配置的置信度
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
                result = self._analyze_single_camera(device_id, yolo_model, confidence_threshold, detect_classes, tags)  # 使用任务配置的置信度
                if result:
                    # 确保所有结果都可JSON序列化
                    result_serializable = self._ensure_json_serializable(result)
                    analysis_results["camera_counts"].append(result_serializable)
                    total_person_count += result.get("person_count", 0)
            
            # 添加总人数
            analysis_results["total_person_count"] = total_person_count
            
            # 删除preview_image字段
            def remove_preview_image(camera_counts):
                processed_camera_counts = []
                for camera in camera_counts:
                    camera_copy = camera.copy()
                    if "preview_image" in camera_copy:
                        del camera_copy["preview_image"]
                    processed_camera_counts.append(camera_copy)
                return processed_camera_counts
            
            processed_camera_counts = remove_preview_image(analysis_results["camera_counts"])
            # 检查是否需要发送预警
            self._check_warning(job_id, total_person_count, processed_camera_counts)
            
            # 保存结果到数据库
            self._save_analysis_result(job_id, total_person_count, location_info, processed_camera_counts)
            
            # 计算分析耗时
            analysis_time = time.time() - start_time
            
            # 更新任务状态
            with self.lock:
                if job_id in self.analysis_jobs:
                    self.analysis_jobs[job_id]["status"] = "completed"
                    self.analysis_jobs[job_id]["last_result"] = {
                        "timestamp": datetime.now().isoformat(),
                        "total_person_count": total_person_count,
                        "camera_counts": analysis_results["camera_counts"],
                        "analysis_time": analysis_time
                    }
                    # 记录分析时间统计
                    if "time_stats" not in self.analysis_jobs[job_id]:
                        self.analysis_jobs[job_id]["time_stats"] = []
                    self.analysis_jobs[job_id]["time_stats"].append({
                        "timestamp": datetime.now().isoformat(),
                        "analysis_time": analysis_time,
                        "device_count": len(device_ids)
                    })
                    # 保持最近10次的记录
                    if len(self.analysis_jobs[job_id]["time_stats"]) > 10:
                        self.analysis_jobs[job_id]["time_stats"] = self.analysis_jobs[job_id]["time_stats"][-10:]
            
            # 检查是否需要自动调整任务间隔
            self._check_and_adjust_interval(job_id, analysis_time)
            
            # logger.info(f"人群分析完成: {job_id}, 总人数: {total_person_count}, 耗时: {analysis_time:.2f}秒")
            return analysis_results
            
        except Exception as e:
            # 计算分析耗时（即使失败也要记录）
            analysis_time = time.time() - start_time
            
            logger.error(f"人群分析任务异常: {e}")
            # 更新任务状态
            with self.lock:
                if job_id in self.analysis_jobs:
                    self.analysis_jobs[job_id]["status"] = "error"
                    self.analysis_jobs[job_id]["last_error"] = str(e)
                    # 记录失败的时间统计
                    if "time_stats" not in self.analysis_jobs[job_id]:
                        self.analysis_jobs[job_id]["time_stats"] = []
                    self.analysis_jobs[job_id]["time_stats"].append({
                        "timestamp": datetime.now().isoformat(),
                        "analysis_time": analysis_time,
                        "device_count": len(device_ids),
                        "status": "error"
                    })
                    # 保持最近10次的记录
                    if len(self.analysis_jobs[job_id]["time_stats"]) > 10:
                        self.analysis_jobs[job_id]["time_stats"] = self.analysis_jobs[job_id]["time_stats"][-10:]
            
            logger.error(f"人群分析任务失败: {job_id}, 耗时: {analysis_time:.2f}秒")
            return None
    
    def _get_camera_frame(self, device):
        """       
        优先使用摄像机API抓图，失败时回退到OpenCV RTSP拉流
        
        Args:
            device: 设备对象
            
        Returns:
            图像帧，失败则返回None
        """
        device_id = device.device_id
        
        # 检查是否有记录的成功方法
        if device_id in self.device_get_frame_method:
            method = self.device_get_frame_method[device_id]
            if method == 'api':
                # 直接使用API方法
                frame = self._get_frame_via_api(device)
                if frame is not None:
                    return frame
                else:
                    # API失败，清除记录并尝试RTSP
                    del self.device_get_frame_method[device_id]

            elif method == 'rtsp':
                # 直接使用RTSP方法
                frame = self._get_frame_via_rtsp(device)
                if frame is not None:
                    return frame
                else:
                    # RTSP失败，清除记录并尝试API
                    del self.device_get_frame_method[device_id]
        
        # 没有记录或记录的方法失败，按优先级尝试
        # 首先尝试使用摄像机API抓图
        frame = self._get_frame_via_api(device)
        if frame is not None:
            # 记录API方法成功
            self.device_get_frame_method[device_id] = 'api'
            return frame
        
        # API抓图失败，回退到OpenCV RTSP拉流
        frame = self._get_frame_via_rtsp(device)
        if frame is not None:
            # 记录RTSP方法成功
            self.device_get_frame_method[device_id] = 'rtsp'
            return frame
        
        return None
    
    def _get_frame_via_api(self, device):
        """
        通过摄像机API抓图获取图像
        
        Args:
            device: 设备对象
            
        Returns:
            OpenCV图像帧，失败则返回None
        """
        try:
            # 构建设备抓图URL
            if device.device_type.lower() == 'nvr':
                snapshot_url = f"http://{device.ip_address}/cgi-bin/snapshot.cgi?channel={device.channel}&type=0"
            else:
                snapshot_url = f"http://{device.ip_address}/cgi-bin/snapshot.cgi?channel=1&type=0"
            
            # 第一次请求，获取认证信息
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            first_response = requests.get(snapshot_url, headers=headers, timeout=10)

            if first_response.status_code == 200:
                # 如果直接成功，将图片字节数据转换为OpenCV图像
                image_array = np.frombuffer(first_response.content, np.uint8)
                frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
                if frame is not None:
                    # logger.info(f"API抓图成功: {device.device_id}, 图像尺寸: {frame.shape}")
                    return frame
                else:
                    # logger.error(f"API抓图成功但图像解码失败: {device.device_id}")
                    return None
            
            elif first_response.status_code == 401:
                # 需要认证
                auth_header = first_response.headers.get('www-authenticate', '')
                
                if 'Digest' in auth_header:
                    # Digest认证
                    auth_response = self._generate_digest_auth(
                        auth_header, device.username, device.password, 
                        'GET', snapshot_url
                    )
                    
                    # 发送带认证的请求
                    auth_headers = {
                        'Authorization': auth_response,
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                    
                    auth_response_obj = requests.get(snapshot_url, headers=auth_headers, timeout=10)
                    
                    if auth_response_obj.status_code == 200:
                        # 将认证后的图片字节数据转换为OpenCV图像
                        image_array = np.frombuffer(auth_response_obj.content, np.uint8)
                        frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
                        if frame is not None:
                            # logger.info(f"API抓图成功(认证): {device.device_id}, 图像尺寸: {frame.shape}")
                            return frame
                        else:
                            # logger.error(f"API抓图成功(认证)但图像解码失败: {device.device_id}")
                            return None
                    else:
                        # logger.error(f"设备抓图失败: {device.device_id}, {auth_response_obj.status_code}")
                        return None
            
            else:
                # 其他状态码
                # logger.error(f"设备抓图失败: {device.device_id}, {first_response.status_code}")
                return None
             
        except requests.exceptions.Timeout:
            # logger.error(f"请求超时，设备可能离线或网络不通: {device.device_id}")
            return None
        except requests.exceptions.ConnectionError:
            # logger.error(f"连接失败，设备可能离线或网络不通: {device.device_id}")
            return None
        except Exception as e:
            # logger.error(f"设备抓图失败: {device.device_id}, {e}")
            return None
    
    def _generate_digest_auth(self, auth_header: str, username: str, password: str, method: str, uri: str) -> str:
        """
        生成Digest认证响应
        """
        import hashlib
        import re
        
        # 解析认证头
        auth_info = {}
        pattern = r'(\w+)="([^"]*)"'
        matches = re.findall(pattern, auth_header)
        
        for key, value in matches:
            auth_info[key] = value
        
        realm = auth_info.get('realm', '')
        nonce = auth_info.get('nonce', '')
        qop = auth_info.get('qop', '')
        algorithm = auth_info.get('algorithm', 'MD5')
        
        # 生成随机值
        import secrets
        cnonce = secrets.token_hex(8)
        nc = '00000001'
        
        # 计算HA1 = MD5(username:realm:password)
        ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()
        
        # 计算HA2 = MD5(method:uri)
        ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
        
        # 计算response
        if qop:
            response = hashlib.md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}".encode()).hexdigest()
        else:
            response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
        
        # 构建Authorization头
        auth_response = f'Digest username="{username}", realm="{realm}", nonce="{nonce}", uri="{uri}", algorithm={algorithm}, response="{response}"'
        
        if qop:
            auth_response += f', qop={qop}, nc={nc}, cnonce="{cnonce}"'
        
        return auth_response

    def _get_frame_via_rtsp(self, device):
        """
        通过OpenCV RTSP拉流获取图像（回退方案）
        
        Args:
            device: 设备对象
            
        Returns:
            图像帧，失败则返回None
        """
        try:
            # 构建RTSP URL
            if device.device_type == 'nvr':
                stream_type = 1 if device.stream_type == 'sub' else 0
                rtsp_url = f"rtsp://{device.username}:{device.password}@{device.ip_address}:{device.port}/cam/realmonitor?channel={device.channel}&subtype={stream_type}"
            else:
                stream_type = 1 if device.stream_type == 'sub' else 0
                rtsp_url = f"rtsp://{device.username}:{device.password}@{device.ip_address}:{device.port}/cam/realmonitor?channel=1&subtype={stream_type}"
            
            # 连接到摄像机
            cap = cv2.VideoCapture(rtsp_url)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # 兼容性处理：某些OpenCV版本可能不支持CAP_PROP_TIMEOUT
            # try:
            #     cap.set(cv2.CAP_PROP_TIMEOUT, 10000)  # 设置10秒超时
            # except AttributeError:
                # logger.warning(f"当前OpenCV版本不支持CAP_PROP_TIMEOUT，将使用默认超时设置")
            
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
            logger.error(f"RTSP拉流失败: {e}, 设备: {device.device_id}")
            return None
    
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
                    if "job" in job_details:
                        old_job = job_details["job"]
                        self.scheduler.remove_job(job_id)
                        
                        # 创建新的调度任务
                        new_job = self.scheduler.add_job(
                            self._run_analysis,
                            trigger=IntervalTrigger(seconds=new_interval),
                            args=[job_id, job_details["device_ids"], job_details["models_id"], 
                                  job_details["tags"], job_details["location_info"], 
                                  job_details["detect_classes"], job_details["confidence_threshold"]],
                            id=job_id,
                            replace_existing=True
                        )
                        job_details["job"] = new_job
                        
                        logger.warning(f"任务 {job_id} 间隔自动调整: {old_interval}秒 → {new_interval}秒 (分析耗时: {analysis_time:.1f}秒)")
                        
                        # 记录调整历史
                        if "interval_adjustments" not in job_details:
                            job_details["interval_adjustments"] = []
                        job_details["interval_adjustments"].append({
                            "timestamp": datetime.now().isoformat(),
                            "old_interval": old_interval,
                            "new_interval": new_interval,
                            "analysis_time": analysis_time,
                            "reason": "自动调整"
                        })
                        # 保持最近5次的调整记录
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
            
    def _analyze_single_camera(self, device_id: str, yolo_model=None, confidence=0.5, detect_classes: List[str] = None, tags: List[str] = None):   
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
                return None
            
            area_coordinates = device.area_coordinates
            
            # 将归一化坐标转换为像素坐标
            if area_coordinates and area_coordinates.get('points'):               
                area_points = self.normalize_points(area_coordinates.get('points'), frame.shape)
            else:
                area_points = None

            # 检测人员
            person_count, person_boxes = self._detect_persons(frame, yolo_model, confidence, area_points, detect_classes)
            
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

            # 推送分析结果
            try:
                if data_pusher.push_configs and tags:
                    # 确保标签列表可序列化
                    serializable_tags = [str(tag) for tag in tags]

                    event_data={
                        'cameraInfo': device.device_name + ":" + device.ip_address,
                        'deviceId': device_id,
                        'enteredCount': 0,
                        'exitedCount': 0,
                        'stayingCount': person_count,
                        'passedCount': 0,
                        'recordTime': datetime.now().isoformat() + '+08:00', 
                        'event_description': f'区域内人数={person_count}'
                    }

                    data_pusher.push_data(
                        data=event_data,
                        tags=serializable_tags  # 添加固定标签
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
            # device = 'cuda' if torch.cuda.is_available() else 'cpu'
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
                self.add_analysis_job(
                    job_id=job.job_id,
                    job_name=job.job_name,
                    device_ids=job.device_ids,
                    models_id=job.models_id,  # 添加模型ID
                    detect_classes=job.detect_classes,
                    confidence_threshold=job.confidence_threshold or 0.5,
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