from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, validator
from datetime import datetime
import uuid
import logging
import re

from src.database import get_db, DetectionConfig, Device, CrowdAnalysisJob, DetectionModel, CrowdAnalysisResult
from src.crowd_analyzer import crowd_analyzer
from api.auth import get_current_user, User

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/crowd-analysis", tags=["人群分析"])

# Pydantic模型
class LocationInfo(BaseModel):
    name: str
    coordinates: Optional[List[float]] = None
    address: Optional[str] = None
    area_code: Optional[str] = None

class AnalysisJobCreate(BaseModel):
    job_name: str
    device_ids: List[str]
    models_id: str  # 指定分析任务使用的模型ID
    interval: Optional[int] = 300  # 默认5分钟
    cron_expression: Optional[str] = None
    tags: Optional[List[str]] = ["crowd_analysis"]
    location_info: Optional[LocationInfo] = None
    description: Optional[str] = None
    detect_classes: Optional[List[str]] = None
    
    @validator('job_name')
    def validate_job_name(cls, v):
        if not v or not v.strip():
            raise ValueError("任务名称不能为空")
        if len(v) > 100:  
            raise ValueError("任务名称过长，请控制在100个字符以内")
        return v
    
    @validator('device_ids')
    def validate_device_ids(cls, v):
        if not v or len(v) == 0:
            raise ValueError("请至少选择一个监控设备")
        return v
    
    @validator('interval')
    def validate_interval(cls, v, values):
        if 'cron_expression' not in values or not values['cron_expression']:
            if v is None:
                raise ValueError("请设置执行间隔")
            if v < 60:
                raise ValueError("执行间隔不能小于60秒")
        return v
    
    @validator('cron_expression')
    def validate_cron_expression(cls, v, values):
        if v is not None and v.strip():
            # 简单的cron表达式验证
            cron_pattern = r'^(\*|[0-9,\-\/]+)\s+(\*|[0-9,\-\/]+)\s+(\*|[0-9,\-\/]+)\s+(\*|[0-9,\-\/]+)\s+(\*|[0-9,\-\/]+)$'
            if not re.match(cron_pattern, v):
                raise ValueError("无效的CRON表达式格式，正确格式如: */30 * * * *")
        return v

class AnalysisJobUpdate(BaseModel):
    job_name: Optional[str] = None
    device_ids: Optional[List[str]] = None
    models_id: Optional[str] = None
    interval: Optional[int] = None
    cron_expression: Optional[str] = None
    tags: Optional[List[str]] = None
    location_info: Optional[LocationInfo] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    detect_classes: Optional[List[str]] = None

class AnalysisJobResponse(BaseModel):
    job_id: str
    job_name: str
    device_ids: List[str]
    models_id: str
    detect_classes: List[str]
    interval: int
    cron_expression: Optional[str]
    tags: List[str]
    location_info: Dict
    description: Optional[str]
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
    # 验证设备ID是否存在
    for device_id in job_data.device_ids:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail=f"设备不存在: {device_id}")
            
        # 检查设备是否有检测配置 - 不再需要，因为现在使用任务指定的模型
        # 但仍然验证设备是否可用
        # if not device.status:
        #     raise HTTPException(status_code=400, detail=f"设备 {device_id} 未启用")

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
        device_ids=job_data.device_ids,
        models_id=job_data.models_id,  # 添加模型ID
        interval=job_data.interval if job_data.cron_expression is None else None,
        cron_expression=job_data.cron_expression,
        tags=job_data.tags,
        location_info=job_data.location_info.dict() if job_data.location_info else {},
        description=job_data.description,
        created_at=datetime.now(),
        is_active=False,
        detect_classes=job_data.detect_classes,
        # is_active=True
    )
    
    try:
        # 保存到数据库
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
        
        # 添加到运行时服务
        # job_details = crowd_analyzer.add_analysis_job(
        #     job_id=job_id,
        #     job_name=job_data.job_name,
        #     device_ids=job_data.device_ids,
        #     models_id=job_data.models_id,  # 添加模型ID
        #     interval=job_data.interval,
        #     cron_expression=job_data.cron_expression,
        #     tags=job_data.tags,
        #     location_info=db_job.location_info
        # )
        
        # 构建响应
        response = {
            "job_id": job_id,
            "job_name": job_data.job_name,
            "device_ids": job_data.device_ids,
            "models_id": job_data.models_id,  # 添加模型ID
            "interval": job_data.interval,
            "cron_expression": job_data.cron_expression,
            "tags": job_data.tags,
            "location_info": db_job.location_info,
            "description": job_data.description,
            "created_at": db_job.created_at,
            "is_active": db_job.is_active,
            "detect_classes": db_job.detect_classes,
            "last_run": None,
            "status": "created",
            "last_result": None,
            "last_error": None
            # "last_run": job_details.get("last_run"),
            # "status": job_details.get("status", "created"),
            # "last_result": job_details.get("last_result"),
            # "last_error": job_details.get("last_error")
        }
        
        return response
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建分析任务失败: {str(e)}")

@router.get("/jobs", response_model=List[AnalysisJobResponse])
async def get_analysis_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取所有人群分析任务"""
    # 从内存中获取运行中的任务
    memory_jobs = crowd_analyzer.get_analysis_jobs()
    memory_jobs_dict = {job.get("job_id"): job for job in memory_jobs}
    
    # 从数据库获取所有任务
    db_jobs = db.query(CrowdAnalysisJob).all()
    
    # 转换为响应格式
    responses = []
    for db_job in db_jobs:
        job_id = db_job.job_id
        # 如果任务在内存中存在，使用内存中的最新状态
        if job_id in memory_jobs_dict:
            memory_job = memory_jobs_dict[job_id]
            response = {
                "job_id": job_id,
                "job_name": db_job.job_name,
                "device_ids": db_job.device_ids,
                "models_id": db_job.models_id,
                "detect_classes": db_job.detect_classes if db_job.detect_classes else [],
                "interval": db_job.interval or 0,
                "cron_expression": db_job.cron_expression,
                "tags": db_job.tags,
                "location_info": db_job.location_info,
                "description": db_job.description,
                "created_at": db_job.created_at,
                "is_active": db_job.is_active,
                "last_run": memory_job.get("last_run"),
                "status": memory_job.get("status", "paused" if not db_job.is_active else "created"),
                "last_result": memory_job.get("last_result"),
                "last_error": memory_job.get("last_error")
            }
        else:
            # 如果任务不在内存中，使用数据库状态
            response = {
                "job_id": job_id,
                "job_name": db_job.job_name,
                "device_ids": db_job.device_ids,
                "models_id": db_job.models_id,
                "detect_classes": db_job.detect_classes if db_job.detect_classes else [],
                "interval": db_job.interval or 0,
                "cron_expression": db_job.cron_expression,
                "tags": db_job.tags,
                "location_info": db_job.location_info,
                "description": db_job.description,
                "created_at": db_job.created_at,
                "is_active": db_job.is_active,
                "last_run": None,
                "status": "paused" if not db_job.is_active else "created",
                "last_result": None,
                "last_error": None
            }
        responses.append(response)
    
    return responses

@router.get("/jobs/{job_id}", response_model=AnalysisJobResponse)
async def get_analysis_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取特定分析任务的详情"""
    # 从内存中查找任务
    memory_jobs = crowd_analyzer.get_analysis_jobs()
    memory_job = next((j for j in memory_jobs if j.get("job_id") == job_id), None)
    
    # 从数据库获取任务
    db_job = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.job_id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail=f"分析任务不存在: {job_id}")
    
    # 构建响应
    if memory_job:
        # 如果任务在内存中，合并内存和数据库信息
        response = {
            "job_id": job_id,
            "job_name": db_job.job_name,
            "device_ids": db_job.device_ids,
            "models_id": db_job.models_id,
            "detect_classes": db_job.detect_classes if db_job.detect_classes else [],
            "interval": db_job.interval or 0,
            "cron_expression": db_job.cron_expression,
            "tags": db_job.tags,
            "location_info": db_job.location_info,
            "description": db_job.description,
            "created_at": db_job.created_at,
            "is_active": db_job.is_active,
            "last_run": memory_job.get("last_run"),
            "status": memory_job.get("status", "paused" if not db_job.is_active else "created"),
            "last_result": memory_job.get("last_result"),
            "last_error": memory_job.get("last_error")
        }
    else:
        # 如果任务不在内存中，使用数据库信息
        response = {
            "job_id": job_id,
            "job_name": db_job.job_name,
            "device_ids": db_job.device_ids,
            "models_id": db_job.models_id,
            "detect_classes": db_job.detect_classes if db_job.detect_classes else [],
            "interval": db_job.interval or 0,
            "cron_expression": db_job.cron_expression,
            "tags": db_job.tags,
            "location_info": db_job.location_info,
            "description": db_job.description,
            "created_at": db_job.created_at,
            "is_active": db_job.is_active,
            "last_run": None,
            "status": "paused" if not db_job.is_active else "created",
            "last_result": None,
            "last_error": None
        }
    
    return response

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
    # 获取所有任务
    jobs = crowd_analyzer.get_analysis_jobs()
    
    # 查找对应的任务
    job = next((j for j in jobs if j.get("job_id") == job_id), None)
    if not job:
        # 检查数据库中是否存在此任务
        db_job = db.query(CrowdAnalysisJob).filter(CrowdAnalysisJob.job_id == job_id).first()
        if not db_job:
            raise HTTPException(status_code=404, detail=f"分析任务不存在: {job_id}")
        
        db_job.is_active = True
        db.commit()
        # 尝试从数据库重新加载任务
        try:
            job_details = crowd_analyzer.add_analysis_job(
                job_id=db_job.job_id,
                job_name=db_job.job_name,
                device_ids=db_job.device_ids,
                models_id=db_job.models_id,
                detect_classes=db_job.detect_classes,
                interval=db_job.interval,
                cron_expression=db_job.cron_expression,
                tags=db_job.tags,
                location_info=db_job.location_info
            )
            job = job_details
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"无法加载分析任务: {str(e)}")
    
    # 验证设备可用性
    device_ids = job.get("device_ids", [])
    unavailable_devices = []
    
    for device_id in device_ids:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if not device or not device.status:
            unavailable_devices.append(device_id)
    
    if unavailable_devices and len(unavailable_devices) == len(device_ids):
        return {
            "status": "error", 
            "message": f"无法执行任务，所有设备不可用: {', '.join(unavailable_devices)}"
        }
    
    # 验证模型可用性
    models_id = job.get("models_id")
    model = db.query(DetectionModel).filter(DetectionModel.models_id == models_id).first()
    if not model:
        return {
            "status": "error",
            "message": f"任务使用的模型不可用: {models_id}"
        }
    
    # 在后台执行任务
    logger.info(f"开始执行人群分析任务: {job_id}")
    
    # 始终在后台执行任务，避免API响应超时
    def run_job():
        crowd_analyzer._run_analysis(
            job_id, 
            job.get("device_ids", []),
            job.get("models_id"),
            job.get("tags", []), 
            job.get("location_info", {}),
            job.get("detect_classes", [])
        )
    
    background_tasks.add_task(run_job)
    return {"status": "success", "message": f"分析任务已开始执行: {job_id}"}

@router.get("/available-devices")
async def get_available_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    
    # 重新添加到运行时服务
    crowd_analyzer.add_analysis_job(
        job_id=job.job_id,
        job_name=job.job_name,
        device_ids=job.device_ids,
        models_id=job.models_id,
        detect_classes=job.detect_classes,
        interval=job.interval,
        cron_expression=job.cron_expression,
        tags=job.tags,
        location_info=job.location_info
    )
    
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
    
    # 这里可以实现查询分析结果历史记录的逻辑
    # 可能需要另外一个表来存储历史分析结果
    return {"status": "success", "data": { "job_name": job.job_name, "results": [] }}

@router.get("/available-models")
async def get_available_models(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取可用于人群分析的模型列表"""
    # 查询所有可用于人体检测的模型
    models = db.query(DetectionModel).all()

    available_models = []

    for model in models:
        available_models.append({
            "model_id": model.models_id,
            "model_name": model.models_name,
            "model_type": model.models_type,
            "description": model.description or ""
        })
    
    return available_models

@router.get("/info-devices")
async def get_devices_details(
    device_ids: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    
    # 验证设备ID是否存在
    if job_data.device_ids:
        for device_id in job_data.device_ids:
            device = db.query(Device).filter(Device.device_id == device_id).first()
            if not device:
                raise HTTPException(status_code=404, detail=f"设备不存在: {device_id}")
    
    # 验证模型ID是否存在
    if job_data.models_id:
        model = db.query(DetectionModel).filter(DetectionModel.models_id == job_data.models_id).first()
        if not model:
            raise HTTPException(status_code=404, detail=f"模型不存在: {job_data.models_id}")
        
        # 验证模型是否可用
        if not model.is_active:
            raise HTTPException(status_code=400, detail=f"模型 {model.models_name} 当前不可用")
    
    # 验证cron和interval的一致性
    if job_data.cron_expression is not None and job_data.interval is not None:
        logger.warning(f"更新任务时同时提供了cron表达式和interval，将优先使用cron表达式: {job_data.cron_expression}")
        job_data.interval = None
    
    # 更新任务信息
    is_active_changed = False
    was_active = db_job.is_active
    
    update_data = job_data.dict(exclude_unset=True)
    
    # 处理位置信息特殊情况
    if 'location_info' in update_data and update_data['location_info']:
        # 确保是字典格式
        if isinstance(update_data['location_info'], LocationInfo):
            update_data['location_info'] = update_data['location_info'].dict()
    
    # 更新数据库中的任务
    for key, value in update_data.items():
        if key == 'is_active' and value != was_active:
            is_active_changed = True
        setattr(db_job, key, value)
    
    try:
        db.commit()
        db.refresh(db_job)
        
        # 如果激活状态改变，需要特殊处理
        if is_active_changed:
            if db_job.is_active:
                # 如果从非激活变为激活，需要添加到运行时服务
                crowd_analyzer.add_analysis_job(
                    job_id=db_job.job_id,
                    job_name=db_job.job_name,
                    device_ids=db_job.device_ids,
                    models_id=db_job.models_id,
                    detect_classes=db_job.detect_classes,
                    interval=db_job.interval,
                    cron_expression=db_job.cron_expression,
                    tags=db_job.tags,
                    location_info=db_job.location_info
                )
            else:
                # 如果从激活变为非激活，需要从运行时服务中移除
                crowd_analyzer.remove_analysis_job(job_id)
        elif db_job.is_active:
            # 如果仍然是激活状态且内容有修改，需要更新运行时服务
            # 先移除原任务，再添加新任务
            crowd_analyzer.remove_analysis_job(job_id)
            crowd_analyzer.add_analysis_job(
                job_id=db_job.job_id,
                job_name=db_job.job_name,
                device_ids=db_job.device_ids,
                models_id=db_job.models_id,
                detect_classes=db_job.detect_classes,
                interval=db_job.interval,
                cron_expression=db_job.cron_expression,
                tags=db_job.tags,
                location_info=db_job.location_info
            )
        
        # 获取内存中的任务状态
        memory_jobs = crowd_analyzer.get_analysis_jobs()
        memory_job = next((j for j in memory_jobs if j.get("job_id") == job_id), None)
        
        # 构建响应
        response = {
            "job_id": job_id,
            "job_name": db_job.job_name,
            "device_ids": db_job.device_ids,
            "models_id": db_job.models_id,
            "interval": db_job.interval or 0,
            "cron_expression": db_job.cron_expression,
            "tags": db_job.tags,
            "location_info": db_job.location_info,
            "description": db_job.description,
            "created_at": db_job.created_at,
            "is_active": db_job.is_active,
            "detect_classes": db_job.detect_classes,
            "last_run": memory_job.get("last_run") if memory_job else db_job.last_run,
            "status": memory_job.get("status", "paused" if not db_job.is_active else "created") if memory_job else ("paused" if not db_job.is_active else "created"),
            "last_result": memory_job.get("last_result") if memory_job else db_job.last_result,
            "last_error": memory_job.get("last_error") if memory_job else db_job.last_error
        }
        
        return response
    except Exception as e:
        db.rollback()
        logger.error(f"更新分析任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新分析任务失败: {str(e)}")

@router.get("/model-classes/{model_id}")
async def get_model_classes(
    model_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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