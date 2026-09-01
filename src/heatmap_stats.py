"""热力图区域绑定与园内人数聚合统计"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.database import CrowdAnalysisJob, HeatmapBinding, SmartEvent, SmartScheme, Device


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_crowd_last_result(last_result: Any) -> int:
    if not last_result:
        return 0
    try:
        if isinstance(last_result, dict):
            return _safe_int(last_result.get("total_person_count"))
        import json
        parsed = json.loads(last_result) if isinstance(last_result, str) else last_result
        if isinstance(parsed, dict):
            return _safe_int(parsed.get("total_person_count"))
    except Exception:
        return 0
    return 0


def _parse_event_data(raw: Any) -> Dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _stats_from_number_stat_event(event: Optional[SmartEvent]) -> Dict[str, Any]:
    if not event or not event.event_data:
        return {
            "current_count": 0,
            "staying_count": 0,
            "entered_count": 0,
            "exited_count": 0,
            "last_update_time": None,
        }
    data = _parse_event_data(event.event_data)
    staying = _safe_int(data.get("stayingCount") or data.get("staying_count"))
    entered = _safe_int(data.get("enteredCount") or data.get("entered_count"))
    exited = _safe_int(data.get("exitedCount") or data.get("exited_count"))
    return {
        "current_count": staying,
        "staying_count": staying,
        "entered_count": entered,
        "exited_count": exited,
        "last_update_time": event.timestamp,
    }


def resolve_binding_stats(db: Session, binding: Optional[HeatmapBinding]) -> Dict[str, Any]:
    if not binding or not binding.data_source_id:
        return {
            "current_count": 0,
            "staying_count": 0,
            "entered_count": 0,
            "exited_count": 0,
            "last_update_time": None,
        }

    source_type = binding.data_source_type or "crowd_analysis"
    source_id = binding.data_source_id

    if source_type == "smart_scheme":
        event = (
            db.query(SmartEvent)
            .filter(
                SmartEvent.scheme_id == source_id,
                SmartEvent.event_type == "number_stat",
            )
            .order_by(SmartEvent.timestamp.desc())
            .first()
        )
        return _stats_from_number_stat_event(event)

    job = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.job_id == source_id).first()
    count = _parse_crowd_last_result(job.last_result if job else None)
    return {
        "current_count": count,
        "staying_count": count,
        "entered_count": 0,
        "exited_count": 0,
        "last_update_time": job.last_run if job else None,
    }


def _scheme_display_name(db: Session, scheme: Optional[SmartScheme], scheme_id: str) -> str:
    if not scheme:
        return scheme_id
    device = db.query(Device).filter(Device.device_id == scheme.camera_id).first()
    if device and device.device_name:
        return device.device_name
    if scheme.remarks:
        return scheme.remarks
    return scheme_id


def parse_area_meta(description: Any) -> Dict[str, Any]:
    if not description:
        return {}
    if isinstance(description, dict):
        return description
    try:
        if isinstance(description, str) and description.strip().startswith("{"):
            data = json.loads(description)
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def get_area_display_unit(area, binding_config: Optional[Dict[str, Any]] = None) -> str:
    meta = parse_area_meta(getattr(area, "description", None))
    unit = str(meta.get("display_unit") or "").strip()
    if unit:
        return unit
    if binding_config:
        unit = str(binding_config.get("display_unit") or "").strip()
        if unit:
            return unit
    return "人"


def build_area_description_meta(display_unit: Optional[str]) -> str:
    unit = str(display_unit or "人").strip() or "人"
    return json.dumps({"display_unit": unit}, ensure_ascii=False)


def build_area_response(area, binding: Optional[HeatmapBinding], stats: Dict[str, Any]) -> Dict[str, Any]:
    config = (binding.config if binding else None) or {}
    display_unit = get_area_display_unit(area, config)
    return {
        "id": area.id,
        "map_id": area.map_id,
        "name": area.name,
        "shape_type": getattr(area, "shape_type", None) or "polygon",
        "points": area.points,
        "color": area.color,
        "area_size": area.area_size,
        "max_capacity": area.max_capacity,
        "description": area.description,
        "data_source_type": binding.data_source_type if binding else None,
        "data_source_id": binding.data_source_id if binding else None,
        "data_source_name": binding.data_source_name if binding else None,
        "display_unit": display_unit,
        "current_count": stats["current_count"],
        "staying_count": stats.get("staying_count", stats["current_count"]),
        "entered_count": stats.get("entered_count", 0),
        "exited_count": stats.get("exited_count", 0),
        "last_update_time": stats.get("last_update_time"),
        "created_at": area.created_at,
        "updated_at": area.updated_at,
        "is_active": area.is_active,
    }


def compute_park_stats(db: Session, park_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not park_config or not park_config.get("enabled"):
        return None

    scheme_ids: List[str] = park_config.get("scheme_ids") or []
    if not scheme_ids:
        return None

    total_entered = 0
    total_exited = 0
    total_park = 0
    sources = []
    last_update: Optional[datetime] = None

    for scheme_id in scheme_ids:
        scheme = db.query(SmartScheme).filter(SmartScheme.id == scheme_id).first()
        event = (
            db.query(SmartEvent)
            .filter(
                SmartEvent.scheme_id == scheme_id,
                SmartEvent.event_type == "number_stat",
            )
            .order_by(SmartEvent.timestamp.desc())
            .first()
        )
        stats = _stats_from_number_stat_event(event)
        entered = stats["entered_count"]
        exited = stats["exited_count"]
        # 多出入口场景：各订阅独立计算进入-离开，允许单点/合计为负
        scheme_park = entered - exited
        total_entered += entered
        total_exited += exited
        total_park += scheme_park
        ts = stats.get("last_update_time")
        if ts and (last_update is None or ts > last_update):
            last_update = ts
        sources.append({
            "scheme_id": scheme_id,
            "name": _scheme_display_name(db, scheme, scheme_id),
            "stayingCount": scheme_park,
            "enteredCount": entered,
            "exitedCount": exited,
        })

    park_count = total_park

    return {
        "title": park_config.get("title") or "园内人数",
        "stayingCount": park_count,
        "enteredCount": total_entered,
        "exitedCount": total_exited,
        "lastUpdate": last_update.isoformat() if last_update else None,
        "sources": sources,
    }
