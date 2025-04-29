from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Integer, Float, Enum, ForeignKey, ARRAY, Text, SmallInteger
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import enum
from datetime import datetime
import uuid
from sqlalchemy import LargeBinary
import os

Base = declarative_base()

class AlarmStatus(enum.Enum):
    pending = "pending"
    processed = "processed"
    ignored = "ignored"

class AnalysisTarget(enum.Enum):
    person = "person"
    vehicle = "vehicle"
    fire = "fire"
    helmet = "helmet"

class SaveMode(enum.Enum):
    none="none"
    screenshot = "screenshot"
    video = "video"
    both = "both"

class EventStatus(enum.Enum):
    new = "new"
    viewed = "viewed"
    flagged = "flagged"
    archived = "archived"

class PushMethod(enum.Enum):
    http = "http"
    https = "https"
    tcp = "tcp"
    mqtt = "mqtt"

class DetectionFrequency(enum.Enum):
    realtime = "realtime"
    scheduled = "scheduled"
    manual = "manual"

class Device(Base):
    __tablename__ = "device"
    
    device_id = Column(String(64), primary_key=True)
    device_name = Column(String(255), nullable=False)
    device_type = Column(String(50))
    ip_address = Column(String(15), nullable=False)
    port = Column(SmallInteger, nullable=False)
    username = Column(String(64), nullable=False)
    password = Column(String(256), nullable=False)
    channel = Column(Integer, default=1)  # 通道号，默认为1
    stream_type = Column(String(10), default="main")  # 码流类型，main或sub
    status = Column(Boolean, default=True)
    last_heartbeat = Column(DateTime)
    location = Column(String(255))
    area = Column(String(255))
    
    detection_configs = relationship("DetectionConfig", back_populates="device", cascade="all, delete-orphan")
    detection_events = relationship("DetectionEvent", back_populates="device", cascade="all, delete-orphan")

class Video(Base):
    __tablename__ = "video"
    
    video_id = Column(String(64), primary_key=True)
    device_id = Column(String(64), ForeignKey('device.device_id'))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    storage_path = Column(Text, nullable=False)
    resolution = Column(String(16))
    frame_rate = Column(SmallInteger)
    analysis_status = Column(Boolean, default=False)

class AnalysisResult(Base):
    __tablename__ = "analysis_result"
    
    result_id = Column(Integer, primary_key=True)
    video_id = Column(String(64), ForeignKey('video.video_id'))
    target_type = Column(Enum(AnalysisTarget), nullable=False)
    confidence = Column(Float, nullable=False)
    start_frame = Column(Integer)
    end_frame = Column(Integer)
    meta_data = Column(JSONB)

class Alarm(Base):
    __tablename__ = "alarm"
    
    alarm_id = Column(String(64), primary_key=True)
    event_type = Column(String(50), nullable=False)
    trigger_time = Column(DateTime, default=datetime.now)
    device_id = Column(String(64), ForeignKey('device.device_id'))
    video_id = Column(String(64), ForeignKey('video.video_id'))
    status = Column(Enum(AlarmStatus), default=AlarmStatus.pending)
    snapshot_path = Column(Text)

class User(Base):
    __tablename__ = "users"
    
    user_id = Column(String(64), primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(64), nullable=False)
    role = Column(String(20))
    allowed_devices = Column(ARRAY(Text))

class SysLog(Base):
    __tablename__ = "syslog"
    
    log_id = Column(Integer, primary_key=True)
    user_id = Column(String(64), ForeignKey('users.user_id'))
    action_type = Column(String(50), nullable=False)
    target_id = Column(String(64))
    detail = Column(Text)
    log_time = Column(DateTime, default=datetime.now)

class DetectionModel(Base):
    __tablename__ = "detection_model"
    
    models_id = Column(String(64), primary_key=True)
    models_name = Column(String(255), nullable=False)
    models_type = Column(String(50), nullable=False)
    file_path = Column(Text, nullable=False)
    file_size = Column(Integer)
    format = Column(String(20), nullable=False)
    description = Column(Text)
    parameters = Column(JSONB)
    upload_time = Column(DateTime, default=datetime.now)
    last_used = Column(DateTime)
    is_active = Column(Boolean, default=True)
    models_classes = Column(JSONB, nullable=True)  # 新增字段，用于存储类别信息

    detection_configs = relationship("DetectionConfig", back_populates="model", cascade="all, delete-orphan")

class DetectionConfig(Base):
    __tablename__ = "detection_config"
    
    config_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(64), ForeignKey('device.device_id'), nullable=False)
    models_id = Column(String(64), ForeignKey('detection_model.models_id'), nullable=False)
    enabled = Column(Boolean, default=False)
    sensitivity = Column(Float, default=0.5)
    target_classes = Column(ARRAY(Text))
    frequency = Column(Enum(DetectionFrequency), default=DetectionFrequency.realtime)
    save_mode = Column(Enum(SaveMode), default=SaveMode.screenshot)
    save_duration = Column(Integer, default=10)
    max_storage_days = Column(Integer, default=30)
    area_coordinates = Column(JSONB)  # 新增字段，用于存储区域坐标
    area_type = Column(Text, default="none")  # 新增字段，用于存储区域类型(拌线/区域)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_by = Column(String(64), ForeignKey('users.user_id'))
    
    device = relationship("Device", back_populates="detection_configs")
    model = relationship("DetectionModel", back_populates="detection_configs")
    schedules = relationship("DetectionSchedule", back_populates="config", cascade="all, delete-orphan")
    events = relationship("DetectionEvent", back_populates="config", cascade="all, delete-orphan")

class DetectionSchedule(Base):
    __tablename__ = "detection_schedule"
    
    schedule_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_id = Column(String(64), ForeignKey('detection_config.config_id'), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    weekdays = Column(ARRAY(Integer))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    
    config = relationship("DetectionConfig", back_populates="schedules")

class DetectionEvent(Base):
    __tablename__ = "detection_event"
    
    event_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(64), ForeignKey('device.device_id'), nullable=False)
    config_id = Column(String(64), ForeignKey('detection_config.config_id'), nullable=False)
    timestamp = Column(DateTime, default=datetime.now)
    event_type = Column(String(50))
    confidence = Column(Float)
    bounding_box = Column(JSONB)
    # 新增以下两个二进制字段
    thumbnail_data = Column(LargeBinary)  # 存储JPEG图像数据
    is_compressed = Column(Boolean, default=False)  # 添加压缩标记
    # video_data = Column(LargeBinary)     # 存储MP4视频数据（可选）
    # 删除原来的路径字段（如果存在）
    snippet_path = Column(Text)
    thumbnail_path = Column(Text)
    meta_data = Column(JSONB)
    status = Column(Enum(EventStatus), default=EventStatus.new)
    viewed_at = Column(DateTime)
    viewed_by = Column(String(64), ForeignKey('users.user_id'))
    notes = Column(Text)
    location = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    
    device = relationship("Device", back_populates="detection_events")
    config = relationship("DetectionConfig", back_populates="events")
    viewer = relationship("User", foreign_keys=[viewed_by])

class DetectionStat(Base):
    __tablename__ = "detection_stat"
    
    stat_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(64), ForeignKey('device.device_id'))
    date = Column(DateTime, default=datetime.now)
    total_events = Column(Integer, default=0)
    by_class = Column(JSONB)
    peak_hour = Column(Integer)
    peak_hour_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    
    device = relationship("Device")

class DetectionPerformance(Base):
    __tablename__ = "detection_performance"
    
    performance_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(64), ForeignKey('device.device_id'))
    config_id = Column(String(64), ForeignKey('detection_config.config_id'))
    timestamp = Column(DateTime, default=datetime.now)
    detection_time = Column(Float)
    preprocessing_time = Column(Float)
    postprocessing_time = Column(Float)
    frame_width = Column(Integer)
    frame_height = Column(Integer)
    objects_detected = Column(Integer)
    device = relationship("Device")
    config = relationship("DetectionConfig")

class DataPushConfig(Base):
    __tablename__ = "data_push_config"
    
    push_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    push_name = Column(String(255), nullable=False)
    push_method = Column(Enum(PushMethod), nullable=False)
    # 修改config_id为可选，允许推送器独立于检测配置
    config_id = Column(String(64), ForeignKey('detection_config.config_id'), nullable=True)
    # 添加标签字段，用于灵活关联不同模块
    tags = Column(ARRAY(Text), default=[])
    enabled = Column(Boolean, default=True)
    
    # HTTP/HTTPS设置
    http_url = Column(Text)
    http_headers = Column(JSONB)
    http_method = Column(String(10), default="POST")
    
    # TCP设置
    tcp_host = Column(String(255))
    tcp_port = Column(Integer)
    
    # MQTT设置
    mqtt_broker = Column(String(255))
    mqtt_port = Column(Integer, default=1883)
    mqtt_topic = Column(String(255))
    mqtt_client_id = Column(String(255))
    mqtt_username = Column(String(255))
    mqtt_password = Column(String(255))
    mqtt_use_tls = Column(Boolean, default=False)
    
    # 通用设置
    push_interval = Column(Integer, default=0)  # 0表示实时推送，>0表示间隔秒数
    last_push_time = Column(DateTime)
    retry_count = Column(Integer, default=3)
    retry_interval = Column(Integer, default=10)  # 重试间隔(秒)
    include_image = Column(Boolean, default=False)  # 是否包含图像数据
    data_format = Column(String(50), default="json")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系可以保留，但现在是可选的
    config = relationship("DetectionConfig", foreign_keys=[config_id])

class CrowdAnalysisJob(Base):
    __tablename__ = "crowd_analysis_job"
    
    job_id = Column(String(64), primary_key=True)
    job_name = Column(String(128), nullable=False)
    device_ids = Column(ARRAY(String)) # 设备ID列表
    models_id = Column(String(64), ForeignKey('detection_model.models_id'), nullable=True) # 检测模型ID
    interval = Column(Integer, nullable=True) # 执行间隔(秒)
    cron_expression = Column(String(64), nullable=True) # Cron表达式
    tags = Column(ARRAY(String)) # 标签列表
    location_info = Column(JSONB, nullable=True) # 位置信息
    description = Column(String(512), nullable=True) # 描述
    is_active = Column(Boolean, default=True) # 是否启用
    detect_classes = Column(ARRAY(String), nullable=True) # 检测类别
    created_at = Column(DateTime, default=datetime.now)
    last_run = Column(DateTime, nullable=True) # 最后执行时间
    last_result = Column(JSONB, nullable=True) # 最后结果
    last_error = Column(String(512), nullable=True) # 最后错误信息
    warning_threshold = Column(Integer, default=0)  # 人数预警阈值，0表示不预警
    warning_message = Column(String(256))  # 预警消息模板
    warning_receivers = Column(ARRAY(String))  # 预警接收者
    
    model = relationship("DetectionModel", foreign_keys=[models_id])

class CrowdAnalysisResult(Base):
    __tablename__ = "crowd_analysis_result"
    
    result_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(64), ForeignKey('crowd_analysis_job.job_id'), nullable=False)
    timestamp = Column(DateTime, default=datetime.now)
    total_person_count = Column(Integer, default=0)
    camera_counts = Column(JSONB)  # 存储各摄像头的人数数据
    location_info = Column(JSONB, nullable=True)
    
    job = relationship("CrowdAnalysisJob", back_populates="results")

# 添加反向关系
CrowdAnalysisJob.results = relationship("CrowdAnalysisResult", back_populates="job")

# 根据环境区分数据库连接字符串
# 开发环境使用本地数据库，生产环境使用Docker容器内数据库
# 开发环境设置的环境变量或默认使用localhost
# dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"
# if dev_mode:
#     # 开发环境使用localhost
#     DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:admin123@10.83.34.35:5432/eyris_core_db")
# else:
    # 生产环境使用Docker容器名
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:admin123@postgres:5432/yolo")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 