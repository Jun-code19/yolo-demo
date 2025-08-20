"""
设备状态监控服务
定期检查所有视频设备的在线状态和记录心跳时间并更新到数据库
"""
import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from src.database import SessionLocal, Device
from src.data_pusher import data_pusher

logger = logging.getLogger(__name__)

class DeviceMonitor:
    """设备状态监控器"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        # 配置APScheduler日志
        logging.getLogger('apscheduler').setLevel(logging.WARNING)
        self.running = False
        self.monitoring_config = {
            'check_interval': 600,  # 10分钟检测一次设备状态
            'push_interval': 30,    # 30秒推送一次状态数据
            'enable_notifications': True  # 是否启用通知
        }
        self.device_status_history = {}  # 设备状态历史记录
        self.lock = threading.Lock()
        
    def start(self):
        """启动设备监控服务"""
        if not self.running:
            self.running = True

            self.scheduler.start()
            
            # 添加设备状态检测任务 - 每5分钟执行一次
            self.scheduler.add_job(
                self._run_check_devices_status,
                IntervalTrigger(seconds=self.monitoring_config['check_interval']),
                id='device_status_check',
                replace_existing=True
            )
            
            # 添加状态数据推送任务 - 每10秒执行一次
            self.scheduler.add_job(
                self._run_push_device_status_data,
                IntervalTrigger(seconds=self.monitoring_config['push_interval']),
                id='device_status_push',
                replace_existing=True
            )
            
    def stop(self):
        """停止设备监控服务"""
        if self.running:
            self.running = False
            self.scheduler.shutdown()
    
    def _run_check_devices_status(self):
        """包装函数：在新的事件循环中运行异步检测任务"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.check_all_devices_status())
        except Exception as e:
            logger.error(f"运行设备状态检测任务失败: {e}")
        finally:
            loop.close()
    
    def _run_push_device_status_data(self):
        """包装函数：在新的事件循环中运行异步推送任务"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.push_device_status_data())
        except Exception as e:
            logger.error(f"运行设备状态推送任务失败: {e}")
        finally:
            loop.close()
        
    async def check_all_devices_status(self):
        """检查所有设备的在线状态 - 每5分钟执行一次"""
        try:
            db = SessionLocal()
            devices = db.query(Device).all()
                       
            for device in devices:
                try:
                    # 检查设备连接状态
                    is_online = await self._check_device_connection(device)
                    
                    # 更新设备状态
                    device.status = is_online
                    if is_online:
                        # 在线时更新心跳时间
                        device.last_heartbeat = datetime.now()
                    
                except Exception as e:
                    device.status = False
            
            # 批量提交数据库更新
            db.commit()
            
        except Exception as e:
            logger.error(f"设备状态检查失败: {e}")
        finally:
            db.close()
            
    async def push_device_status_data(self):
        """推送设备状态数据 - 每10秒执行一次"""
        try:
            db = SessionLocal()
            devices = db.query(Device).all()
            
            cameraStatuses = []
            for device in devices:
                cameraStatuses.append({
                    'deviceId': device.device_id,
                    'online': device.status,
                })
           
            # 推送数据
            try:
                if data_pusher.push_configs:               
                    data_pusher.push_data(
                        data={'cameraStatuses': cameraStatuses},
                        tags=["device_online_status"]
                    )
            except Exception as push_error:
                logger.error(f"推送设备状态数据失败: {push_error}")
                
        except Exception as e:
            logger.error(f"构建设备状态数据失败: {e}")
        finally:
            db.close()
            
    async def _check_device_connection(self, device: Device) -> bool:
        """检查单个设备的连接状态"""
        try:
            # 方法1: HTTP连接测试（适用于支持HTTP API的设备）
            if await self._test_http_connection(device):
                return True
                
            # 方法2: ICMP Ping测试
            if await self._test_ping_connection(device):
                return True
                
            return False
            
        except Exception as e:
            return False
            
    async def _test_http_connection(self, device: Device) -> bool:
        """测试HTTP连接"""
        try:
            import aiohttp
            
            # 尝试多种常见的API端点
            test_urls = [
                f"http://{device.ip_address}/cgi-bin/api/tcpConnect/tcpTest"
            ]
            
            try:
                timeout = aiohttp.ClientTimeout(total=3)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(test_urls) as response:
                        if response.status in [200, 401, 403]:
                            return True
            except:
                return False                   
            
        except Exception as e:
            return False
            
    async def _test_ping_connection(self, device: Device) -> bool:
        """测试ICMP Ping连接"""
        try:
            import subprocess
            import platform
            
            # Windows系统
            if platform.system().lower() == "windows":
                cmd = ["ping", "-n", "1", "-w", "3000", device.ip_address]
            else:
                cmd = ["ping", "-c", "1", "-W", "3", device.ip_address]
                
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Ping测试失败: {e}")
            return False
                         
    def get_monitoring_status(self) -> Dict:
        """获取监控服务状态"""
        with self.lock:
            return {
                'running': self.running,
                'config': self.monitoring_config,
                'scheduler_jobs': len(self.scheduler.get_jobs()),
                'last_check_time': datetime.now().isoformat()
            }
               
# 全局实例
device_monitor = DeviceMonitor()
