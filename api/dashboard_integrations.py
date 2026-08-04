import os
from copy import deepcopy
from typing import Any, Dict, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth import check_admin_permission, get_current_user
from api.logger import log_action
from src.database import PlatformSetting, User, get_db

SETTING_KEY = "dashboard_integrations"

DEFAULT_INTEGRATIONS: Dict[str, Any] = {
    "wait_time_enabled": True,
    "wait_time_url": os.getenv("WAIT_TIME_API_URL", ""),
    "wait_time_token": os.getenv("WAIT_TIME_API_TOKEN", ""),
    "weather_enabled": True,
    "weather_api_url": os.getenv(
        "WEATHER_API_URL",
        "https://api.seniverse.com/v3/weather/now.json",
    ),
    "weather_api_key": os.getenv("WEATHER_API_KEY", ""),
    "weather_default_lat": float(os.getenv("WEATHER_DEFAULT_LAT", "39.9042")),
    "weather_default_lon": float(os.getenv("WEATHER_DEFAULT_LON", "116.4074")),
}

SECRET_FIELDS = ("wait_time_token", "weather_api_key")

router = APIRouter(tags=["大屏外部数据"])


class DashboardIntegrationsModel(BaseModel):
    wait_time_enabled: bool = True
    wait_time_url: str = ""
    wait_time_token: Optional[str] = None
    weather_enabled: bool = True
    weather_api_url: str = "https://api.seniverse.com/v3/weather/now.json"
    weather_api_key: Optional[str] = None
    weather_default_lat: float = Field(default=39.9042, ge=-90, le=90)
    weather_default_lon: float = Field(default=116.4074, ge=-180, le=180)


def _merge_defaults(stored: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = deepcopy(DEFAULT_INTEGRATIONS)
    if stored:
        merged.update(stored)
    return merged


def _load_integrations(db: Session) -> Dict[str, Any]:
    row = db.query(PlatformSetting).filter(PlatformSetting.setting_key == SETTING_KEY).first()
    if row and row.setting_value:
        return _merge_defaults(row.setting_value)
    return deepcopy(DEFAULT_INTEGRATIONS)


def _save_integrations(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    row = db.query(PlatformSetting).filter(PlatformSetting.setting_key == SETTING_KEY).first()
    if row:
        row.setting_value = payload
    else:
        row = PlatformSetting(setting_key=SETTING_KEY, setting_value=payload)
        db.add(row)
    db.commit()
    db.refresh(row)
    return row.setting_value


def _mask_config(config: Dict[str, Any]) -> Dict[str, Any]:
    masked = deepcopy(config)
    for field in SECRET_FIELDS:
        value = masked.get(field) or ""
        if not value:
            masked[field] = ""
            masked[f"{field}_configured"] = False
            continue
        masked[f"{field}_configured"] = True
        if len(value) <= 4:
            masked[field] = "****"
        else:
            masked[field] = "*" * (len(value) - 4) + value[-4:]
    return masked


def _apply_secret_merge(incoming: Dict[str, Any], existing: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(existing)
    merged.update({k: v for k, v in incoming.items() if k not in SECRET_FIELDS})
    for field in SECRET_FIELDS:
        new_val = incoming.get(field)
        if new_val is not None and str(new_val).strip():
            merged[field] = str(new_val).strip()
    return merged


@router.get("/settings/dashboard-integrations")
def get_dashboard_integrations_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = _load_integrations(db)
    return {"success": True, "data": _mask_config(config)}


@router.put("/settings/dashboard-integrations")
def save_dashboard_integrations_config(
    body: DashboardIntegrationsModel,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_admin_permission),
):
    existing = _load_integrations(db)
    incoming = body.model_dump()
    saved = _apply_secret_merge(incoming, existing)
    _save_integrations(db, saved)
    log_action(
        db,
        current_user.user_id,
        "update_system_config",
        SETTING_KEY,
        "更新大屏外部数据接口配置",
    )
    return {"success": True, "data": _mask_config(saved)}


@router.get("/dashboard/wait-time")
def proxy_wait_time(db: Session = Depends(get_db)):
    config = _load_integrations(db)
    if not config.get("wait_time_enabled", True):
        return {"success": True, "data": None, "message": "排队时长接口未启用"}

    url = (config.get("wait_time_url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="未配置排队时长接口地址")

    headers = {}
    token = (config.get("wait_time_token") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"排队时长接口请求失败: {exc}") from exc


@router.get("/dashboard/weather")
def proxy_weather(
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    db: Session = Depends(get_db),
):
    config = _load_integrations(db)
    if not config.get("weather_enabled", True):
        return {"success": True, "data": None, "message": "天气接口未启用"}

    api_key = (config.get("weather_api_key") or "").strip()
    api_url = (config.get("weather_api_url") or DEFAULT_INTEGRATIONS["weather_api_url"]).strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="未配置天气 API Key")

    use_lat = lat if lat is not None else float(config.get("weather_default_lat", 39.9042))
    use_lon = lon if lon is not None else float(config.get("weather_default_lon", 116.4074))
    location = f"{use_lat}:{use_lon}"

    try:
        response = requests.get(
            api_url,
            params={
                "key": api_key,
                "location": location,
                "language": "zh-Hans",
                "unit": "c",
            },
            timeout=10,
        )
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"天气接口请求失败: {exc}") from exc
