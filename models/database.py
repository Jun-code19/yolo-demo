from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Integer, Float, Enum, ForeignKey, ARRAY, Text, SmallInteger
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import enum
from datetime import datetime

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

# 数据库连接配置
DATABASE_URL = "postgresql://postgres:admin123@localhost:5432/eyris_core_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 