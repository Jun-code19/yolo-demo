"""
设备状态监控服务
支持可配置探活策略：RTSP（通道级）、TCP、HTTP（大华）、可选 Ping
"""
import asyncio
import json
import logging
import platform
import shutil
import subprocess
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.database import SessionLocal, Device, DetectionConfig
from src.data_pusher import data_pusher
from src.device_monitor_config import load_device_monitor_config, resolve_check_methods
from src.rtsp_url import build_rtsp_url

logger = logging.getLogger(__name__)


class DeviceConnectivityChecker:
    """设备连通性探测（可被监控任务与 API 共用）"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or load_device_monitor_config()

    def reload_config(self, db_session=None) -> None:
        self.config = load_device_monitor_config(db_session)

    async def check_device(self, device: Device) -> bool:
        methods = resolve_check_methods(device, self.config)
        for method in methods:
            if method == "ping" and not self.config.get("enable_ping"):
                continue
            checker = getattr(self, f"_check_{method}", None)
            if checker is None:
                continue
            try:
                if await checker(device):
                    return True
            except Exception as exc:
                logger.debug("设备 %s 探活 %s 失败: %s", device.device_id, method, exc)
        return False

    async def _check_rtsp(self, device: Device) -> bool:
        stream = self.config.get("rtsp_stream_for_probe", "sub")
        rtsp_url = build_rtsp_url(device, stream_type=stream)
        timeout = float(self.config.get("rtsp_timeout_seconds", 6))
        if shutil.which("ffprobe"):
            return await asyncio.to_thread(self._probe_rtsp_ffprobe, rtsp_url, timeout)
        return await asyncio.to_thread(self._probe_rtsp_opencv, rtsp_url, timeout)

    @staticmethod
    def _probe_rtsp_ffprobe(rtsp_url: str, timeout: float) -> bool:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-rtsp_transport", "tcp",
            "-stimeout", str(int(timeout * 1_000_000)),
            "-i", rtsp_url,
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=max(timeout + 1, 2),
            )
            return result.returncode == 0 and bool(result.stdout.strip())
        except (subprocess.TimeoutExpired, OSError):
            return False

    @staticmethod
    def _probe_rtsp_opencv(rtsp_url: str, timeout: float) -> bool:
        import time
        try:
            import cv2
        except ImportError:
            return False

        cap = None
        try:
            cap = cv2.VideoCapture(rtsp_url)
            if not cap.isOpened():
                return False
            deadline = time.time() + timeout
            while time.time() < deadline:
                ok, _ = cap.read()
                if ok:
                    return True
                time.sleep(0.2)
            return False
        except Exception:
            return False
        finally:
            if cap is not None:
                cap.release()

    async def _check_tcp(self, device: Device) -> bool:
        host = device.ip_address
        ports = []
        if device.port:
            ports.append(int(device.port))
        if 554 not in ports:
            ports.append(554)
        timeout = float(self.config.get("tcp_timeout_seconds", 3))
        for port in ports:
            if await self._tcp_open(host, port, timeout):
                return True
        return False

    @staticmethod
    async def _tcp_open(host: str, port: int, timeout: float) -> bool:
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, asyncio.TimeoutError):
            return False

    async def _check_http_dahua(self, device: Device) -> bool:
        path = self.config.get("http_dahua_path", "/cgi-bin/api/tcpConnect/tcpTest")
        port = int(self.config.get("http_dahua_port", 80))
        url = f"http://{device.ip_address}:{port}{path}"
        payload = {"Ip": device.ip_address, "Port": port}
        timeout = aiohttp.ClientTimeout(total=float(self.config.get("http_timeout_seconds", 3)))
        headers = {"Content-Type": "application/json", "User-Agent": "DeviceMonitor/2.0"}
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, data=json.dumps(payload), headers=headers) as response:
                    return response.status in (200, 401, 403, 404)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False

    async def _check_ping(self, device: Device) -> bool:
        if platform.system().lower() == "windows":
            cmd = ["ping", "-n", "1", "-w", "3000", device.ip_address]
        else:
            cmd = ["ping", "-c", "1", "-W", "3", device.ip_address]
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False


class DeviceMonitor:
    """设备状态监控器"""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        logging.getLogger("apscheduler").setLevel(logging.WARNING)
        self.running = False
        self.config = load_device_monitor_config()
        self.checker = DeviceConnectivityChecker(self.config)
        self.device_status_history: Dict[str, Any] = {}
        self.lock = threading.Lock()

    def _reload_runtime_config(self) -> None:
        db = SessionLocal()
        try:
            self.config = load_device_monitor_config(db)
            self.checker.config = self.config
        finally:
            db.close()

    def start(self):
        if self.running:
            return
        self._reload_runtime_config()
        self.running = True
        self.scheduler.start()

        self.scheduler.add_job(
            self._run_check_devices_status,
            IntervalTrigger(seconds=int(self.config["check_interval"])),
            id="device_status_check",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._run_push_device_status_data,
            IntervalTrigger(seconds=int(self.config["push_interval"])),
            id="device_status_push",
            replace_existing=True,
        )

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.scheduler.shutdown()

    def reload_scheduler(self):
        """配置变更后重建定时任务（无需重启检测服务）"""
        if not self.running:
            return
        self._reload_runtime_config()
        for job_id in ("device_status_check", "device_status_push"):
            try:
                self.scheduler.remove_job(job_id)
            except Exception:
                pass
        self.scheduler.add_job(
            self._run_check_devices_status,
            IntervalTrigger(seconds=int(self.config["check_interval"])),
            id="device_status_check",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._run_push_device_status_data,
            IntervalTrigger(seconds=int(self.config["push_interval"])),
            id="device_status_push",
            replace_existing=True,
        )

    def _run_check_devices_status(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.check_all_devices_status())
        except Exception as exc:
            logger.error("运行设备状态检测任务失败: %s", exc)
        finally:
            loop.close()

    def _run_push_device_status_data(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.push_device_status_data())
        except Exception as exc:
            logger.error("运行设备状态推送任务: %s", exc)
        finally:
            loop.close()

    async def check_all_devices_status(self):
        self._reload_runtime_config()
        db = SessionLocal()
        try:
            devices = db.query(Device).all()
            offline_threshold = int(self.config.get("offline_threshold", 3))
            retry_count = int(self.config.get("retry_count", 3))
            retry_delay = float(self.config.get("retry_delay_seconds", 1))
            per_device_delay = float(self.config.get("per_device_delay_seconds", 0.2))

            for device in devices:
                try:
                    is_online = False
                    for _ in range(retry_count):
                        is_online = await self.checker.check_device(device)
                        if is_online:
                            break
                        await asyncio.sleep(retry_delay)

                    if is_online:
                        device.offline_count = 0
                        device.last_online_time = datetime.now()
                        device.status = True
                        device.last_heartbeat = datetime.now()
                    else:
                        device.offline_count = (device.offline_count or 0) + 1
                        if device.offline_count >= offline_threshold:
                            device.status = False
                except Exception:
                    device.offline_count = (device.offline_count or 0) + 1
                    if device.offline_count >= offline_threshold:
                        device.status = False

                await asyncio.sleep(per_device_delay)

            db.commit()
        except Exception as exc:
            logger.error("设备状态检查失败: %s", exc)
            db.rollback()
        finally:
            db.close()

    async def push_device_status_data(self):
        self._reload_runtime_config()
        enable_push = self.config.get("enable_push", self.config.get("enable_notifications", True))
        if not enable_push:
            return

        push_tags = self.config.get("push_tags") or ["device_online_status"]
        if isinstance(push_tags, str):
            push_tags = [t.strip() for t in push_tags.split(",") if t.strip()]
        if not push_tags:
            push_tags = ["device_online_status"]

        db = SessionLocal()
        try:
            results = (
                db.query(
                    Device.device_id,
                    Device.status,
                    DetectionConfig.area_coordinates,
                )
                .outerjoin(DetectionConfig, Device.device_id == DetectionConfig.device_id)
                .all()
            )

            camera_statuses = []
            for device_id, status, area_coordinates in results:
                camera_statuses.append({"deviceId": device_id, "online": status})
                if not area_coordinates:
                    continue
                occupancy_areas = area_coordinates.get("occupancyAreas")
                if not occupancy_areas or len(occupancy_areas) <= 1:
                    continue
                for area in occupancy_areas:
                    camera_statuses.append({"deviceId": area.get("name"), "online": status})

            if data_pusher.push_configs:
                data_pusher.push_data(
                    data={"cameraStatuses": camera_statuses},
                    tags=push_tags,
                )
        except Exception as exc:
            logger.error("构建设备状态数据失败: %s", exc)
        finally:
            db.close()

    def get_monitoring_status(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "running": self.running,
                "config": self.config,
                "scheduler_jobs": len(self.scheduler.get_jobs()) if self.running else 0,
                "last_check_time": datetime.now().isoformat(),
            }


async def check_device_online(device: Device, db_session=None) -> bool:
    """供 API 等模块复用的单设备探活"""
    config = load_device_monitor_config(db_session)
    checker = DeviceConnectivityChecker(config)
    return await checker.check_device(device)


device_monitor = DeviceMonitor()
