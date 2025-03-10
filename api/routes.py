from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from models.database import get_db, Device, Video, AnalysisResult, Alarm, User, SysLog
from pydantic import BaseModel, IPvAnyAddress

router = APIRouter()

# Pydantic模型定义
class DeviceCreate(BaseModel):
    device_id: str
    device_name: str
    device_type: str
    ip_address: IPvAnyAddress
    port: int
    username: str
    password: str

class DeviceResponse(BaseModel):
    device_id: str
    device_name: str
    device_type: str
    ip_address: str
    port: int
    username: str
    password: str
    status: bool
    last_heartbeat: Optional[datetime]

    class Config:
        from_attributes = True

# 设备管理API
@router.post("/devices/", response_model=DeviceResponse)
def create_device(device: DeviceCreate, db: Session = Depends(get_db)):
    device_data = device.dict()
    # 将 IPv4Address 对象转换为字符串
    device_data['ip_address'] = str(device_data['ip_address'])
    db_device = Device(**device_data)
    try:
        db.add(db_device)
        db.commit()
        db.refresh(db_device)
        return db_device
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/devices/", response_model=List[DeviceResponse])
def get_devices(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    devices = db.query(Device).offset(skip).limit(limit).all()
    return devices

@router.get("/devices/{device_id}", response_model=DeviceResponse)
def get_device(device_id: str, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

@router.put("/devices/{device_id}/status")
def update_device_status(device_id: str, device_name: str, status: bool, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.device_name = device_name
    device.status = status
    device.last_heartbeat = datetime.utcnow()
    db.commit()
    return {"message": "Status updated successfully"}

@router.delete("/devices/{device_id}")
def delete_device(device_id: str, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    try:
        db.delete(device)
        db.commit()
        return {"message": "Device deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# 视频管理API
class VideoCreate(BaseModel):
    video_id: str
    device_id: str
    start_time: datetime
    storage_path: str
    resolution: Optional[str]
    frame_rate: Optional[int]

@router.post("/videos/")
def create_video(video: VideoCreate, db: Session = Depends(get_db)):
    db_video = Video(**video.dict())
    try:
        db.add(db_video)
        db.commit()
        db.refresh(db_video)
        return db_video
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/videos/{video_id}")
def get_video(video_id: str, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.video_id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

# 分析结果API
class AnalysisResultCreate(BaseModel):
    video_id: str
    target_type: str
    confidence: float
    start_frame: Optional[int]
    end_frame: Optional[int]
    meta_data: dict

@router.post("/analysis-results/")
def create_analysis_result(result: AnalysisResultCreate, db: Session = Depends(get_db)):
    db_result = AnalysisResult(**result.dict())
    try:
        db.add(db_result)
        db.commit()
        db.refresh(db_result)
        return db_result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# 报警管理API
class AlarmCreate(BaseModel):
    alarm_id: str
    event_type: str
    device_id: str
    video_id: str
    snapshot_path: Optional[str]

@router.post("/alarms/")
def create_alarm(alarm: AlarmCreate, db: Session = Depends(get_db)):
    db_alarm = Alarm(**alarm.dict())
    try:
        db.add(db_alarm)
        db.commit()
        db.refresh(db_alarm)
        return db_alarm
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/alarms/{alarm_id}/status")
def update_alarm_status(alarm_id: str, status: str, db: Session = Depends(get_db)):
    alarm = db.query(Alarm).filter(Alarm.alarm_id == alarm_id).first()
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found")
    alarm.status = status
    db.commit()
    return {"message": "Alarm status updated successfully"}

# 用户管理API
class UserCreate(BaseModel):
    user_id: str
    username: str
    password: str
    role: str
    allowed_devices: List[str]

@router.post("/users/")
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    # 这里应该添加密码哈希处理
    db_user = User(
        user_id=user.user_id,
        username=user.username,
        password_hash=user.password,  # 实际应用中需要哈希处理
        role=user.role,
        allowed_devices=user.allowed_devices
    )
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# 系统日志API
@router.get("/syslogs/")
def get_syslogs(
    skip: int = 0,
    limit: int = 100,
    user_id: Optional[str] = None,
    action_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(SysLog)
    if user_id:
        query = query.filter(SysLog.user_id == user_id)
    if action_type:
        query = query.filter(SysLog.action_type == action_type)
    return query.offset(skip).limit(limit).all() 