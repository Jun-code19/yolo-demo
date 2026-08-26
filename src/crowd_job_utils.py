"""人群分析任务：设备解析与响应构建"""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.database import CrowdAnalysisJob, Device


def resolve_crowd_job_devices(db: Session, job: CrowdAnalysisJob) -> List[str]:
    """按 device_mode 解析当前应分析的设备列表"""
    mode = getattr(job, "device_mode", None) or "manual"
    if mode == "group" and job.group_id:
        devices = (
            db.query(Device)
            .filter(Device.group_id == job.group_id, Device.status.is_(True))
            .order_by(Device.device_name)
            .all()
        )
        return [device.device_id for device in devices]
    return list(job.device_ids or [])


def snapshot_group_devices(db: Session, group_id: str) -> List[str]:
    devices = (
        db.query(Device)
        .filter(Device.group_id == group_id, Device.status.is_(True))
        .order_by(Device.device_name)
        .all()
    )
    return [device.device_id for device in devices]


def build_crowd_job_response(
    db_job: CrowdAnalysisJob,
    memory_job: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """构建人群分析任务 API 响应"""
    response = {
        "job_id": db_job.job_id,
        "job_name": db_job.job_name,
        "device_mode": getattr(db_job, "device_mode", None) or "manual",
        "group_id": db_job.group_id,
        "group_settings": db_job.group_settings or {},
        "schedule_config": db_job.schedule_config or {},
        "device_ids": db_job.device_ids or [],
        "models_id": db_job.models_id,
        "detect_classes": db_job.detect_classes or [],
        "confidence_threshold": db_job.confidence_threshold or 0.5,
        "interval": db_job.interval or 0,
        "cron_expression": db_job.cron_expression,
        "tags": db_job.tags or [],
        "location_info": db_job.location_info or {},
        "description": db_job.description,
        "warning_threshold": db_job.warning_threshold or 0,
        "warning_message": db_job.warning_message,
        "created_at": db_job.created_at,
        "is_active": db_job.is_active,
        "last_run": db_job.last_run,
        "status": "paused" if not db_job.is_active else "created",
        "last_result": db_job.last_result,
        "last_error": db_job.last_error,
    }
    if memory_job:
        response["last_run"] = memory_job.get("last_run") or response["last_run"]
        response["status"] = memory_job.get(
            "status", "paused" if not db_job.is_active else "created"
        )
        response["last_result"] = memory_job.get("last_result") or response["last_result"]
        response["last_error"] = memory_job.get("last_error") or response["last_error"]
    return response
