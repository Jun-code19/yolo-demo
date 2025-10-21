import asyncio # 导入异步I/O模块
import numpy as np # 导入NumPy模块
import logging # 导入日志模块
import os # 导入操作系统模块
from datetime import datetime, timedelta # 导入日期时间模块
from pathlib import Path # 导入路径模块

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends # 导入FastAPI相关模块
from fastapi.middleware.cors import CORSMiddleware # 导入CORS中间件
from contextlib import asynccontextmanager # 导入异步上下文管理器
from ultralytics import YOLO # 导入YOLO模型
import torch # 导入torch模块
from sqlalchemy.orm import Session # 导入数据库会话

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from pytz import utc

# 导入数据推送模块
from src.data_pusher import data_pusher
# 导入人群分析模块
from src.crowd_analyzer import crowd_analyzer
# 导入数据库模块
from src.database import (
    SessionLocal, DetectionConfig, DetectionEvent, Device, 
    DetectionModel, ExternalEvent,SmartEvent, Base, engine, get_db, ListenerType
)

from src.run_detection_task import DetectionTask

# 导入认证模块
from api.auth import get_current_user, User
# 导入日志模块
from api.logger import log_action, log_detection_action
# 导入事件订阅管理器
from src.smartSchemer import smart_schemer
# 导入设备监控模块
from src.device_monitor import device_monitor

# 导入数据监听器模块
from src.data_listener_manager import data_listener_manager
from src.listeners.tcp_listener import TCPListener
from src.listeners.mqtt_listener import MQTTListener
from src.listeners.http_listener import HTTPListener

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化 APScheduler
scheduler = BackgroundScheduler(timezone=utc)
# 配置APScheduler日志
logging.getLogger('apscheduler').setLevel(logging.WARNING)
scheduler.add_jobstore(MemoryJobStore(), 'default')
scheduler.start()

# 注册监听器类型
def register_listener_types():
    """注册所有支持的监听器类型"""
    try:
        data_listener_manager.register_listener_type(ListenerType.tcp, TCPListener)
        data_listener_manager.register_listener_type(ListenerType.http, HTTPListener)
        
        # MQTT监听器需要额外检查依赖
        try:
            data_listener_manager.register_listener_type(ListenerType.mqtt, MQTTListener)
        except ImportError:
            logger.warning("MQTT监听器不可用，请安装 paho-mqtt 库")
    except Exception as e:
        logger.error(f"注册监听器类型失败: {e}")

# 检测服务器类，管理所有检测任务
class DetectionServer:
    # 初始化检测服务器
    def __init__(self):
        self.tasks = {}  # 存储所有检测任务，格式: {config_id: DetectionTask}
        self.models_cache = {}  # 缓存已加载的模型，格式: {model_path: model}
        self.scheduled_jobs = {}  # 存储所有定时任务，格式: {config_id: job_id}
        self.cleanup_task = None  # 全局清理任务
        self.max_concurrent_tasks = 50 # 最大并发任务数
        # 资源监控相关属性
        self.total_cpu_usage = 0
        self.total_memory_usage = 0
        self.active_task_count = 0
    
    # 启动特定配置的检测任务
    async def start_detection(self, config_id: str, db: Session, user_id: str = None):
        """启动特定配置的检测任务"""
        # 检查任务是否已在运行
        if config_id in self.tasks and self.tasks[config_id].thread and self.tasks[config_id].thread.is_alive():
            return {"status": "success", "message": "检测任务已在运行"}
        
        # 检查系统资源是否允许启动新任务
        if not self._should_start_new_task():
            return {"status": "error", "message": "系统资源不足，无法启动新任务"}
        
        try:
            # 获取检测配置
            config = db.query(DetectionConfig).filter(DetectionConfig.config_id == config_id).first()
            if not config:
                logger.error(f"未找到检测配置: {config_id}")
                # 记录失败日志
                log_detection_action(config_id, "unknown", "start", "failed", "未找到检测配置", user_id)
                return {"status": "error", "message": "未找到检测配置"}
            
            # 获取模型信息
            model = db.query(DetectionModel).filter(DetectionModel.models_id == config.models_id).first()
            if not model:
                logger.error(f"未找到模型: {config.models_id}")
                # 记录失败日志
                log_detection_action(config_id, config.device_id, "start", "failed", f"未找到模型: {config.models_id}", user_id)
                return {"status": "error", "message": "未找到模型"}
            
            # 检查频率
            if config.frequency.value == "scheduled":
                # 对于定时检测，只设置定时任务，不立即启动检测
                result = await self.schedule_detection(config, db)
                
                # 将配置标记为已启用（即使没有立即启动）
                config.enabled = True
                config.updated_at = datetime.now()
                db.commit()
                
                # 记录成功日志
                log_detection_action(config_id, config.device_id, "schedule", "success", "设置定时检测任务成功", user_id)
                
                return result
            elif config.frequency.value == "manual":
                # 对于手动触发，不自动启动任务
                logger.info(f"配置为手动触发模式，不自动启动: {config_id}")
                return {"status": "success", "message": "配置为手动触发模式，请手动启动检测"}
            
            # 实时检测直接启动任务
            await self._create_and_start_task(config, model, db)
            # 记录成功日志
            log_detection_action(config_id, config.device_id, "start", "success", "启动实时检测任务成功", user_id)
            return {"status": "success", "message": "检测任务已启动"}
            
        except Exception as e:
            logger.error(f"启动检测任务失败: {str(e)}")
            # 记录失败日志
            device_id = config.device_id if 'config' in locals() and hasattr(config, 'device_id') else "unknown"
            log_detection_action(config_id, device_id, "start", "failed", f"启动检测任务失败: {str(e)}", user_id)
            return {"status": "error", "message": f"启动检测任务失败: {str(e)}"}
    
    # 停止特定配置的检测任务
    async def stop_detection(self, config_id: str, db: Session, remove_scheduled_jobs=True, user_id: str = None):
        """停止特定配置的检测任务"""
        # 获取设备ID
        device_id = "unknown"
        try:
            config = db.query(DetectionConfig).filter(DetectionConfig.config_id == config_id).first()
            if config:
                device_id = config.device_id
        except Exception:
            pass
        
        # 停止定时任务（如果需要）
        if remove_scheduled_jobs and config_id in self.scheduled_jobs:
            for job_id in self.scheduled_jobs[config_id]:
                try:
                    scheduler.remove_job(job_id)
                except Exception as e:
                    logger.error(f"移除任务失败 {job_id}: {e}")
            del self.scheduled_jobs[config_id]
            log_detection_action(config_id, device_id, "unschedule", "success", "已移除定时检测任务", user_id)
        
        # 停止检测任务
        # if config_id not in self.tasks:
        #     logger.warning(f"检测任务不存在: {config_id}")
            # return {"status": "error", "message": "检测任务不存在"}
        
        try:
            # 停止任务
            if config_id in self.tasks:
                await self.tasks[config_id].stop()
            
            # 更新数据库中的任务状态
            if remove_scheduled_jobs:
                config = db.query(DetectionConfig).filter(DetectionConfig.config_id == config_id).first()
                if config:
                    config.enabled = False
                    config.updated_at = datetime.now()
                    db.commit()
            
            # 移除任务
            if config_id in self.tasks:
                del self.tasks[config_id]
            
            # 记录日志
            log_detection_action(config_id, device_id, "stop", "success", "已停止检测任务", user_id)
            
            logger.info(f"检测任务已停止: {config_id}")
            return {"status": "success", "message": "检测任务已停止"}
            
        except Exception as e:
            logger.error(f"停止检测任务失败: {e}")
            # 记录失败日志
            log_detection_action(config_id, device_id, "stop", "failed", f"停止检测任务失败: {str(e)}", user_id)
            db.rollback()
            return {"status": "error", "message": f"停止检测任务失败: {str(e)}"}
    
    # 启动所有已启用的检测任务
    async def start_all_enabled(self, db: Session):
        """启动所有已启用的检测任务"""
        enabled_configs = db.query(DetectionConfig).filter(DetectionConfig.enabled.is_(True)).all()
        
        started_count = 0
        scheduled_count = 0
        
        for config in enabled_configs:
            try:
                if config.frequency.value == "scheduled":
                    # 对于定时检测，只设置定时任务
                    result = await self.schedule_detection(config, db)
                    if result.get("status") == "success":
                        scheduled_count += 1
                elif config.frequency.value == "realtime":
                    # 实时检测直接启动
                    result = await self.start_detection(config.config_id, db)
                    if result.get("status") == "success":
                        started_count += 1
                # 手动触发的任务不自动启动
            except Exception as e:
                logger.error(f"启动任务 {config.config_id} 失败: {str(e)}")
        
        logger.info(f"已启动 {started_count} 个实时检测任务，设置 {scheduled_count} 个定时检测任务")
    
    # 处理检测预览WebSocket连接
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
                logger.info(f"WebSocket客户端已从检测任务移除: {config_id}")

    # 创建并启动检测任务
    async def _create_and_start_task(self, config: DetectionConfig, model: DetectionModel, db: Session, reset_enabled=True):
        """创建并启动检测任务（内部方法）"""
        config_id = config.config_id
        device_id = config.device_id
        
        # 获取设备信息
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if not device:
            logger.error(f"未找到设备: {device_id}")
            raise ValueError("未找到设备")
        
        # 检查模型文件是否存在
        model_path = model.file_path
        abs_model_path = os.path.abspath(model_path)
        
        if not os.path.exists(abs_model_path):
            # 尝试在models目录中查找
            base_name = os.path.basename(model_path)
            alternative_path = os.path.join("models", base_name)
            alt_abs_path = os.path.abspath(alternative_path)
            
            if os.path.exists(alt_abs_path):
                model_path = alternative_path
            else:
                raise FileNotFoundError(f"模型文件不存在: {os.path.basename(model_path)}")
        
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

            except Exception as e:
                logger.error(f"预加载模型到缓存失败: {e}")
                # 失败但不中断流程，让任务自己尝试加载
        else:
            logger.info(f"使用缓存的模型: {model_path}")
        
        # 创建检测任务
        task = DetectionTask(
            device_id=config.device_id,
            device_name=device.device_name,
            device_ip=device.ip_address,
            config_id=config_id,
            model_path=model_path,  # 使用可能已更新的模型路径
            confidence=config.sensitivity,  
            models_type=model.models_type,
            is_gpu=model.is_gpu,
            target_class=config.target_classes,
            save_mode=config.save_mode,
            area_coordinates=config.area_coordinates
        )
        
        # 如果模型已缓存，直接设置
        if model_path in self.models_cache:

            task.model = self.models_cache[model_path]
            # 设置其他必要属性
            task.class_names = task.model.names
            device = 'cuda' if torch.cuda.is_available() and model.is_gpu else 'cpu'
            task.device = torch.device(device)
            if device == 'cuda' and hasattr(task.model, 'model'):
                if hasattr(task.model.model, 'dtype'):
                    task.model.model.half()

            logger.info(f"使用缓存模型设置任务: {config_id},硬件设备: {device}, 加载模型: {hasattr(task.model, 'model')}")
        
        # 设置事件循环
        task.loop = asyncio.get_event_loop()
        
        # 启动任务
        task.start()
        
        # 保存任务
        self.tasks[config_id] = task
        
        # 更新数据库中的任务状态
        if reset_enabled:
            config.enabled = True
            config.updated_at = datetime.now()
            db.commit()
        
        return task
    
    def _check_system_resources(self):
        """检查系统资源使用情况"""
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            
            self.total_cpu_usage = cpu_percent
            self.total_memory_usage = memory_percent
            self.active_task_count = len([t for t in self.tasks.values() if t.thread and t.thread.is_alive()])
            
            # 记录资源使用情况
            if self.active_task_count > 0:
                logger.info(f"系统资源状态 - CPU: {cpu_percent:.1f}%, 内存: {memory_percent:.1f}%, 活跃任务: {self.active_task_count}")
            
            return cpu_percent, memory_percent
            
        except ImportError:
            return 0, 0
        except Exception as e:
            logger.error(f"检查系统资源失败: {e}")
            return 0, 0
    
    def _should_start_new_task(self):
        """判断是否应该启动新任务"""
        cpu_percent, memory_percent = self._check_system_resources()
        
        # 资源限制条件
        if cpu_percent > 85:
            logger.warning(f"CPU使用率过高({cpu_percent:.1f}%)，暂停启动新任务")
            return False
            
        if memory_percent > 90:
            logger.warning(f"内存使用率过高({memory_percent:.1f}%)，暂停启动新任务")
            return False
            
        if self.active_task_count >= self.max_concurrent_tasks:
            logger.warning(f"已达到最大并发任务数({self.max_concurrent_tasks})，暂停启动新任务")
            return False
            
        return True
    
    # 设置定时检测任务
    async def schedule_detection(self, config: DetectionConfig, db: Session):
        """设置定时检测任务"""
        config_id = config.config_id
        
        # 如果已有定时任务，先移除
        if config_id in self.scheduled_jobs:
            for job_id in self.scheduled_jobs[config_id]:
                try:
                    scheduler.remove_job(job_id)
                except Exception as e:
                    logger.error(f"移除任务失败 {job_id}: {e}")
            del self.scheduled_jobs[config_id]
        
        # 检查是否有定时配置
        if not hasattr(config, 'schedule_config') or not config.schedule_config:
            logger.error(f"定时检测配置不存在: {config_id}")
            return {"status": "error", "message": "定时检测配置不存在"}
        
        try:
            # 解析定时配置
            schedule_config = config.schedule_config
            job_ids = []
            
            # 设置执行时长（分钟）
            duration_minutes = schedule_config.get('duration', 10)
            
            # 简单模式
            if schedule_config.get('mode', 'simple') == 'simple':
                time_str = schedule_config.get('time', '')
                days = schedule_config.get('days', [])
                
                if not time_str or not days:
                    logger.error(f"定时配置无效: {config_id}")
                    return {"status": "error", "message": "定时配置无效"}
                
                # 提取小时和分钟
                hour, minute = map(int, time_str.split(':'))
                
                # 创建定时任务
                job_id = f"scheduled_detection_{config_id}_simple"
                
                # 添加任务到调度器
                # 这里通过 cron 表达式设置，星期几的格式为 0-6 对应周日到周六
                days_str = ','.join(days)
                job = scheduler.add_job(
                    self.run_scheduled_detection_wrapper,
                    CronTrigger(hour=hour, minute=minute, day_of_week=days_str),
                    args=[config_id, duration_minutes],
                    id=job_id,
                    replace_existing=True
                )
                
                job_ids.append(job_id)
                logger.info(f"定时检测任务已设置: {config_id}, 时间: {hour}:{minute}, 日期: {days_str}")
            
            # 高级模式
            else:
                # 获取时间类型
                time_type = schedule_config.get('timeType', 'points')
                date_type = schedule_config.get('dateType', 'weekday')
                
                # 获取执行控制参数
                max_executions = schedule_config.get('maxExecutions', -1)
                idle_timeout = schedule_config.get('idleTimeout', 0)
                
                # 时间点模式
                if time_type == 'points':
                    time_points = schedule_config.get('timePoints', [])
                    if not time_points:
                        logger.error(f"未提供时间点: {config_id}")
                        return {"status": "error", "message": "未提供时间点"}
                    
                    # 添加每个时间点的任务
                    for i, time_str in enumerate(time_points):
                        if not time_str:
                            continue
                            
                        # 提取小时和分钟
                        hour, minute = map(int, time_str.split(':'))
                        
                        # 创建 cron 表达式
                        cron_kwargs = {'hour': hour, 'minute': minute}
                        
                        # 添加日期条件
                        if date_type == 'weekday':
                            weekdays = schedule_config.get('weekdays', [])
                            if weekdays:
                                cron_kwargs['day_of_week'] = ','.join(weekdays)
                        elif date_type == 'monthday':
                            monthdays = schedule_config.get('monthdays', [])
                            if monthdays:
                                cron_kwargs['day'] = ','.join(map(str, monthdays))
                        elif date_type == 'specific':
                            # 特定日期使用不同的方式处理（后面实现）
                            pass
                        
                        # 创建任务 ID
                        job_id = f"scheduled_detection_{config_id}_points_{i}"
                        
                        if date_type != 'specific':
                            # 添加定时任务
                            job = scheduler.add_job(
                                self.run_scheduled_detection_wrapper,
                                CronTrigger(**cron_kwargs),
                                args=[config_id, duration_minutes, max_executions, idle_timeout],
                                id=job_id,
                                replace_existing=True
                            )
                            job_ids.append(job_id)
                            logger.info(f"时间点定时任务已设置: {config_id}, {cron_kwargs}")
                        else:
                            # 处理特定日期
                            specific_dates = schedule_config.get('specificDates', [])
                            for date_str in specific_dates:
                                try:
                                    # 解析日期
                                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                                    # 设置时间
                                    run_date = date_obj.replace(hour=hour, minute=minute)
                                    # 如果日期已过，跳过
                                    if run_date < datetime.now():
                                        continue
                                    # 创建任务 ID
                                    date_job_id = f"{job_id}_{date_str}"
                                    # 添加定时任务
                                    job = scheduler.add_job(
                                        self.run_scheduled_detection_wrapper,
                                        'date',
                                        run_date=run_date,
                                        args=[config_id, duration_minutes, max_executions, idle_timeout],
                                        id=date_job_id,
                                        replace_existing=True
                                    )
                                    job_ids.append(date_job_id)
                                    logger.info(f"特定日期定时任务已设置: {config_id}, {run_date}")
                                except Exception as e:
                                    logger.error(f"特定日期任务设置失败: {date_str}, {e}")
                
                # 时间范围模式
                elif time_type == 'range':
                    start_time = schedule_config.get('startTime', '')
                    end_time = schedule_config.get('endTime', '')
                    interval = schedule_config.get('interval', 5)
                    
                    if not start_time or not end_time:
                        logger.error(f"未提供有效的时间范围: {config_id}")
                        return {"status": "error", "message": "未提供有效的时间范围"}
                    
                    # 解析开始和结束时间
                    start_hour, start_minute = map(int, start_time.split(':'))
                    end_hour, end_minute = map(int, end_time.split(':'))
                    
                    # 如果是跨天时间范围，处理时更复杂，这里假设不跨天
                    if start_hour > end_hour or (start_hour == end_hour and start_minute > end_minute):
                        logger.warning(f"开始时间晚于结束时间，可能是跨天时间段: {config_id}")
                        
                    # 计算间隔总分钟数
                    start_mins = start_hour * 60 + start_minute
                    end_mins = end_hour * 60 + end_minute
                    if end_mins <= start_mins:  # 处理跨天情况
                        end_mins += 24 * 60
                    
                    # 计算每个时间点
                    current_mins = start_mins
                    time_points = []
                    while current_mins < end_mins:
                        hour = (current_mins // 60) % 24
                        minute = current_mins % 60
                        time_points.append((hour, minute))
                        current_mins += interval
                    
                    # 创建每个时间点的任务
                    for i, (hour, minute) in enumerate(time_points):
                        # 创建 cron 表达式
                        cron_kwargs = {'hour': hour, 'minute': minute}
                        
                        # 添加日期条件
                        if date_type == 'weekday':
                            weekdays = schedule_config.get('weekdays', [])
                            if weekdays:
                                cron_kwargs['day_of_week'] = ','.join(weekdays)
                        elif date_type == 'monthday':
                            monthdays = schedule_config.get('monthdays', [])
                            if monthdays:
                                cron_kwargs['day'] = ','.join(map(str, monthdays))
                        
                        # 创建任务 ID
                        job_id = f"scheduled_detection_{config_id}_range_{i}"
                        
                        if date_type != 'specific':
                            # 添加定时任务
                            job = scheduler.add_job(
                                self.run_scheduled_detection_wrapper,
                                CronTrigger(**cron_kwargs),
                                args=[config_id, duration_minutes, max_executions, idle_timeout],
                                id=job_id,
                                replace_existing=True
                            )
                            job_ids.append(job_id)
                            logger.info(f"时间范围定时任务已设置: {config_id}, {hour}:{minute}")
                        else:
                            # 处理特定日期
                            specific_dates = schedule_config.get('specificDates', [])
                            for date_str in specific_dates:
                                try:
                                    # 解析日期
                                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                                    # 设置时间
                                    run_date = date_obj.replace(hour=hour, minute=minute)
                                    # 如果日期已过，跳过
                                    if run_date < datetime.now():
                                        continue
                                    # 创建任务 ID
                                    date_job_id = f"{job_id}_{date_str}"
                                    # 添加定时任务
                                    job = scheduler.add_job(
                                        self.run_scheduled_detection_wrapper,
                                        'date',
                                        run_date=run_date,
                                        args=[config_id, duration_minutes, max_executions, idle_timeout],
                                        id=date_job_id,
                                        replace_existing=True
                                    )
                                    job_ids.append(date_job_id)
                                    logger.info(f"特定日期时间范围任务已设置: {config_id}, {run_date}")
                                except Exception as e:
                                    logger.error(f"特定日期任务设置失败: {date_str}, {e}")
                
            # 记录定时任务
            self.scheduled_jobs[config_id] = job_ids
            
            return {"status": "success", "message": f"定时检测任务已设置: {len(job_ids)}个时间点"}
        
        except Exception as e:
            logger.error(f"设置定时检测任务失败: {str(e)}")
            return {"status": "error", "message": f"设置定时检测任务失败: {str(e)}"}
    
    # 首先添加同步包装器函数
    def run_scheduled_detection_wrapper(self, config_id, duration_minutes, max_executions=-1, idle_timeout=0):
        """调度器可调用的同步包装函数，用于执行异步的_run_scheduled_detection方法"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._run_scheduled_detection(config_id, duration_minutes, max_executions, idle_timeout))
        finally:
            loop.close()
   
    # 执行定时检测任务
    async def _run_scheduled_detection(self, config_id: str, duration_minutes: int, max_executions=-1, idle_timeout=0):
        """执行定时检测任务"""
        logger.info(f"开始执行定时检测任务: {config_id}")
        
        # 创建数据库会话
        db = SessionLocal()
        try:
            # 获取检测配置
            config = db.query(DetectionConfig).filter(DetectionConfig.config_id == config_id).first()
            if not config:
                logger.error(f"未找到检测配置: {config_id}")
                log_detection_action(config_id, "unknown", "auto_start", "failed", "未找到检测配置")
                return
            
            # 获取模型信息
            model = db.query(DetectionModel).filter(DetectionModel.models_id == config.models_id).first()
            if not model:
                logger.error(f"未找到模型: {config.models_id}")
                log_detection_action(config_id, config.device_id, "auto_start", "failed", f"未找到模型: {config.models_id}")
                return
            
            # 创建并启动检测任务
            await self._create_and_start_task(config, model, db, reset_enabled=False)
            # 记录自动启动日志
            log_detection_action(config_id, config.device_id, "auto_start", "success", f"定时任务自动启动检测: 持续{duration_minutes}分钟")
            
            # 任务执行一段时间后自动停止（例如duration_minutes分钟）
            await asyncio.sleep(duration_minutes * 60)
            
            # 停止任务，但不清除定时任务
            if config_id in self.tasks:
                await self.stop_detection(config_id, db, remove_scheduled_jobs=False)
                # 记录自动停止日志
                log_detection_action(config_id, config.device_id, "auto_stop", "success", f"定时任务自动停止，运行了{duration_minutes}分钟")
                logger.info(f"定时检测任务已自动停止: {config_id}")
        
        except Exception as e:
            logger.error(f"执行定时检测任务失败: {str(e)}")
            # 记录错误日志
            device_id = config.device_id if 'config' in locals() and hasattr(config, 'device_id') else "unknown"
            log_detection_action(config_id, device_id, "auto_start", "failed", f"执行定时检测任务失败: {str(e)}")
        finally:
            db.close()

    async def start_global_cleanup_task(self):#启动全局清理任务
        """启动全局清理任务"""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._global_cleanup_worker())
            
            # 计算下次清理时间并显示
            now = datetime.now()
            next_cleanup = now.replace(hour=2, minute=0, second=0, microsecond=0)
            if now >= next_cleanup:
                next_cleanup += timedelta(days=1)
    
    async def _global_cleanup_worker(self):#全局清理工作协程，每天凌晨2点执行一次
        """全局清理工作协程，每天凌晨2点执行一次"""
        while True:
            try:
                # 计算到下一个凌晨2点的等待时间
                now = datetime.now()
                
                # 设置今天凌晨2点的时间
                target_time = now.replace(hour=2, minute=0, second=0, microsecond=0)
                
                # 如果当前时间已经过了今天的凌晨2点，则设置为明天凌晨2点
                if now >= target_time:
                    target_time += timedelta(days=1)
                
                # 计算等待时间（秒）
                wait_seconds = (target_time - now).total_seconds()
                
                logger.info(f"全局清理任务已调度，将在 {target_time.strftime('%Y-%m-%d %H:%M:%S')} 执行下次清理")
                
                # 等待到目标时间
                await asyncio.sleep(wait_seconds)
                
                # 执行清理任务
                await self._cleanup_all_expired_events()
                logger.info(f"全局清理任务执行完成,当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"全局清理任务错误: {e}")
                # 出错后等待1小时再重试
                await asyncio.sleep(3600)
    
    async def _cleanup_all_expired_events(self):#清理所有配置的过期事件
        """清理所有配置的过期事件"""
        start_time = datetime.now()
        try:
            logger.info("开始执行全局清理任务...")
            
            # 1. 清理检测事件
            await self._cleanup_detection_events()
            
            # 2. 清理外部数据事件
            await self._cleanup_external_events()

            # 3. 清理智能事件
            await self._cleanup_smart_events()
            
            # 4. 清理空的日期目录
            try:
                await self._cleanup_empty_directories()
            except Exception as e:
                logger.warning(f"清理空目录失败: {e}")
            
            # 计算执行时间
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"全局清理任务执行完成 - 总执行时间: {execution_time:.2f}秒")           
            
        except Exception as e:
            logger.error(f"全局清理任务失败: {e}")
    
    async def _cleanup_detection_events(self):
        """清理检测事件"""
        db = SessionLocal()
        try:
            current_time = datetime.now()
            
            # 获取所有检测配置
            configs = db.query(DetectionConfig).all()
            
            total_deleted_events = 0
            total_deleted_files = 0
            processed_configs = 0
            failed_configs = 0
            
            logger.info(f"开始清理检测事件，共有 {len(configs)} 个配置需要处理")
            
            for config in configs:
                try:
                    # 获取最大存储天数，如果为0则设置为30天
                    max_storage_days = config.max_storage_days if config.max_storage_days > 0 else 30
                    
                    # 计算过期时间点
                    expire_time = current_time - timedelta(days=max_storage_days)
                    
                    # 查询要删除的事件
                    events_to_delete = db.query(DetectionEvent).filter(
                        DetectionEvent.config_id == config.config_id,
                        DetectionEvent.created_at < expire_time
                    ).all()
                    
                    if not events_to_delete:
                        continue  # 没有过期事件，跳过
                    
                    # 删除关联的文件
                    deleted_files_count = 0
                    for event in events_to_delete:
                        # 删除缩略图文件
                        if event.thumbnail_path and Path(event.thumbnail_path).exists():
                            try:
                                Path(event.thumbnail_path).unlink()
                                deleted_files_count += 1
                            except Exception as e:
                                logger.warning(f"删除缩略图文件失败: {event.thumbnail_path}, 错误: {e}")
                        
                        # 删除视频片段文件
                        if hasattr(event, 'snippet_path') and event.snippet_path and Path(event.snippet_path).exists():
                            try:
                                Path(event.snippet_path).unlink()
                                deleted_files_count += 1
                            except Exception as e:
                                logger.warning(f"删除视频文件失败: {event.snippet_path}, 错误: {e}")
                    
                    # 删除数据库记录
                    deleted_events_count = db.query(DetectionEvent).filter(
                        DetectionEvent.config_id == config.config_id,
                        DetectionEvent.created_at < expire_time
                    ).delete()
                    
                    if deleted_events_count > 0:
                        total_deleted_events += deleted_events_count
                        total_deleted_files += deleted_files_count
                        processed_configs += 1
                        logger.info(f"配置 {config.config_id} (设备: {config.device_id}) 清理了 {deleted_events_count} 条过期事件 (>{max_storage_days}天), {deleted_files_count} 个文件")
                        
                except Exception as e:
                    failed_configs += 1
                    logger.error(f"清理配置 {config.config_id} 的过期事件失败: {e}")
                    continue
            
            # 提交所有删除操作
            if total_deleted_events > 0:
                db.commit()
            
            # 输出清理统计
            log_action(db, 'admin', 'cleanup_detection_events', 'system', f"检测事件清理完成 - 处理配置 {processed_configs}/{len(configs)} 个, 失败 {failed_configs} 个")
            logger.info(f"检测事件清理完成 - 处理配置 {processed_configs}/{len(configs)} 个, 失败 {failed_configs} 个")
            logger.info(f"检测事件删除统计: {total_deleted_events} 条记录, {total_deleted_files} 个文件")
            
        except Exception as e:
            logger.error(f"清理检测事件失败: {e}")
            if 'db' in locals():
                db.rollback()
        finally:
            if 'db' in locals():
                db.close()
    
    async def _cleanup_empty_directories(self):#清理空的存储目录
        """清理空的存储目录"""
        storage_path = Path("storage/events")
        if not storage_path.exists():
            return
        
        deleted_dirs = 0
        try:
            # 遍历所有日期目录
            for date_dir in storage_path.iterdir():
                if date_dir.is_dir():
                    # 检查设备目录
                    for device_dir in date_dir.iterdir():
                        if device_dir.is_dir() and not any(device_dir.iterdir()):
                            # 删除空的设备目录
                            device_dir.rmdir()
                            deleted_dirs += 1
                    
                    # 如果日期目录也空了，删除它
                    if not any(date_dir.iterdir()):
                        date_dir.rmdir()
                        deleted_dirs += 1
            
            if deleted_dirs > 0:
                logger.info(f"清理了 {deleted_dirs} 个空目录")
                
        except Exception as e:
            logger.warning(f"清理空目录时出错: {e}")
    
    async def _cleanup_external_events(self):#清理所有外部的数据事件
        """清理所有外部的数据事件"""
        try:
            db = SessionLocal()
            current_time = datetime.now()
            
            # 外部事件保留100天
            expire_time = current_time - timedelta(days=100)
            
            # 查询要删除的外部事件（用于删除关联的文件）
            events_to_delete = db.query(ExternalEvent).filter(
                ExternalEvent.created_at < expire_time
            ).all()
            
            if not events_to_delete:
                logger.info("没有找到过期的外部数据事件")
                return
            
            deleted_files_count = 0
            deleted_events_count = 0
            
            logger.info(f"开始清理外部数据事件，共有 {len(events_to_delete)} 条过期事件需要处理")
            log_action(db, 'admin', 'cleanup_external_events', 'system', f"开始清理外部数据事件，共有 {len(events_to_delete)} 条过期事件需要处理")
            # 删除关联的图片文件
            for event in events_to_delete:
                try:
                    image_paths = []
                    
                    # 从normalized_data中查找图片路径
                    if event.normalized_data and isinstance(event.normalized_data, dict):
                        # 检查processed_images字段
                        processed_images = event.normalized_data.get('processed_images', {})
                        if isinstance(processed_images, dict):
                            # 遍历processed_images中的所有字段（如pic_data、spic_data等）
                            for field_name, image_data in processed_images.items():
                                if isinstance(image_data, dict):
                                    # 检查original_path
                                    if 'original_path' in image_data and image_data['original_path']:
                                        image_paths.append(image_data['original_path'])
                                    
                                    # 检查thumbnail_path
                                    if 'thumbnail_path' in image_data and image_data['thumbnail_path']:
                                        image_paths.append(image_data['thumbnail_path'])                       
                    
                    # 删除所有找到的图片文件
                    for image_path in set(image_paths):  # 使用set去重
                        if image_path and isinstance(image_path, str):
                            # 处理Windows路径分隔符
                            image_path = image_path.replace('\\', '/')
                            
                            # 处理相对路径和绝对路径
                            if not Path(image_path).is_absolute():
                                # 如果是相对路径，直接使用，因为通常相对于项目根目录
                                full_path = Path(image_path)
                                if not full_path.exists():
                                    # 如果直接路径不存在，尝试在常见的存储目录中查找
                                    for base_dir in ['storage', 'uploads', 'images', 'data']:
                                        full_path = Path(base_dir) / image_path
                                        if full_path.exists():
                                            break
                            else:
                                full_path = Path(image_path)
                            
                            if full_path.exists():
                                try:
                                    full_path.unlink()
                                    deleted_files_count += 1
                                    logger.debug(f"已删除外部事件图片: {full_path}")
                                except Exception as e:
                                    logger.warning(f"删除外部事件图片失败: {full_path}, 错误: {e}")
                
                except Exception as e:
                    logger.warning(f"处理外部事件文件删除失败 (事件ID: {getattr(event, 'event_id', 'unknown')}): {e}")
                    continue
            
            # 删除数据库记录
            deleted_events_count = db.query(ExternalEvent).filter(
                ExternalEvent.created_at < expire_time
            ).delete()
            
            # 提交删除操作
            if deleted_events_count > 0:
                db.commit()
                logger.info(f"外部数据事件清理完成: 删除 {deleted_events_count} 条记录 (>100天), {deleted_files_count} 个图片文件")
            else:
                logger.info("没有需要清理的外部数据事件")
                
        except Exception as e:
            logger.error(f"清理外部数据事件失败: {e}")
            if 'db' in locals():
                db.rollback()
        finally:
            if 'db' in locals():
                db.close()
    
    async def _cleanup_smart_events(self):
        """清理智能事件"""
        try:
            db = SessionLocal()
            current_time = datetime.now()
            
            # 智能事件保留7天
            expire_time = current_time - timedelta(days=7)
            
            # 查询要删除的外部事件（用于删除关联的文件）
            events_to_delete = db.query(SmartEvent).filter(
                SmartEvent.created_at < expire_time
            ).all()
            
            if not events_to_delete:
                logger.info("没有找到过期的智能事件")
                return
            
            deleted_events_count = 0
            
            logger.info(f"开始清理智能事件，共有 {len(events_to_delete)} 条过期事件需要处理")
            log_action(db, 'admin', 'cleanup_smart_events', 'system', f"开始清理智能事件，共有 {len(events_to_delete)} 条过期事件需要处理")
           
            # 删除数据库记录
            deleted_events_count = db.query(SmartEvent).filter(
                SmartEvent.created_at < expire_time
            ).delete()
            
            # 提交删除操作
            if deleted_events_count > 0:
                db.commit()
                logger.info(f"智能事件清理完成: 删除 {deleted_events_count} 条记录 (>30天)")
            else:
                logger.info("没有需要清理的智能事件")
                
        except Exception as e:
            logger.error(f"清理智能事件失败: {e}")
            if 'db' in locals():
                db.rollback()
        finally:
            if 'db' in locals():
                db.close()
            
# 创建检测服务器实例
detection_server = DetectionServer()

# 应用程序生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用程序生命周期管理"""
    logger.info("检测服务器启动中...")
    
    # 创建数据库表（如果不存在）
    Base.metadata.create_all(bind=engine)
    
    # 1. 注册数据监听器类型
    try:
        register_listener_types()
    except Exception as e:
        logger.error(f"注册监听器类型失败: {e}") 

    # 2. 启动设备监控服务
    try:
        device_monitor.start()
    except Exception as e:
        logger.error(f"启动设备监控服务失败: {e}")

    # 3. 启动FFmpeg解码器线程池
    # try:
    #     logger.info("启动FFmpeg解码器线程池")
    # except Exception as e:
    #     logger.error(f"启动FFmpeg解码器线程池失败: {e}")

    # 3.启动数据推送服务
    try:
        data_pusher.startup_push_service()
    except Exception as e:
        logger.error(f"启动数据推送服务失败: {e}")

    # 4. 启动时初始化事件订阅管理器
    try:
        await smart_schemer.initialize()
    except Exception as e:
        logger.error(f"事件订阅管理器初始化失败: {e}")

    # 5. 启动检测服务
    try:
        db = SessionLocal()
        await detection_server.start_all_enabled(db)
        db.close()
    except Exception as e:
        logger.error(f"启动检测服务失败: {e}")

    # 6. 启动人群分析服务
    try:       
        # 加载所有活跃的人群分析任务
        crowd_analyzer.load_all_active_jobs()
        # 启动人群分析服务
        crowd_analyzer.start()
    except Exception as e:
        logger.error(f"启动人群分析服务失败: {e}")

    # 7. 启动数据监听服务
    try:
        db = SessionLocal()
        await data_listener_manager.start_all_enabled(db)
        db.close()
    except Exception as e:
        logger.error(f"启动数据监听服务失败: {e}")
    
    # 8. 启动全局清理任务
    try:
        await detection_server.start_global_cleanup_task()
    except Exception as e:
        logger.error(f"启动全局清理任务失败: {e}")
    
    yield
    
    # 关闭服务（顺序与启动相反）
    logger.info("检测服务器关闭中...")
    
    # 1. 停止全局清理任务
    try:
        if detection_server.cleanup_task:
            detection_server.cleanup_task.cancel()
    except Exception as e:
        logger.error(f"停止全局清理任务失败: {e}")
    
    # 2. 停止数据监听服务
    try:
        await data_listener_manager.stop_all()
    except Exception as e:
        logger.error(f"停止数据监听服务失败: {e}")
    
    # 3. 停止人群分析服务
    try:
        crowd_analyzer.stop()
    except Exception as e:
        logger.error(f"停止人群分析服务失败: {e}")

    # 4. 停止检测任务
    for config_id, task in list(detection_server.tasks.items()):
        try:
            await task.stop()
        except Exception as e:
            logger.error(f"停止检测任务 {config_id} 失败: {e}")
    
    # 5. 关闭时清理事件订阅管理器
    try:
        await smart_schemer.shutdown()
    except Exception as e:
        logger.error(f"关闭事件订阅管理器失败: {e}")
    
    # 6. 停止数据推送服务
    try:
        data_pusher.shutdown_push_service()
    except Exception as e:
        logger.error(f"停止数据推送服务失败: {e}")

    # 7. 停止设备监控服务
    try:
        device_monitor.stop()
    except Exception as e:
        logger.error(f"停止设备监控服务失败: {e}")

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

# 启动检测任务API
@app.post("/api/v2/detection/{config_id}/start", tags=["检测任务"])
async def start_detection_api(config_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """启动检测任务API"""
    log_action(db, current_user.user_id, 'start_detection', config_id, f"启动检测任务: {config_id}")
    return await detection_server.start_detection(config_id, db, current_user.user_id)

# 停止检测任务API
@app.post("/api/v2/detection/{config_id}/stop", tags=["检测任务"])
async def stop_detection_api(config_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """停止检测任务API"""
    log_action(db, current_user.user_id, 'stop_detection', config_id, f"停止检测任务: {config_id}")
    return await detection_server.stop_detection(config_id, db, remove_scheduled_jobs=True, user_id=current_user.user_id)

# 获取所有检测任务的状态API
@app.get("/api/v2/detection/status", tags=["检测任务"])
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
    
    return {
        "status": "success",
        "tasks": tasks_status,
        "total_tasks": len(tasks_status)
    }

# 手动清理过期事件API
@app.post("/api/v2/detection/cleanup-expired-events", tags=["清理事件"])
async def cleanup_expired_events_api(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """手动清理过期检测事件和外部事件"""
    try:
        log_action(db, current_user.user_id, 'cleanup_expired_events', 'system', "手动清理过期事件")
        
        # 执行完整的清理操作（包括检测事件和外部事件）
        await detection_server._cleanup_all_expired_events()
        
        return {
            "status": "success",
            "message": "过期事件清理完成（包括检测事件和外部事件）"
        }
    except Exception as e:
        logger.error(f"手动清理过期事件失败: {e}")
        return {
            "status": "error",
            "message": f"清理失败: {str(e)}"
        }

# 手动清理外部事件API
@app.post("/api/v2/detection/cleanup-external-events", tags=["清理事件"])
async def cleanup_external_events_api(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """手动清理外部数据事件"""
    try:
        log_action(db, current_user.user_id, 'cleanup_external_events', 'system', "手动清理外部数据事件")
        
        # 执行外部事件清理
        await detection_server._cleanup_external_events()
        
        return {
            "status": "success",
            "message": "外部数据事件清理完成"
        }
    except Exception as e:
        logger.error(f"手动清理外部事件失败: {e}")
        return {
            "status": "error",
            "message": f"清理失败: {str(e)}"
        }

# 获取清理任务状态API
@app.get("/api/v2/detection/cleanup-status", tags=["清理事件"])
async def get_cleanup_status_api(current_user: User = Depends(get_current_user)):
    """获取清理任务状态"""
    try:
        now = datetime.now()
        
        # 计算下次清理时间
        next_cleanup = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if now >= next_cleanup:
            next_cleanup += timedelta(days=1)
        
        # 检查清理任务状态
        cleanup_task_running = (detection_server.cleanup_task is not None and 
                               not detection_server.cleanup_task.done())
        
        # 获取数据库中的事件统计
        db = SessionLocal()
        try:
            # 统计检测事件
            total_detection_events = db.query(DetectionEvent).count()
            expired_detection_events = 0
            
            # 统计各配置的过期事件
            configs = db.query(DetectionConfig).all()
            for config in configs:
                max_storage_days = config.max_storage_days if config.max_storage_days > 0 else 30
                expire_time = now - timedelta(days=max_storage_days)
                count = db.query(DetectionEvent).filter(
                    DetectionEvent.config_id == config.config_id,
                    DetectionEvent.created_at < expire_time
                ).count()
                expired_detection_events += count
            
            # 统计外部事件
            total_external_events = db.query(ExternalEvent).count()
            expire_time_external = now - timedelta(days=100)
            expired_external_events = db.query(ExternalEvent).filter(
                ExternalEvent.created_at < expire_time_external
            ).count()
            
        finally:
            db.close()
        
        return {
            "status": "success",
            "data": {
                "cleanup_task_running": cleanup_task_running,
                "next_cleanup_time": next_cleanup.strftime('%Y-%m-%d %H:%M:%S'),
                "current_time": now.strftime('%Y-%m-%d %H:%M:%S'),
                "time_until_next_cleanup": str(next_cleanup - now).split('.')[0],  # 去掉微秒
                "statistics": {
                    "detection_events": {
                        "total": total_detection_events,
                        "expired": expired_detection_events
                    },
                    "external_events": {
                        "total": total_external_events,
                        "expired": expired_external_events,
                        "retention_days": 100
                    }
                }
            }
        }
    except Exception as e:
        logger.error(f"获取清理任务状态失败: {e}")
        return {
            "status": "error",
            "message": f"获取状态失败: {str(e)}"
        }

# 获取系统资源状态API
@app.get("/api/v2/detection/system-status", tags=["清理事件"])
async def get_system_status_api(current_user: User = Depends(get_current_user)):
    """获取系统资源状态"""
    try:
        # 检查系统资源
        detection_server._check_system_resources()
        
        # 获取任务状态
        tasks_status = {}
        for config_id, task in detection_server.tasks.items():
            tasks_status[config_id] = {
                "device_id": task.device_id,
                "is_running": task.thread is not None and task.thread.is_alive(),
                "connected": task.connected,
                "clients_count": len(task.clients),
                "use_gpu_decoder": hasattr(task, 'ffmpeg_decoder') and task.ffmpeg_decoder is not None,
                "skip_frame_count": getattr(task, 'skip_frame_count', 5)
            }
        
        return {
            "status": "success",
            "data": {
                "system_resources": {
                    "cpu_usage": detection_server.total_cpu_usage,
                    "memory_usage": detection_server.total_memory_usage,
                    "active_tasks": detection_server.active_task_count,
                    "max_concurrent_tasks": detection_server.max_concurrent_tasks
                },
                "tasks": tasks_status,
                "total_tasks": len(tasks_status),
                "gpu_available": torch.cuda.is_available(),
                "gpu_device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0
            }
        }
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        return {
            "status": "error",
            "message": f"获取系统状态失败: {str(e)}"
        }

# 加载模型API端点
@app.post("/api/v2/model/load", tags=["检测任务"])
async def load_model_api(model_data: dict): # 加载模型API端点
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

# 检测预览WebSocket端点
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

# 添加RTSP相关的API接口
from api.rtsp_server import router as rtsp_router
app.include_router(rtsp_router, prefix="/ws")

# 添加数据监听相关的API接口
from api.data_listener_routes import router as data_listener_router
app.include_router(data_listener_router, prefix="/api/v2")

# 添加事件订阅相关的API接口
from api.smart_scheme_routes import router as smart_scheme_router
app.include_router(smart_scheme_router, prefix="/api/v2")

# 主函数
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 