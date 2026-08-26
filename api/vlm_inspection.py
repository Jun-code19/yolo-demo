from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from datetime import datetime
import uuid
import logging
import cv2
import numpy as np

from src.database import get_db, Device, DeviceGroup, DetectionModel, VlmInspectionJob, VlmInspectionRun, VlmInspectionFinding, VlmInspectionAlertCooldown
from src.vlm_inspection_engine import vlm_inspection_engine
from src.vlm_inspection_job_utils import (
    build_inspection_job_response,
    build_inspection_run_response,
    normalize_group_settings,
    normalize_vlm_config,
    snapshot_group_devices,
)
from src.inference_pipeline.providers.qwen_vl import is_api_key_configured
from src.inference_pipeline.payload_builder import load_prompt_registry
from src.inference_pipeline.vlm_only_stage import run_vlm_only_inspection
from api.auth import get_current_user, User
from api.logger import log_action

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vlm-inspection", tags=["VLM巡检"])

DEFAULT_GROUP_SETTINGS = {
    "frame_source_primary": "snapshot",
    "frame_source_fallback": "rtsp",
    "device_interval_sec": 1.0,
}


def _normalize_group_settings(settings: Optional[Dict]) -> Dict:
    return normalize_group_settings(settings)


def _apply_device_source(db: Session, payload: Dict) -> Dict:
    mode = payload.get("device_mode") or "manual"
    if mode == "group":
        group_id = payload.get("group_id")
        group = db.query(DeviceGroup).filter(DeviceGroup.group_id == group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail=f"设备分组不存在: {group_id}")
        payload["device_ids"] = snapshot_group_devices(db, group_id)
        payload["group_id"] = group_id
    else:
        payload["group_id"] = None
        for device_id in payload.get("device_ids") or []:
            device = db.query(Device).filter(Device.device_id == device_id).first()
            if not device:
                raise HTTPException(status_code=404, detail=f"设备不存在: {device_id}")
    return payload


class InspectionJobCreate(BaseModel):
    job_name: str
    device_mode: Optional[str] = "manual"
    group_id: Optional[str] = None
    group_settings: Optional[Dict] = None
    schedule_config: Optional[Dict] = None
    device_ids: Optional[List[str]] = None
    vlm_model_id: str
    prompt_id: Optional[str] = "general_patrol_v1"
    prompt_override: Optional[str] = None
    vlm_config: Optional[Dict] = None
    alert_labels: Optional[List[str]] = None
    min_confidence: Optional[float] = 0.7
    interval: Optional[int] = 300
    tags: Optional[List[str]] = None
    description: Optional[str] = None

    @field_validator("job_name")
    @classmethod
    def validate_job_name(cls, v):
        if not v or not v.strip():
            raise ValueError("任务名称不能为空")
        return v.strip()

    @model_validator(mode="after")
    def validate_devices(self):
        if self.device_mode == "group":
            if not self.group_id:
                raise ValueError("按分组模式必须选择设备分组")
        elif not self.device_ids:
            raise ValueError("请至少选择一个监控设备")
        return self


class InspectionJobUpdate(BaseModel):
    job_name: Optional[str] = None
    device_mode: Optional[str] = None
    group_id: Optional[str] = None
    group_settings: Optional[Dict] = None
    schedule_config: Optional[Dict] = None
    device_ids: Optional[List[str]] = None
    vlm_model_id: Optional[str] = None
    prompt_id: Optional[str] = None
    prompt_override: Optional[str] = None
    vlm_config: Optional[Dict] = None
    alert_labels: Optional[List[str]] = None
    min_confidence: Optional[float] = None
    interval: Optional[int] = None
    tags: Optional[List[str]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


def _validate_vlm_model(db: Session, model_id: str) -> DetectionModel:
    model = db.query(DetectionModel).filter(DetectionModel.models_id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"VLM 模型不存在: {model_id}")
    if model.models_type != "vlm":
        raise HTTPException(status_code=400, detail="所选模型不是 VLM 类型，请在模型管理中注册 models_type=vlm")
    if not model.is_active:
        raise HTTPException(status_code=400, detail=f"模型 {model.models_name} 当前不可用")
    params = model.parameters or {}
    if not _infer_supports_vision(params.get("base_url") or "", params.get("supports_vision")):
        raise HTTPException(status_code=400, detail=_vision_unsupported_message(params.get("base_url") or ""))
    return model


class BootstrapQwenBody(BaseModel):
    api_key: Optional[str] = None


class VlmModelCredentials(BaseModel):
    api_key: str

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v):
        if not v or not v.strip():
            raise ValueError("API Key 不能为空")
        return v.strip()


VLM_PROVIDER_PRESETS = [
    {
        "id": "dashscope_qwen",
        "name": "阿里云 DashScope（通义千问 VL）",
        "provider": "qwen_vl",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model_name": "qwen-vl-plus",
        "api_key_required": True,
        "supports_vision": True,
        "api_key_hint": "DashScope Key，或填 env:DASHSCOPE_API_KEY",
    },
    {
        "id": "dashscope_qwen_max",
        "name": "阿里云 DashScope（qwen-vl-max）",
        "provider": "qwen_vl",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model_name": "qwen-vl-max",
        "api_key_required": True,
        "supports_vision": True,
        "api_key_hint": "DashScope Key",
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "provider": "openai_compatible",
        "base_url": "https://api.openai.com/v1",
        "model_name": "gpt-4o",
        "api_key_required": True,
        "supports_vision": True,
        "api_key_hint": "OpenAI API Key",
    },
    {
        "id": "zhipu",
        "name": "智谱 AI",
        "provider": "openai_compatible",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model_name": "glm-4v",
        "api_key_required": True,
        "supports_vision": True,
        "api_key_hint": "智谱 API Key",
    },
    {
        "id": "ollama",
        "name": "Ollama（本地）",
        "provider": "openai_compatible",
        "base_url": "http://127.0.0.1:11434/v1",
        "model_name": "llava",
        "api_key_required": False,
        "supports_vision": True,
        "api_key_hint": "本地一般无需 Key，需拉取 llava 等视觉模型",
    },
    {
        "id": "custom",
        "name": "自定义 OpenAI 兼容接口",
        "provider": "openai_compatible",
        "base_url": "",
        "model_name": "",
        "api_key_required": True,
        "supports_vision": True,
        "api_key_hint": "须支持 chat/completions + image_url 多模态；DeepSeek 官方 API 不支持传图",
    },
]


def _infer_supports_vision(base_url: str, explicit: Optional[bool] = None) -> bool:
    if explicit is False:
        return False
    base = (base_url or "").lower()
    # DeepSeek 官方托管 API 仅文本，不接受 image_url
    if "deepseek.com" in base:
        return False
    return True


def _vision_unsupported_message(base_url: str) -> str:
    if "deepseek.com" in (base_url or "").lower():
        return (
            "DeepSeek 官方 API（deepseek-chat / deepseek-v4 等）仅支持纯文本，不支持 image_url 传图。"
            "VLM 巡检请改用 Qwen-VL、GPT-4o、GLM-4V 或本地 Ollama（llava）等视觉模型。"
        )
    return "该接口不支持多模态 image_url 传图，请更换支持视觉的 VLM 模型。"


class VlmModelCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    models_name: str
    provider: str = "openai_compatible"
    base_url: str
    model_name: str
    api_key: Optional[str] = None
    description: Optional[str] = None
    temperature: Optional[float] = 0.2
    timeout_sec: Optional[int] = 60
    api_key_required: Optional[bool] = True
    supports_vision: Optional[bool] = True

    @field_validator("models_name", "base_url", "model_name")
    @classmethod
    def strip_required(cls, v):
        if v is None:
            return v
        s = str(v).strip()
        if not s:
            raise ValueError("不能为空")
        return s


class VlmModelUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    models_name: Optional[str] = None
    provider: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    description: Optional[str] = None
    temperature: Optional[float] = None
    timeout_sec: Optional[int] = None
    api_key_required: Optional[bool] = None
    supports_vision: Optional[bool] = None
    is_active: Optional[bool] = None


def _build_vlm_parameters(body: Dict) -> Dict:
    api_key_required = body.get("api_key_required", True)
    base_url = body["base_url"].rstrip("/")
    supports_vision = _infer_supports_vision(base_url, body.get("supports_vision"))
    if not supports_vision:
        raise HTTPException(status_code=400, detail=_vision_unsupported_message(base_url))

    api_key = (body.get("api_key") or "").strip()
    if not api_key and api_key_required is not False:
        api_key = "env:DASHSCOPE_API_KEY"
    params = {
        "engine": "vlm",
        "provider": (body.get("provider") or "openai_compatible").strip(),
        "base_url": body["base_url"].rstrip("/"),
        "model_name": body["model_name"],
        "api_key": api_key,
        "timeout_sec": int(body.get("timeout_sec") or 60),
        "temperature": float(body.get("temperature") if body.get("temperature") is not None else 0.2),
        "api_key_required": api_key_required is not False,
        "supports_vision": supports_vision,
    }
    return params


def _vlm_model_to_dict(model: DetectionModel) -> Dict:
    params = model.parameters or {}
    safe_params = {k: v for k, v in params.items() if k != "api_key"}
    return {
        "model_id": model.models_id,
        "models_name": model.models_name,
        "description": model.description,
        "is_active": model.is_active,
        "api_key_configured": is_api_key_configured(params),
        "parameters": safe_params,
        "upload_time": model.upload_time.isoformat() if model.upload_time else None,
    }


@router.post("/bootstrap-qwen-model")
async def bootstrap_qwen_vlm_model(
    body: Optional[BootstrapQwenBody] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """注册默认 Qwen-VL 模型（若尚不存在），可选传入 api_key"""
    api_key = (body.api_key if body else None) or None
    existing = (
        db.query(DetectionModel)
        .filter(DetectionModel.models_type == "vlm", DetectionModel.models_name == "qwen-vl-plus")
        .first()
    )
    if existing:
        if api_key:
            params = dict(existing.parameters or {})
            params["api_key"] = api_key
            existing.parameters = params
            db.commit()
            log_action(db, current_user.user_id, "update_vlm_api_key", existing.models_id, "更新 Qwen-VL API Key")
            return {
                "status": "updated",
                "model_id": existing.models_id,
                "api_key_configured": True,
                "message": "API Key 已保存",
            }
        configured = is_api_key_configured(existing.parameters)
        return {
            "status": "exists",
            "model_id": existing.models_id,
            "api_key_configured": configured,
            "message": "Qwen-VL 模型已存在" + ("" if configured else "，请配置 API Key"),
        }

    parameters = {
        "engine": "vlm",
        "provider": "qwen_vl",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model_name": "qwen-vl-plus",
        "api_key": api_key if api_key else "env:DASHSCOPE_API_KEY",
        "timeout_sec": 60,
        "temperature": 0.2,
    }
    model_id = str(uuid.uuid4())
    db_model = DetectionModel(
        models_id=model_id,
        models_name="qwen-vl-plus",
        models_type="vlm",
        file_path="remote://dashscope/qwen-vl-plus",
        file_size=0,
        format="api",
        description="通义千问 Qwen-VL（DashScope OpenAI 兼容接口）",
        parameters=parameters,
        is_active=True,
        is_gpu=False,
    )
    db.add(db_model)
    db.commit()
    log_action(db, current_user.user_id, "bootstrap_qwen_vlm", model_id, "注册 Qwen-VL 模型")
    configured = is_api_key_configured(parameters)
    return {
        "status": "created",
        "model_id": model_id,
        "api_key_configured": configured,
        "message": "Qwen-VL 模型已注册" + ("" if configured else "，请配置 DASHSCOPE_API_KEY 或在界面填写 API Key"),
    }


@router.get("/vlm-providers")
async def list_vlm_providers():
    """OpenAI 兼容 VLM 接入预设"""
    return VLM_PROVIDER_PRESETS


@router.get("/vlm-models")
async def list_vlm_models(db: Session = Depends(get_db)):
    """列出全部 VLM 模型（含未激活）"""
    models = (
        db.query(DetectionModel)
        .filter(DetectionModel.models_type == "vlm")
        .order_by(DetectionModel.upload_time.desc())
        .all()
    )
    return [_vlm_model_to_dict(m) for m in models]


@router.post("/vlm-models")
async def create_vlm_model(
    body: VlmModelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """注册自定义 OpenAI 兼容 VLM"""
    model_id = str(uuid.uuid4())
    parameters = _build_vlm_parameters(body.model_dump())

    db_model = DetectionModel(
        models_id=model_id,
        models_name=body.models_name,
        models_type="vlm",
        file_path=f"remote://vlm/{body.provider}/{body.model_name}",
        file_size=0,
        format="api",
        description=body.description or f"OpenAI 兼容 VLM · {body.model_name}",
        parameters=parameters,
        is_active=True,
        is_gpu=False,
    )
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    log_action(db, current_user.user_id, "create_vlm_model", model_id, f"注册 VLM: {body.models_name}")
    return {
        "status": "created",
        "model": _vlm_model_to_dict(db_model),
        "message": "VLM 模型已注册",
    }


@router.put("/vlm-models/{model_id}")
async def update_vlm_model(
    model_id: str,
    body: VlmModelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = db.query(DetectionModel).filter(DetectionModel.models_id == model_id).first()
    if not model or model.models_type != "vlm":
        raise HTTPException(status_code=404, detail="VLM 模型不存在")

    params = dict(model.parameters or {})
    data = body.model_dump(exclude_unset=True)

    if "models_name" in data and data["models_name"]:
        model.models_name = data["models_name"].strip()
    if "description" in data:
        model.description = data["description"]
    if "is_active" in data:
        model.is_active = data["is_active"]

    for key in ("provider", "base_url", "model_name", "temperature", "timeout_sec", "api_key_required", "supports_vision"):
        if key in data and data[key] is not None:
            if key == "base_url":
                params["base_url"] = str(data[key]).rstrip("/")
            elif key == "api_key_required":
                params["api_key_required"] = data[key] is not False
            elif key == "supports_vision":
                params["supports_vision"] = data[key] is not False
            else:
                params[key] = data[key]

    base_url = params.get("base_url") or ""
    if not _infer_supports_vision(base_url, params.get("supports_vision")):
        raise HTTPException(status_code=400, detail=_vision_unsupported_message(base_url))
    params["supports_vision"] = _infer_supports_vision(base_url, params.get("supports_vision"))

    if "api_key" in data and data["api_key"] and str(data["api_key"]).strip():
        params["api_key"] = str(data["api_key"]).strip()

    model.parameters = params
    db.commit()
    db.refresh(model)
    log_action(db, current_user.user_id, "update_vlm_model", model_id, f"更新 VLM: {model.models_name}")
    return {"status": "success", "model": _vlm_model_to_dict(model)}


@router.delete("/vlm-models/{model_id}")
async def delete_vlm_model(
    model_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = db.query(DetectionModel).filter(DetectionModel.models_id == model_id).first()
    if not model or model.models_type != "vlm":
        raise HTTPException(status_code=404, detail="VLM 模型不存在")

    job_count = db.query(VlmInspectionJob).filter(VlmInspectionJob.vlm_model_id == model_id).count()
    if job_count:
        raise HTTPException(status_code=400, detail=f"仍有 {job_count} 个 VLM 巡检任务使用该模型，请先修改或删除任务")

    db.delete(model)
    db.commit()
    log_action(db, current_user.user_id, "delete_vlm_model", model_id, f"删除 VLM: {model.models_name}")
    return {"status": "success", "message": "VLM 模型已删除"}


@router.put("/vlm-models/{model_id}/credentials")
async def update_vlm_model_credentials(
    model_id: str,
    body: VlmModelCredentials,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = _validate_vlm_model(db, model_id)
    params = dict(model.parameters or {})
    params["api_key"] = body.api_key
    model.parameters = params
    db.commit()
    log_action(db, current_user.user_id, "update_vlm_api_key", model_id, "更新 VLM API Key")
    return {"status": "success", "api_key_configured": True, "message": "API Key 已保存"}


@router.get("/vlm-models/{model_id}/credentials-status")
async def get_vlm_credentials_status(model_id: str, db: Session = Depends(get_db)):
    model = db.query(DetectionModel).filter(DetectionModel.models_id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    return {"model_id": model_id, "api_key_configured": is_api_key_configured(model.parameters)}


@router.get("/prompts")
async def list_prompts():
    registry = load_prompt_registry()
    items = []
    for prompt_id, meta in registry.items():
        items.append(
            {
                "prompt_id": prompt_id,
                "name": meta.get("name") or prompt_id,
                "description": meta.get("description") or "",
                "default_alert_labels": meta.get("default_alert_labels") or [],
            }
        )
    return items


@router.get("/available-vlm-models")
async def get_available_vlm_models(db: Session = Depends(get_db)):
    models = (
        db.query(DetectionModel)
        .filter(DetectionModel.models_type == "vlm", DetectionModel.is_active.is_(True))
        .all()
    )
    result = []
    for model in models:
        result.append(
            {
                "model_id": model.models_id,
                "model_name": model.models_name,
                "description": model.description,
                "api_key_configured": is_api_key_configured(model.parameters),
                "parameters": {
                    k: v for k, v in (model.parameters or {}).items() if k != "api_key"
                },
            }
        )
    return result


@router.get("/available-devices")
async def get_available_devices(db: Session = Depends(get_db)):
    devices = db.query(Device).filter(Device.status.is_(True)).all()
    return [
        {
            "device_id": d.device_id,
            "device_name": d.device_name,
            "location": d.location or "",
            "area": d.area or "",
        }
        for d in devices
    ]


@router.post("/jobs")
async def create_inspection_job(
    job_data: InspectionJobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validate_vlm_model(db, job_data.vlm_model_id)
    payload = _apply_device_source(db, job_data.model_dump())
    job_id = str(uuid.uuid4())

    db_job = VlmInspectionJob(
        job_id=job_id,
        job_name=job_data.job_name,
        device_mode=payload.get("device_mode") or "manual",
        group_id=payload.get("group_id"),
        group_settings=_normalize_group_settings(payload.get("group_settings")),
        schedule_config=payload.get("schedule_config") or {},
        device_ids=payload.get("device_ids") or [],
        vlm_model_id=job_data.vlm_model_id,
        prompt_id=job_data.prompt_id or "general_patrol_v1",
        prompt_override=job_data.prompt_override,
        vlm_config=normalize_vlm_config(job_data.vlm_config),
        alert_labels=job_data.alert_labels or ["fire", "fight", "fall"],
        min_confidence=job_data.min_confidence or 0.7,
        interval=job_data.interval or 300,
        tags=job_data.tags or ["vlm_inspection"],
        description=job_data.description,
        is_active=False,
        status="created",
    )
    try:
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
        log_action(db, current_user.user_id, "create_vlm_inspection", job_id, f"创建 VLM 巡检任务: {job_data.job_name}")
        return build_inspection_job_response(db_job, db=db)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建任务失败: {exc}")


@router.get("/jobs")
async def list_inspection_jobs(page: int = 1, page_size: int = 20, db: Session = Depends(get_db)):
    memory_jobs = {j["job_id"]: j for j in vlm_inspection_engine.get_inspection_jobs()}
    total = db.query(VlmInspectionJob).count()
    skip = (page - 1) * page_size
    rows = (
        db.query(VlmInspectionJob)
        .order_by(VlmInspectionJob.created_at.desc())
        .offset(skip)
        .limit(page_size)
        .all()
    )
    data = [build_inspection_job_response(row, memory_jobs.get(row.job_id), db=db) for row in rows]
    for item in data:
        item["is_running"] = vlm_inspection_engine.is_job_running(item["job_id"])
    return {
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/jobs/{job_id}")
async def get_inspection_job(job_id: str, db: Session = Depends(get_db)):
    row = db.query(VlmInspectionJob).filter(VlmInspectionJob.job_id == job_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    memory = next((j for j in vlm_inspection_engine.get_inspection_jobs() if j.get("job_id") == job_id), None)
    response = build_inspection_job_response(row, memory, db=db)
    response["is_running"] = vlm_inspection_engine.is_job_running(job_id)
    return response


@router.put("/jobs/{job_id}")
async def update_inspection_job(
    job_id: str,
    job_data: InspectionJobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_job = db.query(VlmInspectionJob).filter(VlmInspectionJob.job_id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="任务不存在")

    update_data = job_data.model_dump(exclude_unset=True)
    if "vlm_model_id" in update_data and update_data["vlm_model_id"]:
        _validate_vlm_model(db, update_data["vlm_model_id"])

    device_fields = {"device_mode", "group_id", "device_ids", "group_settings"}
    if device_fields & set(update_data.keys()):
        merged = {
            "device_mode": update_data.get("device_mode", db_job.device_mode),
            "group_id": update_data.get("group_id", db_job.group_id),
            "device_ids": update_data.get("device_ids", db_job.device_ids),
            "group_settings": update_data.get("group_settings", db_job.group_settings),
        }
        merged = _apply_device_source(db, merged)
        update_data.update(merged)

    was_active = db_job.is_active
    is_active_changed = False
    for key, value in update_data.items():
        if key == "group_settings":
            value = _normalize_group_settings(value)
        if key == "vlm_config":
            value = normalize_vlm_config(value)
        if key == "is_active" and value != was_active:
            is_active_changed = True
        setattr(db_job, key, value)

    try:
        db.commit()
        db.refresh(db_job)
        if is_active_changed:
            if db_job.is_active:
                vlm_inspection_engine.add_inspection_job(job_id)
            else:
                vlm_inspection_engine.remove_inspection_job(job_id)
        elif db_job.is_active:
            vlm_inspection_engine.remove_inspection_job(job_id)
            vlm_inspection_engine.add_inspection_job(job_id)

        log_action(db, current_user.user_id, "update_vlm_inspection", job_id, "更新 VLM 巡检任务")
        memory = next((j for j in vlm_inspection_engine.get_inspection_jobs() if j.get("job_id") == job_id), None)
        return build_inspection_job_response(db_job, memory, db=db)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新失败: {exc}")


@router.delete("/jobs/{job_id}/delete")
async def delete_inspection_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_job = db.query(VlmInspectionJob).filter(VlmInspectionJob.job_id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="任务不存在")
    try:
        vlm_inspection_engine.remove_inspection_job(job_id)
        db.query(VlmInspectionFinding).filter(VlmInspectionFinding.job_id == job_id).delete()
        db.query(VlmInspectionRun).filter(VlmInspectionRun.job_id == job_id).delete()
        db.query(VlmInspectionAlertCooldown).filter(VlmInspectionAlertCooldown.job_id == job_id).delete()
        db.delete(db_job)
        db.commit()
        log_action(db, current_user.user_id, "delete_vlm_inspection", job_id, "删除 VLM 巡检任务")
        return {"status": "success", "message": "任务已删除"}
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {exc}")


@router.post("/jobs/{job_id}/pause")
async def pause_inspection_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(VlmInspectionJob).filter(VlmInspectionJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    job.is_active = False
    job.status = "paused"
    db.commit()
    vlm_inspection_engine.remove_inspection_job(job_id)
    log_action(db, current_user.user_id, "pause_vlm_inspection", job_id, "暂停 VLM 巡检任务")
    return {"status": "success", "message": "任务已暂停"}


@router.post("/jobs/{job_id}/resume")
async def resume_inspection_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(VlmInspectionJob).filter(VlmInspectionJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    _validate_vlm_model(db, job.vlm_model_id)
    job.is_active = True
    job.status = "scheduled"
    db.commit()
    vlm_inspection_engine.add_inspection_job(job_id)
    log_action(db, current_user.user_id, "resume_vlm_inspection", job_id, "恢复 VLM 巡检任务")
    return {"status": "success", "message": "任务已恢复"}


@router.post("/jobs/{job_id}/run")
async def run_inspection_job_now(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(VlmInspectionJob).filter(VlmInspectionJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    _validate_vlm_model(db, job.vlm_model_id)
    if vlm_inspection_engine.is_job_running(job_id):
        raise HTTPException(status_code=409, detail="该任务正在执行中，请稍后再试")
    log_action(db, current_user.user_id, "run_vlm_inspection", job_id, "立即执行 VLM 巡检")
    background_tasks.add_task(vlm_inspection_engine.run_inspection, job_id, True)
    return {"status": "success", "message": "巡检任务已开始执行"}


@router.get("/jobs/{job_id}/runs")
async def list_job_runs(
    job_id: str,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    job = db.query(VlmInspectionJob).filter(VlmInspectionJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    query = db.query(VlmInspectionRun).filter(VlmInspectionRun.job_id == job_id)
    total = query.count()
    skip = (page - 1) * page_size
    rows = query.order_by(VlmInspectionRun.started_at.desc()).offset(skip).limit(page_size).all()
    return {
        "data": [build_inspection_run_response(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size else 0,
        "is_running": vlm_inspection_engine.is_job_running(job_id),
    }


@router.get("/jobs/{job_id}/findings")
async def list_job_findings(
    job_id: str,
    page: int = 1,
    page_size: int = 20,
    alerts_only: bool = False,
    db: Session = Depends(get_db),
):
    job = db.query(VlmInspectionJob).filter(VlmInspectionJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    query = db.query(VlmInspectionFinding).filter(VlmInspectionFinding.job_id == job_id)
    if alerts_only:
        query = query.filter(VlmInspectionFinding.needs_alert.is_(True))
    total = query.count()
    skip = (page - 1) * page_size
    rows = query.order_by(VlmInspectionFinding.timestamp.desc()).offset(skip).limit(page_size).all()
    devices = {d.device_id: d.device_name for d in db.query(Device).all()}
    data = []
    for row in rows:
        data.append(
            {
                "finding_id": row.finding_id,
                "run_id": row.run_id,
                "device_id": row.device_id,
                "device_name": devices.get(row.device_id, row.device_id),
                "timestamp": row.timestamp,
                "summary": row.summary,
                "findings": row.findings,
                "needs_alert": row.needs_alert,
                "alert_labels": row.alert_labels,
                "snapshot_path": row.snapshot_path,
                "latency_ms": row.latency_ms,
                "error": row.error,
            }
        )
    return {"data": data, "total": total, "page": page, "page_size": page_size}


@router.post("/test")
async def test_vlm_inspection(
    vlm_model_id: str = Form(...),
    prompt_id: str = Form("general_patrol_v1"),
    alert_labels: str = Form("fire,fight,fall"),
    min_confidence: float = Form(0.7),
    prompt_override: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = _validate_vlm_model(db, vlm_model_id)
    content = await file.read()
    arr = np.frombuffer(content, np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="无法解析上传图片")
    labels = [x.strip() for x in alert_labels.split(",") if x.strip()]
    result = run_vlm_only_inspection(
        frame=frame,
        model_record=model,
        prompt_id=prompt_id,
        alert_labels=labels,
        min_confidence=min_confidence,
        prompt_override=prompt_override,
    )
    return result
