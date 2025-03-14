from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Integer, Float, Enum, ForeignKey, ARRAY, Text, SmallInteger
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import enum
from datetime import datetime
import uuid

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
    screenshot = "screenshot"
    video = "video"
    both = "both"

class EventStatus(enum.Enum):
    new = "new"
    viewed = "viewed"
    flagged = "flagged"
    archived = "archived"

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
    status = Column(Boolean, default=True)
    last_heartbeat = Column(DateTime)
    
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
    trigger_time = Column(DateTime, default=datetime.utcnow)
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
    log_time = Column(DateTime, default=datetime.utcnow)

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
    upload_time = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
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
    created_at = Column(DateTime, default=datetime.utcnow)
    
    config = relationship("DetectionConfig", back_populates="schedules")

class DetectionEvent(Base):
    __tablename__ = "detection_event"
    
    event_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(64), ForeignKey('device.device_id'), nullable=False)
    config_id = Column(String(64), ForeignKey('detection_config.config_id'), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    event_type = Column(String(50))
    confidence = Column(Float)
    bounding_box = Column(JSONB)
    snippet_path = Column(Text)
    thumbnail_path = Column(Text)
    meta_data = Column(JSONB)
    status = Column(Enum(EventStatus), default=EventStatus.new)
    viewed_at = Column(DateTime)
    viewed_by = Column(String(64), ForeignKey('users.user_id'))
    notes = Column(Text)
    location = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    device = relationship("Device", back_populates="detection_events")
    config = relationship("DetectionConfig", back_populates="events")
    viewer = relationship("User", foreign_keys=[viewed_by])

class DetectionStat(Base):
    __tablename__ = "detection_stat"
    
    stat_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(64), ForeignKey('device.device_id'))
    date = Column(DateTime, default=datetime.utcnow)
    total_events = Column(Integer, default=0)
    by_class = Column(JSONB)
    peak_hour = Column(Integer)
    peak_hour_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    device = relationship("Device")

class DetectionPerformance(Base):
    __tablename__ = "detection_performance"
    
    performance_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(64), ForeignKey('device.device_id'))
    config_id = Column(String(64), ForeignKey('detection_config.config_id'))
    timestamp = Column(DateTime, default=datetime.utcnow)
    detection_time = Column(Float)
    preprocessing_time = Column(Float)
    postprocessing_time = Column(Float)
    frame_width = Column(Integer)
    frame_height = Column(Integer)
    objects_detected = Column(Integer)
    device = relationship("Device")
    config = relationship("DetectionConfig")

DATABASE_URL = "postgresql://postgres:admin123@localhost:5432/eyris_core_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 