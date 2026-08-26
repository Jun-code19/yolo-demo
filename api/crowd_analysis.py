from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from pydantic import BaseModel, field_validator, model_validator
from datetime import datetime
import uuid
import logging
import re

from src.database import get_db, DetectionConfig, Device, DeviceGroup, CrowdAnalysisJob, DetectionModel, CrowdAnalysisResult
from src.crowd_analyzer import crowd_analyzer
from src.crowd_job_utils import build_crowd_job_response, snapshot_group_devices, resolve_crowd_job_devices
from api.auth import get_current_user, User
from api.logger import log_action
# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/crowd-analysis", tags=["人群分析"])

DEFAULT_GROUP_SETTINGS = {
    "frame_source_primary": "snapshot",
    "frame_source_fallback": "rtsp",
    "device_interval_sec": 1.0,
}


def _normalize_group_settings(settings: Optional[Dict]) -> Dict:
    merged = {**DEFAULT_GROUP_SETTINGS, **(settings or {})}
    return merged


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
        device_ids = payload.get("device_ids") or []
        for device_id in device_ids:
            device = db.query(Device).filter(Device.device_id == device_id).first()
            if not device:
                raise HTTPException(status_code=404, detail=f"设备不存在: {device_id}")
    return payload

# Pydantic模型
class LocationInfo(BaseModel):
    name: str
    coordinates: Optional[List[float]] = None
    address: Optional[str] = None
    area_code: Optional[str] = None

class AnalysisJobCreate(BaseModel):
    job_name: str
    device_mode: Optional[str] = "manual"  # manual | group
    group_id: Optional[str] = None
    group_settings: Optional[Dict] = None
    schedule_config: Optional[Dict] = None
    device_ids: Optional[List[str]] = None
    models_id: str  # 指定分析任务使用的模型ID
    interval: Optional[int] = 300  # 默认5分钟
    cron_expression: Optional[str] = None
    tags: Optional[List[str]] = ["crowd_analysis"]
    location_info: Optional[LocationInfo] = None
    description: Optional[str] = None
    detect_classes: Optional[List[str]] = None
    confidence_threshold: Optional[float] = 0.5  # 置信度阈值，默认0.5
    warning_threshold: Optional[int] = 0
    warning_message: Optional[str] = None
    
    @field_validator('job_name')
    @classmethod
    def validate_job_name(cls, v):
        if not v or not v.strip():
            raise ValueError("任务名称不能为空")
        if len(v) > 100:
            raise ValueError("任务名称过长，请控制在100个字符以内")
        return v

    @field_validator('confidence_threshold')
    @classmethod
    def validate_confidence_threshold(cls, v):
        if v is not None and (v < 0.1 or v > 1.0):
            raise ValueError("置信度阈值必须在0.1到1.0之间")
        return v

    @field_validator('cron_expression')
    @classmethod
    def validate_cron_expression(cls, v):
        if v is not None and v.strip():
            cron_pattern = (
                r'^(\*|[0-9,\-\/]+)\s+(\*|[0-9,\-\/]+)\s+(\*|[0-9,\-\/]+)\s+'
                r'(\*|[0-9,\-\/]+)\s+(\*|[0-9,\-\/]+)$'
            )
            if not re.match(cron_pattern, v):
                raise ValueError("无效的CRON表达式格式，正确格式如: */30 * * * *")
        return v

    @model_validator(mode='after')
    def validate_job_config(self):
        mode = self.device_mode or "manual"
        if mode == "group":
            if not self.group_id:
                raise ValueError("按分组模式需选择设备分组")
        elif not self.device_ids:
            raise ValueError("请至少选择一个监控设备")

        if not self.cron_expression:
            if self.interval is None:
                raise ValueError("请设置执行间隔")
            if self.interval < 60:
                raise ValueError("执行间隔不能小于60秒")
        return self

class AnalysisJobUpdate(BaseModel):
    job_name: Optional[str] = None
    device_mode: Optional[str] = None
    group_id: Optional[str] = None
    group_settings: Optional[Dict] = None
    schedule_config: Optional[Dict] = None
    device_ids: Optional[List[str]] = None
    models_id: Optional[str] = None
    interval: Optional[int] = None
    cron_expression: Optional[str] = None
    tags: Optional[List[str]] = None
    location_info: Optional[LocationInfo] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    detect_classes: Optional[List[str]] = None
    confidence_threshold: Optional[float] = None
    warning_threshold: Optional[int] = None
    warning_message: Optional[str] = None

class AnalysisJobResponse(BaseModel):
    job_id: str
    job_name: str
    device_mode: Optional[str] = "manual"
    group_id: Optional[str] = None
    group_settings: Optional[Dict] = None
    schedule_config: Optional[Dict] = None
    device_ids: List[str]
    models_id: str
    detect_classes: List[str]
    confidence_threshold: float
    interval: int
    cron_expression: Optional[str]
    tags: List[str]
    location_info: Dict
    description: Optional[str]
    warning_threshold: Optional[int] = 0
    warning_message: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_run: Optional[datetime]
    status: str
    last_result: Optional[Dict] = None
    last_error: Optional[str] = None

@router.post("/jobs", response_model=AnalysisJobResponse)
async def create_analysis_job(
    job_data: AnalysisJobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新的人群分析任务并保存到数据库"""
    payload = job_data.model_dump()
    payload = _apply_device_source(db, payload)

    # 验证模型ID是否存在
    model = db.query(DetectionModel).filter(DetectionModel.models_id == job_data.models_id).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"模型不存在: {job_data.models_id}")
    
    # 验证模型是否可用
    if not model.is_active:
        raise HTTPException(status_code=400, detail=f"模型 {model.models_name} 当前不可用")
    
    # 验证cron和interval的一致性
    if job_data.cron_expression and job_data.interval != 300:
        # 如果同时提供了cron表达式和非默认的interval，给出警告
        logger.warning(f"创建任务时同时提供了cron表达式和interval，将优先使用cron表达式: {job_data.cron_expression}")

    # 生成任务ID
    job_id = str(uuid.uuid4())
    
    # 准备数据库模型
    db_job = CrowdAnalysisJob(
        job_id=job_id,
        job_name=job_data.job_name,
        device_mode=payload.get("device_mode") or "manual",
        group_id=payload.get("group_id"),
        group_settings=_normalize_group_settings(payload.get("group_settings")),
        schedule_config=payload.get("schedule_config") or {},
        device_ids=payload.get("device_ids") or [],
        models_id=job_data.models_id,
        interval=job_data.interval if job_data.cron_expression is None else None,
        cron_expression=job_data.cron_expression,
        tags=job_data.tags,
        location_info=job_data.location_info.model_dump() if job_data.location_info else {},
        description=job_data.description,
        created_at=datetime.now(),
        is_active=False,
        detect_classes=job_data.detect_classes,
        confidence_threshold=job_data.confidence_threshold,
        warning_threshold=job_data.warning_threshold or 0,
        warning_message=job_data.warning_message,
    )
    
    try:
        # 保存到数据库
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
              
        # 记录创建操作
        log_action(db, current_user.user_id, 'create_crowd_task', job_id, f"创建人群分析任务: {job_data.job_name}")

        return build_crowd_job_response(db_job)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建分析任务失败: {str(e)}")

@router.get("/jobs")
async def get_analysis_jobs(
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db)
):
    """获取人群分析任务列表（分页）"""
    # 从内存中获取运行中的任务
    memory_jobs = crowd_analyzer.get_analysis_jobs()
    memory_jobs_dict = {job.get("job_id"): job for job in memory_jobs}
    
    # 查询总数
    total_count = db.query(CrowdAnalysisJob).count()
    
    # 计算分页
    skip = (page - 1) * page_size
    
    # 从数据库获取分页任务
    db_jobs = db.query(CrowdAnalysisJob).order_by(CrowdAnalysisJob.created_at.desc()).offset(skip).limit(page_size).all()
    
    # 转换为响应格式
    responses = []
    for db_job in db_jobs:
        memory_job = memory_jobs_dict.get(db_job.job_id)
        responses.append(build_crowd_job_response(db_job, memory_job))
    
    return {
        "data": responses,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": (total_count + page_size - 1) // page_size
    }

@router.get("/jobs/{job_id}", response_model=AnalysisJobResponse)
async def get_analysis_job(
    job_id: str,
    db: Session = Depends(get_db)
):
    """获取特定分析任务的详情"""
    memory_jobs = crowd_analyzer.get_analysis_jobs()
    memory_job = next((j for j in memory_jobs if j.get("job_id") == job_id), None)

    db_job = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.job_id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail=f"分析任务不存在: {job_id}")

    return build_crowd_job_response(db_job, memory_job)

@router.delete("/jobs/{job_id}/delete")
async def delete_analysis_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除分析任务"""
    # 检查任务是否存在
    db_job = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.job_id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail=f"分析任务不存在: {job_id}")
    
    try:
        # 1. 从运行时服务中移除任务
        crowd_analyzer.remove_analysis_job(job_id)
        
        # 2. 删除相关的分析结果
        db.query(CrowdAnalysisResult).filter(CrowdAnalysisResult.job_id == job_id).delete()
        
        # 3. 删除任务本身
        db.delete(db_job)
        db.commit()
        
        # 记录删除操作
        log_action(db, current_user.user_id, 'delete_crowd_task', job_id, f"删除人群分析任务: {job_id}")

        return {"status": "success", "message": f"分析任务及相关数据已删除: {job_id}"}
    except Exception as e:
        db.rollback()
        logger.error(f"删除分析任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除分析任务失败: {str(e)}")

@router.post("/jobs/{job_id}/run")
async def run_analysis_job_now(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """立即执行分析任务"""
    db_job = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.job_id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail=f"分析任务不存在: {job_id}")

    device_ids = resolve_crowd_job_devices(db, db_job)
    unavailable_devices = []
    for device_id in device_ids:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if not device or not device.status:
            unavailable_devices.append(device_id)

    if unavailable_devices and len(unavailable_devices) == len(device_ids):
        return {
            "status": "error",
            "message": f"无法执行任务，所有设备不可用: {', '.join(unavailable_devices)}",
        }

    model = db.query(DetectionModel).filter(DetectionModel.models_id == db_job.models_id).first()
    if not model:
        return {
            "status": "error",
            "message": f"任务使用的模型不可用: {db_job.models_id}",
        }

    log_action(db, current_user.user_id, 'run_crowd_task', job_id, f"立即执行人群分析任务: {job_id}")
    logger.info(f"开始执行人群分析任务: {job_id}")

    background_tasks.add_task(crowd_analyzer._run_analysis, job_id, True)
    return {"status": "success", "message": f"分析任务已开始执行: {job_id}"}

@router.get("/available-devices")
async def get_available_devices(
    db: Session = Depends(get_db)
):
    """获取可用于人群分析的设备列表"""
    # 查询所有有效的设备（必须有检测配置）
    # devices = db.query(Device).join(
    #     DetectionConfig, Device.device_id == DetectionConfig.device_id
    # ).all()
    devices = db.query(Device).all()

    available_devices = []

    for device in devices:
        available_devices.append({
            "device_id": device.device_id,
            "device_name": device.device_name,
            "location": device.location or "",
            "area": device.area or ""
        })
    
    return available_devices

@router.post("/jobs/{job_id}/pause")
async def pause_analysis_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """暂停分析任务"""
    job = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"分析任务不存在: {job_id}")
    
    job.is_active = False
    db.commit()
    
    # 记录暂停操作
    log_action(db, current_user.user_id, 'pause_crowd_task', job_id, f"暂停人群分析任务: {job_id}")

    # 从运行时服务中移除
    result = crowd_analyzer.remove_analysis_job(job_id)
    
    return {"status": "success", "message": f"分析任务已暂停: {job_id}"}

@router.post("/jobs/{job_id}/resume")
async def resume_analysis_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """恢复分析任务"""
    job = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"分析任务不存在: {job_id}")
    
    job.is_active = True
    db.commit()
    
    # 记录恢复操作
    log_action(db, current_user.user_id, 'resume_crowd_task', job_id, f"恢复人群分析任务: {job_id}")

    # 重新添加到运行时服务
    crowd_analyzer.add_analysis_job(job.job_id)
    
    return {"status": "success", "message": f"分析任务已恢复: {job_id}"}

@router.get("/jobs/{job_id}/export")
async def export_analysis_results(
    job_id: str,
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """导出分析结果数据（最近n天）"""
    job = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"分析任务不存在: {job_id}")
    
    # 记录导出操作
    log_action(db, current_user.user_id, 'export_crowd_results', job_id, f"导出人群分析结果: {job_id}")

    # 这里可以实现查询分析结果历史记录的逻辑
    # 可能需要另外一个表来存储历史分析结果
    return {"status": "success", "data": { "job_name": job.job_name, "results": [] }}

@router.get("/available-models")
async def get_available_models(
    db: Session = Depends(get_db)
):
    """获取可用于人群分析的模型列表"""
    # 人群分析使用 YOLO 等检测模型，排除 VLM 大模型
    models = db.query(DetectionModel).filter(DetectionModel.models_type != "vlm").all()

    available_models = []

    for model in models:
        available_models.append({
            "model_id": model.models_id,
            "model_name": model.models_name,
            "model_type": model.models_type,
            "description": model.description or "",
            "is_active": model.is_active
        })
    
    return available_models

@router.get("/info-devices")
async def get_devices_details(
    device_ids: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取设备详情，可以通过device_ids查询参数过滤设备列表"""
    query = db.query(Device)
    
    if device_ids:
        # 将逗号分隔的字符串拆分为列表
        device_id_list = device_ids.split(',')
        query = query.filter(Device.device_id.in_(device_id_list))
    
    devices = query.all()
    
    devices_details = []
    for device in devices:
        devices_details.append({
            "device_id": device.device_id,
            "device_name": device.device_name,
            "ip_address": device.ip_address,
            "port": device.port,
            "channel": device.channel,
            "location": device.location or "",
            "area": device.area or "",
            "status": "online" if device.status else "offline"
        })
    
    return devices_details

@router.get("/jobs/{job_id}/history")
async def get_analysis_history(
    job_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取分析任务的历史数据，用于展示趋势图"""
    # 检查任务是否存在
    job = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"分析任务不存在: {job_id}")
    
    # 构建查询
    query = db.query(CrowdAnalysisResult).filter(CrowdAnalysisResult.job_id == job_id)
    
    # 添加日期过滤
    if start_date:
        try:
            start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(CrowdAnalysisResult.timestamp >= start_datetime)
        except ValueError:
            logger.warning(f"无效的开始日期格式: {start_date}")
    
    if end_date:
        try:
            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(CrowdAnalysisResult.timestamp <= end_datetime)
        except ValueError:
            logger.warning(f"无效的结束日期格式: {end_date}")
    
    # 按时间排序
    query = query.order_by(CrowdAnalysisResult.timestamp)
    
    # 获取结果
    results = query.all()
    
    # 格式化响应
    response_data = []
    for result in results:
        # 提取主要数据点
        data_point = {
            "timestamp": result.timestamp.isoformat(),
            "total_person_count": result.total_person_count,
            "camera_counts": []
        }
        
        # 添加各摄像头的数据
        if result.camera_counts:
            for camera in result.camera_counts:
                data_point["camera_counts"].append({
                    "device_id": camera.get("device_id"),
                    "device_name": camera.get("device_name"),
                    "person_count": camera.get("person_count", 0)
                })
        
        response_data.append(data_point)
    
    return {
        "job_id": job_id,
        "job_name": job.job_name,
        "data_points": response_data
    }

@router.put("/jobs/{job_id}", response_model=AnalysisJobResponse)
async def update_analysis_job(
    job_id: str,
    job_data: AnalysisJobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新现有的人群分析任务"""
    # 检查任务是否存在
    db_job = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.job_id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail=f"分析任务不存在: {job_id}")
    
    # 验证设备/分组
    update_data = job_data.model_dump(exclude_unset=True)
    if any(key in update_data for key in ("device_mode", "group_id", "device_ids")):
        merged = {
            "device_mode": update_data.get("device_mode", db_job.device_mode or "manual"),
            "group_id": update_data.get("group_id", db_job.group_id),
            "device_ids": update_data.get("device_ids", db_job.device_ids),
        }
        merged = _apply_device_source(db, merged)
        update_data["device_mode"] = merged["device_mode"]
        update_data["group_id"] = merged["group_id"]
        update_data["device_ids"] = merged["device_ids"]

    if "group_settings" in update_data and update_data["group_settings"] is not None:
        update_data["group_settings"] = _normalize_group_settings(update_data["group_settings"])
    
    # 验证模型ID是否存在
    if job_data.models_id:
        model = db.query(DetectionModel).filter(DetectionModel.models_id == job_data.models_id).first()
        if not model:
            raise HTTPException(status_code=404, detail=f"模型不存在: {job_data.models_id}")
        
        # 验证模型是否可用
        if not model.is_active:
            raise HTTPException(status_code=400, detail=f"模型 {model.models_name} 当前不可用")
    
    # 验证 cron 和 interval 的一致性
    if job_data.cron_expression is not None and job_data.interval is not None:
        logger.warning(
            f"更新任务时同时提供了cron表达式和interval，将优先使用cron表达式: {job_data.cron_expression}"
        )
        update_data["interval"] = None

    is_active_changed = False
    was_active = db_job.is_active

    if 'location_info' in update_data and update_data['location_info']:
        if isinstance(update_data['location_info'], LocationInfo):
            update_data['location_info'] = update_data['location_info'].model_dump()

    for key, value in update_data.items():
        if key == 'is_active' and value != was_active:
            is_active_changed = True
        setattr(db_job, key, value)
    
    try:
        db.commit()
        db.refresh(db_job)
        
        # 记录更新操作
        log_action(db, current_user.user_id, 'update_crowd_task', job_id, f"更新人群分析任务: {job_id}")

        # 如果激活状态改变，需要特殊处理
        if is_active_changed:
            if db_job.is_active:
                crowd_analyzer.add_analysis_job(db_job.job_id)
            else:
                crowd_analyzer.remove_analysis_job(job_id)
        elif db_job.is_active:
            crowd_analyzer.remove_analysis_job(job_id)
            crowd_analyzer.add_analysis_job(db_job.job_id)

        memory_jobs = crowd_analyzer.get_analysis_jobs()
        memory_job = next((j for j in memory_jobs if j.get("job_id") == job_id), None)
        return build_crowd_job_response(db_job, memory_job)
    except Exception as e:
        db.rollback()
        logger.error(f"更新分析任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新分析任务失败: {str(e)}")

@router.get("/model-classes/{model_id}")
async def get_model_classes(
    model_id: str,
    db: Session = Depends(get_db)
):
    """获取特定模型支持的类别信息"""
    model = db.query(DetectionModel).filter(DetectionModel.models_id == model_id, DetectionModel.is_active == True).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"模型不存在: {model_id}")
    
    # 返回模型类别信息
    if model.models_classes:
        return {"model_id": model_id, "classes": model.models_classes}
    else:
        # 如果模型没有保存类别信息，返回空列表
        return {"model_id": model_id, "classes": []}