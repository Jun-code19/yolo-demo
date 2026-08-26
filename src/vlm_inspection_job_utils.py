"""VLM 巡检任务：设备解析与 API 响应"""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.database import Device, VlmInspectionJob


DEFAULT_GROUP_SETTINGS = {
    "frame_source_primary": "snapshot",
    "frame_source_fallback": "rtsp",
    "device_interval_sec": 1.0,
}

DEFAULT_VLM_CONFIG = {
    "task_type": "detect",
    "input": {"scope": "full_frame", "max_width": 1280, "jpeg_quality": 85},
    "output_schema": "vlm_detect_v1",
    "rate_limit": {"cooldown_after_alert_sec": 30},
    "save_snapshot": True,
}


def resolve_inspection_devices(db: Session, job: VlmInspectionJob) -> List[str]:
    mode = getattr(job, "device_mode", None) or "manual"
    if mode == "group" and job.group_id:
        devices = (
            db.query(Device)
            .filter(Device.group_id == job.group_id, Device.status.is_(True))
            .order_by(Device.device_name)
            .all()
        )
        return [d.device_id for d in devices]
    return list(job.device_ids or [])


def snapshot_group_devices(db: Session, group_id: str) -> List[str]:
    devices = (
        db.query(Device)
        .filter(Device.group_id == group_id, Device.status.is_(True))
        .order_by(Device.device_name)
        .all()
    )
    return [d.device_id for d in devices]


def normalize_group_settings(settings: Optional[Dict]) -> Dict:
    return {**DEFAULT_GROUP_SETTINGS, **(settings or {})}


def normalize_vlm_config(config: Optional[Dict]) -> Dict:
    merged = {**DEFAULT_VLM_CONFIG, **(config or {})}
    merged["input"] = {**DEFAULT_VLM_CONFIG["input"], **(merged.get("input") or {})}
    merged["rate_limit"] = {**DEFAULT_VLM_CONFIG["rate_limit"], **(merged.get("rate_limit") or {})}
    return merged


def build_inspection_job_response(
    db_job: VlmInspectionJob,
    memory_job: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    status = "paused" if not db_job.is_active else (db_job.status or "created")
    resolved_device_ids = list(db_job.device_ids or [])
    if db is not None:
        resolved_device_ids = resolve_inspection_devices(db, db_job)
    response = {
        "job_id": db_job.job_id,
        "job_name": db_job.job_name,
        "device_mode": db_job.device_mode or "manual",
        "group_id": db_job.group_id,
        "group_settings": normalize_group_settings(db_job.group_settings),
        "schedule_config": db_job.schedule_config or {},
        "device_ids": db_job.device_ids or [],
        "resolved_device_ids": resolved_device_ids,
        "device_count": len(resolved_device_ids),
        "vlm_model_id": db_job.vlm_model_id,
        "prompt_id": db_job.prompt_id or "general_patrol_v1",
        "prompt_override": db_job.prompt_override,
        "vlm_config": normalize_vlm_config(db_job.vlm_config),
        "alert_labels": db_job.alert_labels or [],
        "min_confidence": db_job.min_confidence or 0.7,
        "interval": db_job.interval or 300,
        "tags": db_job.tags or [],
        "description": db_job.description,
        "is_active": db_job.is_active,
        "status": status,
        "last_run": db_job.last_run,
        "last_result": db_job.last_result,
        "last_error": db_job.last_error,
        "created_at": db_job.created_at,
        "updated_at": db_job.updated_at,
    }
    if memory_job:
        response["last_run"] = memory_job.get("last_run") or response["last_run"]
        response["status"] = memory_job.get("status", response["status"])
        response["last_result"] = memory_job.get("last_result") or response["last_result"]
        response["last_error"] = memory_job.get("last_error") or response["last_error"]
    response["is_running"] = False
    return response


def build_inspection_run_response(run_row: "VlmInspectionRun") -> Dict[str, Any]:
    duration_sec = None
    if run_row.started_at and run_row.finished_at:
        duration_sec = int((run_row.finished_at - run_row.started_at).total_seconds())
    return {
        "run_id": run_row.run_id,
        "job_id": run_row.job_id,
        "started_at": run_row.started_at,
        "finished_at": run_row.finished_at,
        "device_total": run_row.device_total or 0,
        "device_success": run_row.device_success or 0,
        "device_failed": run_row.device_failed or 0,
        "alert_count": run_row.alert_count or 0,
        "status": run_row.status,
        "summary": run_row.summary,
        "duration_sec": duration_sec,
    }
