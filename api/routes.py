from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from models.database import get_db, Device, Video, AnalysisResult, Alarm, User, SysLog
from pydantic import BaseModel, IPvAnyAddress
from fastapi.security import OAuth2PasswordRequestForm
from api.auth import authenticate_user, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user, check_admin_permission, get_password_hash, verify_password
from api.logger import log_action
from passlib.context import CryptContext

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

class DeviceUpdate(BaseModel):
    device_name: str
    device_type: str
    ip_address: str
    port: int
    username: str
    password: Optional[str]
    status: bool

# 设备管理API
@router.post("/devices/", response_model=DeviceResponse)
def create_device(device: DeviceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # 处理IP地址，将IPv4Address转换为字符串
    device_data = device.dict()
    if isinstance(device_data['ip_address'], (str, bytes, bytearray)):
        device_data['ip_address'] = str(device_data['ip_address'])
    
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
    db: Session = Depends(get_db)
):
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
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "role": current_user.role,
        "allowed_devices": current_user.allowed_devices
    }

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