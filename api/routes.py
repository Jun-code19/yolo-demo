from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from models.database import get_db, Device, Video, AnalysisResult, Alarm, User, SysLog, DetectionModel, DetectionConfig, DetectionEvent, DetectionSchedule, DetectionStat, DetectionPerformance, SaveMode, EventStatus, DetectionFrequency
from pydantic import BaseModel, IPvAnyAddress, Field
from fastapi.security import OAuth2PasswordRequestForm
from api.auth import authenticate_user, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user, check_admin_permission, get_password_hash, verify_password
from api.logger import log_action
from passlib.context import CryptContext
from fastapi.responses import FileResponse,Response
import requests

import os
import shutil
import uuid
import json
from pathlib import Path
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, text, desc, and_, or_
from ultralytics import YOLO

router = APIRouter()

# Pydantic模型定义
class DeviceCreate(BaseModel):
    device_id: str
    device_name: str
    device_type: str
    ip_address: str
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

class DeviceUpdate(BaseModel):
    device_name: str
    device_type: str
    ip_address: str
    port: int
    username: str
    password: Optional[str]

# 设备管理API
@router.post("/devices/", response_model=DeviceResponse)
def create_device(device: DeviceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # 处理IP地址，将IPv4Address转换为字符串
    device_data = device.dict()
    # if isinstance(device_data['ip_address'], (str, bytes, bytearray)):
    #     device_data['ip_address'] = str(device_data['ip_address'])
    
    db_device = Device(**device_data)
    try:
        db.add(db_device)
        db.commit()
        db.refresh(db_device)
        # 记录操作日志
        log_action(db, current_user.user_id, "create_device", db_device.device_id, f"Created device {db_device.device_name}")
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

@router.get("/alldevices/status")
def update_device_status(db: Session = Depends(get_db)):
    devices = db.query(Device).all()
    for device in devices:
        try:
            # 构建HTTP请求URL
            api_url = f"http://{device.ip_address}/cgi-bin/api/tcpConnect/tcpTest"
            # 发送HTTP请求
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "DeviceMonitor/1.0"
            }           
            # 按照文档格式构造请求体
            payload = {
                "Ip": device.ip_address,  # 根据文档示例，这里应为服务器IP
                "Port": 80
            }
            # 发送POST请求（文档要求POST方法）
            response = requests.post(
                url=api_url,
                data=json.dumps(payload),  # 确保JSON序列化
                headers=headers,
                timeout=3
            )
            # 严格的状态码检查
            print(f"异常状态码: {response.status_code}, 响应内容: {response.text}")
            if response.status_code == 200 or response.status_code == 401:
                # 解析响应体               
                device.status = True
                device.last_heartbeat = datetime.now()
            else:
                device.status = False
        except requests.exceptions.RequestException as e:
            device.status = False            
        except json.JSONDecodeError:
            device.status = False

    db.commit()
    return {"message": "Status updated successfully"}

@router.put("/devices/{device_id}", response_model=DeviceResponse)
def update_device(device_id: str, device: DeviceUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_device = db.query(Device).filter(Device.device_id == device_id).first()
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # 更新设备信息
    update_data = device.dict(exclude_unset=True)
    # 如果密码为空，不更新密码
    if 'password' in update_data and not update_data['password']:
        del update_data['password']
    
    try:
        for key, value in update_data.items():
            setattr(db_device, key, value)
        db.commit()
        db.refresh(db_device)
        # 记录操作日志
        log_action(db, current_user.user_id, "update_device", device_id, f"Updated device {db_device.device_name}")
        return db_device
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/devices/{device_id}")
def delete_device(device_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    device_name = device.device_name
    try:
        db.delete(device)
        db.commit()
        # 记录操作日志
        log_action(db, current_user.user_id, "delete_device", device_id, f"Deleted device {device_name}")
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

# 用户管理API相关数据模型
class UserCreate(BaseModel):
    user_id: str
    username: str
    password: str
    role: str
    allowed_devices: List[str] = []

class UserUpdate(BaseModel):
    username: str
    allowed_devices: Optional[List[str]] = []

class PasswordUpdate(BaseModel):
    user_id: str
    old_password: str
    new_password: str

# 用户管理API
@router.post("/users/", response_model=dict)
def create_user(user: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(check_admin_permission)):
    # 哈希处理密码
    hashed_password = get_password_hash(user.password)
    db_user = User(
        user_id=user.user_id,
        username=user.username,
        password_hash=hashed_password,
        role=user.role,
        allowed_devices=user.allowed_devices
    )
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        # 记录操作日志
        log_action(db, current_user.user_id, "create_user", db_user.user_id, f"Created user {db_user.username}")
        return {"message": "用户创建成功", "user_id": db_user.user_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/users/profile", response_model=dict)
def update_user_profile(user_data: UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新当前用户的个人信息"""
    try:
        # 更新用户信息
        current_user.username = user_data.username
        current_user.allowed_devices = user_data.allowed_devices
        
        db.commit()
        db.refresh(current_user)
        
        # 记录操作日志
        log_action(db, current_user.user_id, "update_profile", current_user.user_id, f"Updated user profile for {current_user.username}")
        
        return {
            "message": "用户信息更新成功",
            "user_id": current_user.user_id,
            "username": current_user.username,
            "role": current_user.role,
            "allowed_devices": current_user.allowed_devices
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/users/password", response_model=dict)
def update_user_password(password_data: PasswordUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新用户密码"""
    # 验证是当前用户或管理员在操作
    if current_user.user_id != password_data.user_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权修改其他用户的密码")
    
    # 获取需要修改密码的用户
    target_user = current_user
    if current_user.user_id != password_data.user_id:
        target_user = db.query(User).filter(User.user_id == password_data.user_id).first()
        if not target_user:
            raise HTTPException(status_code=404, detail="用户不存在")
    
    # 验证旧密码（管理员重置密码可跳过此步骤）
    if current_user.role != "admin" and not verify_password(password_data.old_password, target_user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    
    # 更新密码
    try:
        target_user.password_hash = get_password_hash(password_data.new_password)
        db.commit()
        
        # 记录操作日志
        log_action(db, current_user.user_id, "update_password", target_user.user_id, f"Updated password for user {target_user.username}")
        
        return {"message": "密码更新成功"}
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
    db: Session = Depends(get_db)):
    query = db.query(SysLog)
    if user_id:
        query = query.filter(SysLog.user_id == user_id)
    if action_type:
        query = query.filter(SysLog.action_type == action_type)
    return query.offset(skip).limit(limit).all()

# 认证API
class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
       
    # 首先尝试使用标准认证
    user = authenticate_user(db, form_data.username, form_data.password)
    
    # 如果标准认证失败，尝试使用回退策略
    if not user:       
        user = db.query(User).filter(User.username == form_data.username).first()
        
        # 如果找到用户但认证失败，尝试直接比较密码
        if user and user.password_hash == form_data.password:
            print("使用明文密码比较成功")
        else:
            print("回退认证也失败")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    # 此时认证已成功
    print(f"用户 {form_data.username} 认证成功")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # 记录登录日志
    log_action(db, user.user_id, "login", user.user_id, f"User {user.username} logged in")
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=dict)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "role": current_user.role,
        "allowed_devices": current_user.allowed_devices
    }

@router.get("/token/validate")
async def validate_token(current_user: User = Depends(get_current_user)):
    """验证token是否有效"""
    return {"status": "success", "message": "Token is valid"}

@router.get("/system/init-check")
def check_system_initialization(db: Session = Depends(get_db)):
    """检查系统是否已初始化（是否存在用户）"""
    users_count = db.query(User).count()
    return {"initialized": users_count > 0}

@router.post("/system/init")
def initialize_system(admin_data: UserCreate, db: Session = Depends(get_db)):
    """初始化系统，创建管理员账户（仅当系统中没有用户时可用）"""
    users_count = db.query(User).count()
    if users_count > 0:
        raise HTTPException(status_code=400, detail="系统已初始化，无法重复创建管理员账户")
    
    # 设置为管理员角色
    admin_data.role = "admin"
    
    # 初始化加密上下文
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    # 生成哈希（示例输出：$2b$12$Pv20XbsKbZQrZpP58FABDupyf8DE9/NGHjB3IJ7fxtgfyIw.ygu92）
    hashed_password = pwd_context.hash(admin_data.password)
    # 创建管理员用户
    db_user = User(
        user_id=admin_data.user_id,
        username=admin_data.username,
        password_hash=hashed_password,
        role=admin_data.role,
        allowed_devices=admin_data.allowed_devices
    )
    
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        # 记录操作日志
        log_action(db, db_user.user_id, "create_admin", db_user.user_id, f"Created admin user {db_user.username}")
        return {"message": "系统初始化成功，管理员账户已创建"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# 调试API
@router.get("/debug/users")
def debug_users(db: Session = Depends(get_db)):
    """仅用于调试：获取所有用户信息"""
    users = db.query(User).all()
    result = []
    for user in users:
        user_info = {
            "user_id": user.user_id,
            "username": user.username,
            "role": user.role,
            "password_hash_prefix": user.password_hash[:10] + "..." if user.password_hash else None
        }
        result.append(user_info)
    return result

@router.get("/debug/user/{username}")
def debug_user(username: str, db: Session = Depends(get_db)):
    """仅用于调试：检查特定用户的信息"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return {"message": f"用户 {username} 不存在"}
    
    return {
        "user_id": user.user_id,
        "username": user.username,
        "role": user.role,
        "password_hash": user.password_hash,
        "is_bcrypt": user.password_hash.startswith("$2") if user.password_hash else False
    }

# 模型相关的Pydantic模型
class ModelBase(BaseModel):
    models_name: str
    models_type: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

class ModelResponse(ModelBase):
    models_id: str
    file_path: str
    file_size: int
    format: str
    upload_time: datetime
    last_used: Optional[datetime] = None
    is_active: bool
    models_classes: Optional[Dict[int, str]] = None

    class Config:
        from_attributes = True

# 模型管理API
@router.get("/models/", response_model=List[ModelResponse])
def get_models(skip: int = 0, limit: int = 100, db: Session = Depends(get_db),
              current_user: User = Depends(get_current_user)):
    """获取所有检测模型列表"""
    models = db.query(DetectionModel).offset(skip).limit(limit).all()
    return models

@router.get("/models/{models_id}", response_model=ModelResponse)
def get_model(models_id: str, db: Session = Depends(get_db),
             current_user: User = Depends(get_current_user)):
    """获取特定模型详情"""
    model = db.query(DetectionModel).filter(DetectionModel.models_id == models_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model

@router.post("/models/", response_model=ModelResponse)
async def upload_model(
    models_file: UploadFile = File(...),
    models_name: str = Form(...),
    models_type: str = Form(...),
    description: Optional[str] = Form(None),
    parameters: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)):
    """上传新模型文件"""
    # 检查权限（只有管理员可以上传模型）
    check_admin_permission(current_user)
    
    # 检查文件格式
    file_ext = os.path.splitext(models_file.filename)[1].lower()
    if file_ext not in ['.pt', '.onnx', '.pth', '.weights']:
        raise HTTPException(status_code=400, detail="Unsupported model format. Supported formats: .pt, .onnx, .pth, .weights")
    
    # 创建模型ID
    models_id = str(uuid.uuid4())
    
    # 确保模型目录存在
    models_dir = Path("models")
    models_dir.mkdir(exist_ok=True)
    
    # 保存文件
    file_path = models_dir / f"{models_id}{file_ext}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(models_file.file, buffer)
    
    # 获取文件大小
    file_size = os.path.getsize(file_path)
    
    # 解析参数JSON
    models_params = {}
    if parameters:
        try:
            models_params = json.loads(parameters)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid parameters JSON")
    
    # 加载模型并获取类别
    try:
        model = YOLO(file_path)  # 加载模型
        classes = model.names  # 获取类别名称
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型加载失败: {str(e)}")

    # 创建数据库记录
    db_model = DetectionModel(
        models_id=models_id,
        models_name=models_name,
        models_type=models_type,
        file_path=str(file_path),
        file_size=file_size,
        format=file_ext[1:],  # 去掉点号
        description=description,
        parameters=models_params,
        upload_time=datetime.now(),
        is_active=True,
        models_classes=classes  # 将类别信息存储到数据库
    )
    
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    
    # 记录操作日志
    log_action(db, current_user.user_id, "upload_model", models_id, f"Uploaded model {models_name}")
    
    return db_model

@router.delete("/models/{models_id}")
def delete_model(models_id: str, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    """删除模型"""
    # 检查权限
    check_admin_permission(current_user)
    
    # 查找模型
    model = db.query(DetectionModel).filter(DetectionModel.models_id == models_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # 删除文件
    try:
        os.remove(model.file_path)
    except OSError as e:
        # 如果文件不存在，继续删除数据库记录
        print(f"Error deleting file: {e}")
    
    # 删除数据库记录
    db.delete(model)
    db.commit()
    
    # 记录操作日志
    log_action(db, current_user.user_id, "delete_model", models_id, f"Deleted model {model.models_name}")
    
    return {"message": "Model deleted successfully"}

@router.put("/models/{models_id}/toggle")
def toggle_models_active(models_id: str, active: bool, db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    """切换模型激活状态"""
    # 检查权限
    check_admin_permission(current_user)
    
    # 查找模型
    model = db.query(DetectionModel).filter(DetectionModel.models_id == models_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # 更新状态
    model.is_active = active
    db.commit()
    db.refresh(model)
    
    # 记录操作日志
    action = "activate_model" if active else "deactivate_model"
    log_action(db, current_user.user_id, action, models_id, f"{'Activated' if active else 'Deactivated'} model {model.models_name}")
    
    return {"message": f"Model {'activated' if active else 'deactivated'} successfully"}

class Point(BaseModel):
    x: float
    y: float

class AreaCoordinates(BaseModel):
    type: str
    points: List[Point]  # 使用 Point 模型来表示坐标点
# 添加检测配置的Pydantic模型
class DetectionConfigBase(BaseModel):
    device_id: str
    models_id: str
    enabled: bool = False
    sensitivity: float = 0.5
    target_classes: Optional[List[str]] = []
    frequency: Optional[str] = "realtime"
    save_mode: Optional[str] = "none"
    save_duration: int = 10
    max_storage_days: int = 30

class DetectionConfigCreate(DetectionConfigBase):
    pass

class DetectionConfigUpdate(BaseModel):
    models_id: Optional[str] = None
    enabled: Optional[bool] = None
    sensitivity: Optional[float] = None
    target_classes: Optional[List[str]] = None
    frequency: Optional[str] = None
    save_mode: Optional[str] = None
    save_duration: Optional[int] = None
    max_storage_days: Optional[int] = None
    area_type:Optional[str] = None
    area_coordinates:Optional[AreaCoordinates] = None

class DetectionConfigResponse(DetectionConfigBase):
    config_id: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None

    class Config:
        from_attributes = True

class DetectionConfigDetailResponse(DetectionConfigBase):
    config_id: str
    device_name: str
    device_type: str
    ip_address: str
    port: int
    username: str
    password: str
    models_name: str
    models_type: str
    area_type: Optional[str] = None
    area_coordinates: dict # 定义为列表，包含坐标对
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None

    class Config:
        from_attributes = True

class DetectionConfigInfoResponse(DetectionConfigBase):
    config_id: str
    device_name: str
    models_name: str
    models_type: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None

    class Config:
        from_attributes = True

# 添加检测计划的Pydantic模型
class DetectionScheduleBase(BaseModel):
    config_id: str
    start_time: datetime
    end_time: datetime
    weekdays: List[int] = []
    is_active: bool = True

class DetectionScheduleCreate(DetectionScheduleBase):
    pass

class DetectionScheduleResponse(DetectionScheduleBase):
    schedule_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class BoundingBoxItem(BaseModel):
    bbox: List[float]
    class_id: int
    class_name: str
    confidence: float
# 添加检测事件的Pydantic模型
class DetectionEventBase(BaseModel):
    device_id: str
    config_id: str
    event_type: str
    confidence: float
    bounding_box: List[BoundingBoxItem]  # 修改为列表
    meta_data: Optional[dict] = None
    location: Optional[str] = None

class DetectionEventCreate(DetectionEventBase):
    pass

class DetectionEventUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    viewed_by: Optional[str] = None

class DetectionEventResponse(DetectionEventBase):
    event_id: str
    timestamp: datetime
    snippet_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    status: str
    viewed_at: Optional[datetime] = None
    viewed_by: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    save_mode: str = None

    class Config:
        from_attributes = True

# 获取检测配置列表
@router.get("/detection/configs", response_model=List[DetectionConfigDetailResponse])
async def get_detection_configs(
    device_id: Optional[str] = None,
    enabled: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)):
    """
    获取检测配置列表，可按设备ID和启用状态筛选
    """
    query = db.query(DetectionConfig).join(Device).join(DetectionModel)
    
    if device_id:
        query = query.filter(DetectionConfig.device_id == device_id)
    if enabled is not None:
        query = query.filter(DetectionConfig.enabled == enabled)
    
    configs = query.offset(skip).limit(limit).all()
    
    # 数据转换，确保枚举值被正确处理
    result = []
    for config in configs:

        area_coordinates = config.area_coordinates or {}  # 确保不为 None

        config_dict = {
            "config_id": config.config_id,
            "device_id": config.device_id,
            "device_name": config.device.device_name,
            "device_type": config.device.device_type,
            "ip_address": config.device.ip_address,
            "port": config.device.port,
            "username": config.device.username,
            "password": config.device.password,
            "models_id": config.models_id,
            "models_name": config.model.models_name,
            "models_type": config.model.models_type,
            "enabled": config.enabled,
            "sensitivity": config.sensitivity,
            "target_classes": config.target_classes if config.target_classes else [],
            "frequency": config.frequency.value if hasattr(config.frequency, "value") else config.frequency,
            "save_mode": config.save_mode.value if hasattr(config.save_mode, "value") else config.save_mode,
            "save_duration": config.save_duration,
            "max_storage_days": config.max_storage_days,
            "area_type": config.area_type,
            "area_coordinates": area_coordinates,
            "created_at": config.created_at,
            "updated_at": config.updated_at,
            "created_by": config.created_by
        }
        result.append(config_dict)
    
    return result

# 获取单个检测配置
@router.get("/detection/configs/{config_id}", response_model=DetectionConfigInfoResponse, tags=["检测配置"])
async def get_detection_config(
    config_id: str,
    db: Session = Depends(get_db)):
    """
    获取单个检测配置详情
    """
    config = db.query(DetectionConfig).join(Device).join(DetectionModel).filter(DetectionConfig.config_id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="检测配置不存在")
    
    # 数据转换，确保枚举值被正确处理
    config_dict = {
        "config_id": config.config_id,
        "device_id": config.device_id,
        "device_name": config.device.device_name,
        "models_id": config.models_id,
        "models_name": config.model.models_name,
        "models_type": config.model.models_type,
        "enabled": config.enabled,
        "sensitivity": config.sensitivity,
        "target_classes": config.target_classes if config.target_classes else [],
        "frequency": config.frequency.value if hasattr(config.frequency, "value") else config.frequency,
        "save_mode": config.save_mode.value if hasattr(config.save_mode, "value") else config.save_mode,
        "save_duration": config.save_duration,
        "max_storage_days": config.max_storage_days,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
        "created_by": config.created_by
    }
    
    return config_dict

# 创建检测配置
@router.post("/detection/configs", response_model=DetectionConfigResponse, tags=["检测配置"])
async def create_detection_config(
    config: DetectionConfigCreate,
    db: Session = Depends(get_db)):
    """
    创建新的检测配置
    """
    # 检查设备是否存在
    device = db.query(Device).filter(Device.device_id == config.device_id).first()
    if not device:
        raise HTTPException(status_code=400, detail="设备不存在")
    
    # 检查模型是否存在
    model = db.query(DetectionModel).filter(DetectionModel.models_id == config.models_id).first()
    if not model:
        raise HTTPException(status_code=400, detail="检测模型不存在")
    
    # 处理枚举类型
    try:
        frequency_enum = DetectionFrequency(config.frequency) if isinstance(config.frequency, str) else config.frequency
        save_mode_enum = SaveMode(config.save_mode) if isinstance(config.save_mode, str) else config.save_mode
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的频率或保存模式值")
    
    # 创建配置记录
    db_config = DetectionConfig(
        config_id=str(uuid.uuid4()),
        device_id=config.device_id,
        models_id=config.models_id,
        enabled=config.enabled,
        sensitivity=config.sensitivity,
        target_classes=config.target_classes,
        frequency=frequency_enum,
        save_mode=save_mode_enum,
        save_duration=config.save_duration,
        max_storage_days=config.max_storage_days,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    
    # 转换返回数据
    config_dict = {
        "config_id": db_config.config_id,
        "device_id": db_config.device_id,
        "models_id": db_config.models_id,
        "enabled": db_config.enabled,
        "sensitivity": db_config.sensitivity,
        "target_classes": db_config.target_classes if db_config.target_classes else [],
        "frequency": db_config.frequency.value if hasattr(db_config.frequency, "value") else db_config.frequency,
        "save_mode": db_config.save_mode.value if hasattr(db_config.save_mode, "value") else db_config.save_mode,
        "save_duration": db_config.save_duration,
        "max_storage_days": db_config.max_storage_days,
        "created_at": db_config.created_at,
        "updated_at": db_config.updated_at,
        "created_by": db_config.created_by
    }
    
    return config_dict

# 更新检测配置
@router.put("/detection/configs/{config_id}", response_model=DetectionConfigResponse, tags=["检测配置"])
async def update_detection_config(
    config_id: str,
    config_update: DetectionConfigUpdate,
    db: Session = Depends(get_db)):
    """
    更新检测配置
    """
    # 查找配置
    db_config = db.query(DetectionConfig).filter(DetectionConfig.config_id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="检测配置不存在")
    
    # 更新模型ID（如果提供）
    if config_update.models_id is not None:
        model = db.query(DetectionModel).filter(DetectionModel.models_id == config_update.models_id).first()
        if not model:
            raise HTTPException(status_code=400, detail="检测模型不存在")
        db_config.models_id = config_update.models_id
    
    # 更新其他字段
    if config_update.enabled is not None:
        db_config.enabled = config_update.enabled
    
    if config_update.sensitivity is not None:
        db_config.sensitivity = config_update.sensitivity
    
    if config_update.target_classes is not None:
        db_config.target_classes = config_update.target_classes
    
    if config_update.frequency is not None:
        try:
            db_config.frequency = DetectionFrequency(config_update.frequency) if isinstance(config_update.frequency, str) else config_update.frequency
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的频率值")
    
    if config_update.save_mode is not None:
        try:
            db_config.save_mode = SaveMode(config_update.save_mode) if isinstance(config_update.save_mode, str) else config_update.save_mode
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的保存模式值")
    
    if config_update.save_duration is not None:
        db_config.save_duration = config_update.save_duration
    
    if config_update.max_storage_days is not None:
        db_config.max_storage_days = config_update.max_storage_days

    if config_update.area_type is not None:  
        db_config.area_type = config_update.area_type

    if config_update.area_coordinates is not None:  
        # area_coordinates = config_update.area_coordinates
        # if area_coordinates and isinstance(area_coordinates, dict) and "points" in area_coordinates and len(area_coordinates["points"]) > 0:
        #     db_config.area_coordinates = area_coordinates
        # else:
        #     raise HTTPException(status_code=422, detail="Invalid area coordinates")
        db_config.area_coordinates = config_update.area_coordinates.dict()
    

    # 更新时间戳
    db_config.updated_at = datetime.now()
    
    # 提交更改
    db.commit()
    db.refresh(db_config)
    
    # 转换返回数据
    config_dict = {
        "config_id": db_config.config_id,
        "device_id": db_config.device_id,
        "models_id": db_config.models_id,
        "enabled": db_config.enabled,
        "sensitivity": db_config.sensitivity,
        "target_classes": db_config.target_classes if db_config.target_classes else [],
        "frequency": db_config.frequency.value if hasattr(db_config.frequency, "value") else db_config.frequency,
        "save_mode": db_config.save_mode.value if hasattr(db_config.save_mode, "value") else db_config.save_mode,
        "save_duration": db_config.save_duration,
        "max_storage_days": db_config.max_storage_days,
        "created_at": db_config.created_at,
        "updated_at": db_config.updated_at,
        "created_by": db_config.created_by,
        "area_type": db_config.area_type
    }
    
    return config_dict

@router.put("/detection/configs/{config_id}/toggle")
def toggle_detection_active(config_id: str, enabled: bool, db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    """切换检测配置启用状态"""
    # 检查权限
    check_admin_permission(current_user)
    
    # 查找模型
    config = db.query(DetectionConfig).filter(DetectionConfig.config_id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="检测配置不存在")
    
    # 更新状态
    config.enabled = enabled
    db.commit()
    db.refresh(config)
    return {"message": f"检测配置 {'启用' if enabled else '禁用'} 成功"}

# 删除检测配置
@router.delete("/detection/configs/{config_id}", tags=["检测配置"])
async def delete_detection_config(
    config_id: str,
    db: Session = Depends(get_db)):
    """
    删除检测配置
    """
    db_config = db.query(DetectionConfig).filter(DetectionConfig.config_id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="检测配置不存在")
    
    try:
        db.delete(db_config)
        db.commit()
        return {"message": "检测配置已成功删除"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除检测配置失败: {str(e)}")

# 获取设备的所有检测事件
@router.get("/detection/events", response_model=List[DetectionEventResponse], tags=["检测事件"])
async def get_detection_events(
    device_id: Optional[str] = None,
    config_id: Optional[str] = None,
    event_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status: Optional[str] = None,
    min_confidence: Optional[float] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)):
    """
    获取检测事件列表，支持多种筛选条件
    """
    query = db.query(DetectionEvent).join(DetectionConfig)
    # 应用筛选条件
    if device_id:
        query = query.filter(DetectionEvent.device_id == device_id)
    if config_id:
        query = query.filter(DetectionEvent.config_id == config_id)
    if event_type:
        query = query.filter(DetectionEvent.event_type == event_type)
    if start_date:
        query = query.filter(DetectionEvent.created_at >= start_date)
    if end_date:
        query = query.filter(DetectionEvent.created_at <= end_date)
    if status:
        try:
            status_enum = getattr(EventStatus, status)
            query = query.filter(DetectionEvent.status == status_enum)
        except AttributeError:
            raise HTTPException(status_code=400, detail="无效的状态值")
    if min_confidence:
        query = query.filter(DetectionEvent.confidence >= min_confidence)
    
    # 按时间倒序排列
    query = query.order_by(desc(DetectionEvent.created_at))
    
    events = query.offset(skip).limit(limit).all()
    
    # 转换结果
    result = []
    for event in events:
        # 确保bounding_box是字典
        bounding_box = event.bounding_box
        if isinstance(bounding_box, str):
            try:
                bounding_box = json.loads(bounding_box)
            except (json.JSONDecodeError, TypeError):
                bounding_box = []
        
        # 确保meta_data是字典
        meta_data = event.meta_data
        if isinstance(meta_data, str):
            try:
                meta_data = json.loads(meta_data)
            except (json.JSONDecodeError, TypeError):
                meta_data = {}
        elif meta_data is None:
            meta_data = {}
        
        event_dict = {
            "event_id": event.event_id,
            "device_id": event.device_id,
            "config_id": event.config_id,
            "timestamp": event.timestamp,
            "event_type": event.event_type,
            "confidence": event.confidence,
            "bounding_box": bounding_box,
            "meta_data": meta_data,
            "location": event.location,
            "snippet_path": event.snippet_path,
            "thumbnail_path": event.thumbnail_path,
            "status": event.status.value if hasattr(event.status, "value") else event.status,
            "viewed_at": event.viewed_at,
            "viewed_by": event.viewed_by,
            "notes": event.notes,
            "created_at": event.created_at,
            "save_mode": event.config.save_mode.value if hasattr(event.config.save_mode, "value") else event.config.save_mode
        }
        result.append(event_dict)
    
    return result

# 获取单个检测事件详情
@router.get("/detection/events/{event_id}", response_model=DetectionEventResponse, tags=["检测事件"])
async def get_detection_event(
    event_id: str,
    db: Session = Depends(get_db)):
    """
    通过事件ID获取检测事件详情
    """
    event = db.query(DetectionEvent).filter(DetectionEvent.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="检测事件不存在")
    
    # 确保bounding_box是字典
    bounding_box = event.bounding_box
    if isinstance(bounding_box, str):
        try:
            bounding_box = json.loads(bounding_box)
        except (json.JSONDecodeError, TypeError):
            bounding_box = []
    
    # 确保meta_data是字典
    meta_data = event.meta_data
    if isinstance(meta_data, str):
        try:
            meta_data = json.loads(meta_data)
        except (json.JSONDecodeError, TypeError):
            meta_data = {}
    elif meta_data is None:
        meta_data = {}
    
    # 转换结果
    event_dict = {
        "event_id": event.event_id,
        "device_id": event.device_id,
        "config_id": event.config_id,
        "timestamp": event.timestamp,
        "event_type": event.event_type,
        "confidence": event.confidence,
        "bounding_box": bounding_box,
        "meta_data": meta_data,
        "location": event.location,
        "snippet_path": event.snippet_path,
        "thumbnail_path": event.thumbnail_path,
        "status": event.status.value if hasattr(event.status, "value") else event.status,
        "viewed_at": event.viewed_at,
        "viewed_by": event.viewed_by,
        "notes": event.notes,
        "created_at": event.created_at
    }
    
    return event_dict

@router.get("/detection/events/{event_id}/thumbnail")
async def get_thumbnail(event_id: str, db: Session = Depends(get_db)):
    """获取缩略图数据"""
    event = db.query(DetectionEvent).filter(DetectionEvent.event_id == event_id).first() 

    if not event or not event.thumbnail_data:
        raise HTTPException(status_code=404, detail="未找到图像数据")
    
    # 添加缓存控制头
    headers = {
        "Content-Type": "image/jpeg",
        "Cache-Control": "public, max-age=86400",
        "Content-Disposition": f"inline; filename={event_id}.jpg"
    }
    
    # 验证二进制数据有效性
    if not isinstance(event.thumbnail_data, bytes):
        raise HTTPException(status_code=500, detail="数据格式错误")
    
    return Response(
        content=event.thumbnail_data,
        media_type="image/jpeg",
        headers=headers
    )

# 创建检测事件
@router.post("/detection/events", response_model=DetectionEventResponse, tags=["检测事件"])
async def create_detection_event(
    event: DetectionEventCreate,
    db: Session = Depends(get_db)):
    """
    创建新的检测事件
    """
    # 检查设备是否存在
    device = db.query(Device).filter(Device.device_id == event.device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 检查配置是否存在
    config = db.query(DetectionConfig).filter(DetectionConfig.config_id == event.config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="检测配置不存在")
    
     # 确保bounding_box是列表
    bounding_box = event.bounding_box
    if not isinstance(bounding_box, list):
        raise HTTPException(status_code=400, detail="bounding_box必须是一个有效的列表对象")
    
    # 确保每个元素都是字典
    for item in bounding_box:
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="bounding_box中的每个元素必须是字典对象")
    
    # 确保meta_data是字典
    meta_data = event.meta_data if event.meta_data is not None else {}
    if not isinstance(meta_data, dict):
        raise HTTPException(status_code=400, detail="meta_data必须是一个有效的JSON对象")
    
    try:
        event_id = str(uuid.uuid4())
        current_time = datetime.now()
        db_event = DetectionEvent(
            event_id=event_id,
            device_id=event.device_id,
            config_id=event.config_id,
            timestamp=current_time,
            event_type=event.event_type,
            confidence=event.confidence,
            bounding_box=bounding_box,
            meta_data=meta_data,
            status=EventStatus.new,
            location=event.location,
            created_at=current_time
        )
        db.add(db_event)
        db.commit()
        db.refresh(db_event)
        
        # 更新统计数据
        update_detection_stats(db, event.device_id, event.event_type)
        
        # 处理返回数据中的bounding_box
        bounding_box_result = db_event.bounding_box
        if isinstance(bounding_box_result, str):
            try:
                bounding_box_result = json.loads(bounding_box_result)
            except (json.JSONDecodeError, TypeError):
                bounding_box_result = []
                
        # 处理返回数据中的meta_data
        meta_data_result = db_event.meta_data
        if isinstance(meta_data_result, str):
            try:
                meta_data_result = json.loads(meta_data_result)
            except (json.JSONDecodeError, TypeError):
                meta_data_result = {}
        elif meta_data_result is None:
            meta_data_result = {}
        
        # 转换返回数据
        event_dict = {
            "event_id": db_event.event_id,
            "device_id": db_event.device_id,
            "config_id": db_event.config_id,
            "timestamp": db_event.timestamp,
            "event_type": db_event.event_type,
            "confidence": db_event.confidence,
            "bounding_box": bounding_box_result,
            "meta_data": meta_data_result,
            "location": db_event.location,
            "snippet_path": db_event.snippet_path,
            "thumbnail_path": db_event.thumbnail_path,
            "status": db_event.status.value if hasattr(db_event.status, "value") else db_event.status,
            "viewed_at": db_event.viewed_at,
            "viewed_by": db_event.viewed_by,
            "notes": db_event.notes,
            "created_at": db_event.created_at
        }
        
        return event_dict
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建检测事件失败: {str(e)}")

# 更新检测事件状态
@router.put("/detection/events/{event_id}", response_model=DetectionEventResponse, tags=["检测事件"])
async def update_detection_event(
    event_id: str,
    event_update: DetectionEventUpdate,
    db: Session = Depends(get_db)):
    """
    更新检测事件状态、备注等信息
    """
    db_event = db.query(DetectionEvent).filter(DetectionEvent.event_id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="检测事件不存在")
    
    # 更新字段
    if event_update.status is not None:
        try:
            db_event.status = getattr(EventStatus, event_update.status)
        except AttributeError:
            raise HTTPException(status_code=400, detail="无效的状态值")
    
    if event_update.notes is not None:
        db_event.notes = event_update.notes
    
    if event_update.viewed_by is not None:
        # 检查用户是否存在
        user = db.query(User).filter(User.user_id == event_update.viewed_by).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        db_event.viewed_by = event_update.viewed_by
        db_event.viewed_at = datetime.now()
    
    try:
        db.commit()
        db.refresh(db_event)
        
        # 确保bounding_box是字典
        bounding_box = db_event.bounding_box
        if isinstance(bounding_box, str):
            try:
                bounding_box = json.loads(bounding_box)
            except (json.JSONDecodeError, TypeError):
                bounding_box = []
        
        # 确保meta_data是字典
        meta_data = db_event.meta_data
        if isinstance(meta_data, str):
            try:
                meta_data = json.loads(meta_data)
            except (json.JSONDecodeError, TypeError):
                meta_data = {}
        elif meta_data is None:
            meta_data = {}
        
        # 转换返回数据
        event_dict = {
            "event_id": db_event.event_id,
            "device_id": db_event.device_id,
            "config_id": db_event.config_id,
            "timestamp": db_event.timestamp,
            "event_type": db_event.event_type,
            "confidence": db_event.confidence,
            "bounding_box": bounding_box,
            "meta_data": meta_data,
            "location": db_event.location,
            "snippet_path": db_event.snippet_path,
            "thumbnail_path": db_event.thumbnail_path,
            "status": db_event.status.value if hasattr(db_event.status, "value") else db_event.status,
            "viewed_at": db_event.viewed_at,
            "viewed_by": db_event.viewed_by,
            "notes": db_event.notes,
            "created_at": db_event.created_at
        }
        
        return event_dict
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新检测事件失败: {str(e)}")

# 删除检测事件
@router.delete("/detection/events/{event_id}", tags=["检测事件"])
async def delete_detection_event(
    event_id: str,
    db: Session = Depends(get_db)):
    """
    删除检测事件
    """
    db_event = db.query(DetectionEvent).filter(DetectionEvent.event_id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="检测事件不存在")
    
    try:
        db.delete(db_event)
        db.commit()
        return {"message": "检测事件已成功删除"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除检测事件失败: {str(e)}")

# 获取设备的检测统计数据
@router.get("/detection/stats", response_model=List[dict], tags=["检测统计"])
async def get_detection_stats(
    device_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)):
    """
    获取设备的检测统计数据
    """
    query = db.query(DetectionStat)
    
    if device_id:
        query = query.filter(DetectionStat.device_id == device_id)
    if start_date:
        query = query.filter(DetectionStat.date >= start_date)
    if end_date:
        query = query.filter(DetectionStat.date <= end_date)
    
    stats = query.order_by(DetectionStat.date).all()
    
    result = []
    for stat in stats:
        result.append({
            "stat_id": stat.stat_id,
            "device_id": stat.device_id,
            "date": stat.date,
            "total_events": stat.total_events,
            "by_class": stat.by_class,
            "peak_hour": stat.peak_hour,
            "peak_hour_count": stat.peak_hour_count
        })
    
    return result

# 检测计划相关API
@router.get("/detection/schedules", response_model=List[DetectionScheduleResponse], tags=["检测计划"])
async def get_detection_schedules(
    config_id: Optional[str] = None,
    active_only: bool = False,
    db: Session = Depends(get_db)):
    """
    获取检测计划列表
    """
    query = db.query(DetectionSchedule)
    
    if config_id:
        query = query.filter(DetectionSchedule.config_id == config_id)
    if active_only:
        query = query.filter(DetectionSchedule.is_active == True)
    
    schedules = query.all()
    return schedules

@router.post("/detection/schedules", response_model=DetectionScheduleResponse, tags=["检测计划"])
async def create_detection_schedule(
    schedule: DetectionScheduleCreate,
    db: Session = Depends(get_db)):
    """
    创建新的检测计划
    """
    # 检查配置是否存在
    config = db.query(DetectionConfig).filter(DetectionConfig.config_id == schedule.config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="检测配置不存在")
    
    # 验证时间范围
    if schedule.start_time >= schedule.end_time:
        raise HTTPException(status_code=400, detail="开始时间必须早于结束时间")
    
    # 验证周几设置
    for day in schedule.weekdays:
        if day < 1 or day > 7:
            raise HTTPException(status_code=400, detail="周几设置必须是1-7的整数")
    
    try:
        schedule_id = str(uuid.uuid4())
        db_schedule = DetectionSchedule(
            schedule_id=schedule_id,
            config_id=schedule.config_id,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            weekdays=schedule.weekdays,
            is_active=schedule.is_active,
            created_at=datetime.now()
        )
        db.add(db_schedule)
        db.commit()
        db.refresh(db_schedule)
        return db_schedule
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建检测计划失败: {str(e)}")

# 辅助函数：更新检测统计数据
def update_detection_stats(db: Session, device_id: str, event_type: str):
    # 获取今天的日期（不包含时间）
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 查找今天的统计记录
    stat = db.query(DetectionStat).filter(
        DetectionStat.device_id == device_id,
        func.date(DetectionStat.date) == func.date(today)
    ).first()
    
    # 如果不存在，创建新记录
    if not stat:
        stat = DetectionStat(
            stat_id=str(uuid.uuid4()),
            device_id=device_id,
            date=today,
            total_events=1,
            by_class={event_type: 1},
            peak_hour=datetime.now().hour,
            peak_hour_count=1,
            created_at=datetime.now()
        )
        db.add(stat)
    else:
        # 更新统计数据
        stat.total_events += 1
        
        # 更新分类统计
        by_class = stat.by_class or {}
        by_class[event_type] = by_class.get(event_type, 0) + 1
        stat.by_class = by_class
        
        # 更新峰值小时
        current_hour = datetime.now().hour
        hourly_events = db.query(func.count(DetectionEvent.event_id)).filter(
            DetectionEvent.device_id == device_id,
            func.date(DetectionEvent.created_at) == func.date(today),
            func.extract('hour', DetectionEvent.created_at) == current_hour
        ).scalar()
        
        if hourly_events > stat.peak_hour_count:
            stat.peak_hour = current_hour
            stat.peak_hour_count = hourly_events
    
    db.commit() 

@router.get("/files/{file_path:path}")
async def get_file(file_path: str):
    # 构建完整的文件路径
    full_path = os.path.join(file_path)

    # 检查文件是否存在
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    # 返回文件
    return FileResponse(full_path)