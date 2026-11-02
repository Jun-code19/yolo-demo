"""平台端系统状态采集（CPU / 内存 / 磁盘 / GPU / 主机信息）"""
from __future__ import annotations

import os
import platform
import socket
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session


def _format_uptime(seconds: float) -> str:
    total = max(0, int(seconds))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts: List[str] = []
    if days:
        parts.append(f"{days}天")
    if hours or days:
        parts.append(f"{hours}小时")
    if minutes or hours or days:
        parts.append(f"{minutes}分")
    parts.append(f"{secs}秒")
    return "".join(parts)


def _disk_usage(path: str) -> Dict[str, Any]:
    import psutil

    try:
        usage = psutil.disk_usage(path)
        return {
            "path": path,
            "percent": round(usage.percent, 1),
            "total": round(usage.total / (1024 ** 3), 2),
            "used": round(usage.used / (1024 ** 3), 2),
            "free": round(usage.free / (1024 ** 3), 2),
        }
    except Exception:
        return {"path": path, "percent": 0, "total": 0, "used": 0, "free": 0}


def _collect_gpus() -> Dict[str, Any]:
    """返回首卡汇总 + 全部 GPU 列表。"""
    devices: List[Dict[str, Any]] = []
    try:
        import GPUtil

        for gpu in GPUtil.getGPUs() or []:
            devices.append(
                {
                    "id": gpu.id,
                    "name": getattr(gpu, "name", None) or f"GPU-{gpu.id}",
                    "percent": round(float(gpu.load or 0) * 100, 1),
                    "memory_total": round(float(gpu.memoryTotal or 0) / 1024, 2),
                    "memory_used": round(float(gpu.memoryUsed or 0) / 1024, 2),
                    "temperature": getattr(gpu, "temperature", None),
                }
            )
    except Exception:
        pass

    if not devices:
        return {
            "percent": 0,
            "total": 0,
            "used": 0,
            "available": False,
            "devices": [],
        }

    first = devices[0]
    return {
        "percent": first["percent"],
        "total": first["memory_total"],
        "used": first["memory_used"],
        "available": True,
        "name": first["name"],
        "devices": devices,
    }


def collect_system_status(db: Optional[Session] = None) -> Dict[str, Any]:
    import psutil

    now = datetime.now()
    boot_ts = psutil.boot_time()
    uptime_sec = now.timestamp() - boot_ts

    cpu_percent = psutil.cpu_percent(interval=0.4)
    cpu_logical = psutil.cpu_count(logical=True) or 0
    cpu_physical = psutil.cpu_count(logical=False) or 0

    memory = psutil.virtual_memory()

    disk_root = (os.environ.get("SystemDrive", "C:") + "\\") if os.name == "nt" else "/"
    disk = _disk_usage(disk_root)

    # 项目根目录所在磁盘（便于观察模型/日志占用）
    project_root = Path(__file__).resolve().parents[1]
    data_storage = _disk_usage(str(project_root))

    gpu = _collect_gpus()

    status = "normal"
    if cpu_percent > 90 or memory.percent > 90 or disk["percent"] > 90 or gpu["percent"] > 90:
        status = "danger"
    elif cpu_percent > 70 or memory.percent > 80 or disk["percent"] > 80 or gpu["percent"] > 70:
        status = "warning"

    enabled_configs = 0
    active_models = 0
    if db is not None:
        try:
            from src.database import DetectionConfig, DetectionModel

            enabled_configs = (
                db.query(DetectionConfig).filter(DetectionConfig.enabled.is_(True)).count()
            )
            active_models = (
                db.query(DetectionModel).filter(DetectionModel.is_active.is_(True)).count()
            )
        except Exception:
            pass

    return {
        "status": status,
        "system": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "app_name": "yolo-demo",
            "app_version": os.getenv("APP_VERSION", "1.0.0"),
            "current_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "boot_time": datetime.fromtimestamp(boot_ts).strftime("%Y-%m-%d %H:%M:%S"),
            "uptime_seconds": int(uptime_sec),
            "uptime_text": _format_uptime(uptime_sec),
        },
        "cpu": {
            "percent": round(cpu_percent, 1),
            "total": cpu_logical,
            "physical": cpu_physical,
            "used": round(cpu_logical * (cpu_percent / 100.0), 2),
        },
        "memory": {
            "percent": round(memory.percent, 1),
            "total": round(memory.total / (1024 ** 3), 2),
            "used": round(memory.used / (1024 ** 3), 2),
            "available": round(memory.available / (1024 ** 3), 2),
        },
        "disk": disk,
        "data_storage": data_storage,
        "gpu": gpu,
        "detection": {
            "enabled_configs": enabled_configs,
            "active_models": active_models,
        },
        # 兼容旧前端字段（已废弃实时日志）
        "logs": [],
    }
