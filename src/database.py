from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Integer, Float, Enum, ForeignKey, ARRAY, Text, SmallInteger, Index
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
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
    created_at = Column(DateTime, default=datetime.now)
    
    detection_configs = relationship("DetectionConfig", back_populates="device", cascade="all, delete-orphan")
    detection_events = relationship("DetectionEvent", back_populates="device", cascade="all, delete-orphan")

class AnalysisResult(Base):
    __tablename__ = "analysis_result"
    
    result_id = Column(Integer, primary_key=True)
    # video_id = Column(String(64), ForeignKey('video.video_id'))
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
    # video_id = Column(String(64), ForeignKey('video.video_id'))
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
    schedule_config = Column(JSONB)  # 定时检测配置
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
    confidence_threshold = Column(Float, default=0.5) # 置信度阈值，默认0.5
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
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:admin123@10.83.34.35:5432/eyris_core_db")
# else:
    # 生产环境使用Docker容器名
# DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:admin123@postgres:5432/yolo")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 添加DetectionLog表
class DetectionLog(Base):
    __tablename__ = "detection_log"
    
    log_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_id = Column(String(64), ForeignKey('detection_config.config_id'), nullable=False)
    device_id = Column(String(64), ForeignKey('device.device_id'), nullable=False)
    operation = Column(String(50), nullable=False)  # start, stop, auto_start, auto_stop
    status = Column(String(50))  # success, failed
    message = Column(Text)
    created_by = Column(String(64), ForeignKey('users.user_id'), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    # 关联
    config = relationship("DetectionConfig")
    device = relationship("Device")
    user = relationship("User", foreign_keys=[created_by]) 

class EdgeServer(Base):
    """边缘服务器模型"""
    __tablename__ = "edge_servers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="服务器名称")
    ip_address = Column(String(45), nullable=False, unique=True, comment="IP地址")
    port = Column(Integer, default=80, nullable=False, comment="端口号")
    description = Column(Text, comment="服务器描述")
    
    # 状态信息
    status = Column(String(20), default="unknown", comment="状态: online/offline/checking/unknown")
    last_checked = Column(DateTime(timezone=True), comment="最后检查时间")
    
    # 系统信息 (JSON格式存储)
    system_info = Column(JSONB, comment="系统信息")
    version_info = Column(JSONB, comment="版本信息")
    device_info = Column(JSONB, comment="设备信息")
    
    # 创建和更新时间
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 是否启用
    is_active = Column(Boolean, default=True, comment="是否启用")
    
    def __repr__(self):
        return f"<EdgeServer(id={self.id}, name='{self.name}', ip='{self.ip_address}')>" 

class ListenerType(enum.Enum):
    tcp = "tcp"
    mqtt = "mqtt"
    sdk = "sdk"
    http = "http"
    websocket = "websocket"

class ExternalEventType(enum.Enum):
    detection = "detection"
    alarm = "alarm"
    status = "status"
    command = "command"
    heartbeat = "heartbeat"
    other = "other"

class ListenerConfig(Base):
    __tablename__ = "listener_configs"
    
    config_id = Column(String, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    listener_type = Column(Enum(ListenerType), nullable=False)
    connection_config = Column(JSONB, nullable=False)  # 连接配置
    data_mapping = Column(JSONB)  # 数据映射规则
    filter_rules = Column(JSONB)  # 过滤规则
    
    # 新增：边缘设备和算法字段映射
    edge_device_mappings = Column(JSONB)  # 关联的边缘设备列表
    algorithm_field_mappings = Column(JSONB)  # 算法字段映射配置 {device_id: [engine_ids]}
    algorithm_specific_fields = Column(JSONB)  # 算法特定字段配置 {device_id: {engine_id: {field_configs}}}
    
    # 新增：设备和引擎名称映射（用于数据标准化时获取名称）
    device_name_mappings = Column(JSONB)  # 设备SN到名称的映射 {device_sn: device_name}
    engine_name_mappings = Column(JSONB)  # 引擎ID到名称的映射 {engine_id: engine_name}
    
    storage_enabled = Column(Boolean, default=True)
    push_enabled = Column(Boolean, default=False)
    push_config = Column(JSONB)  # 推送配置
    enabled = Column(Boolean, default=False)
    created_by = Column(String, ForeignKey('users.user_id'))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    creator = relationship("User")

class ExternalEvent(Base):
    __tablename__ = "external_events"
    
    event_id = Column(String, primary_key=True)
    config_id = Column(String, ForeignKey('listener_configs.config_id'), nullable=False)
    source_type = Column(Enum(ListenerType), nullable=False)
    event_type = Column(Enum(ExternalEventType), nullable=False)
    
    # 设备相关信息
    device_id = Column(String(64))  # 可选关联设备（保持向后兼容）
    device_sn = Column(String(100))  # 新增：设备SN码
    device_name = Column(String(200))  # 新增：设备名称
    channel_id = Column(String(50))  # 新增：视频通道ID
    engine_id = Column(String(50))   # 新增：算法引擎ID
    engine_name = Column(String(200))  # 新增：算法引擎名称
    
    location = Column(String(200))
    confidence = Column(Float)
    original_data = Column(JSONB, nullable=False)  # 原始数据
    normalized_data = Column(JSONB)  # 标准化数据
    algorithm_data = Column(JSONB)   # 新增：算法特定数据
    event_metadata = Column(JSONB)  # 元数据
    status = Column(Enum(EventStatus), default=EventStatus.new)
    processed = Column(Boolean, default=False)
    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    
    config = relationship("ListenerConfig")
    # device = relationship("Device")

class ListenerStatus(Base):
    __tablename__ = "listener_status"
    
    config_id = Column(String, ForeignKey('listener_configs.config_id'), primary_key=True)
    status = Column(String(20), default='stopped')  # running, stopped, error
    last_event_time = Column(DateTime)
    events_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    last_error = Column(Text)
    started_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    config = relationship("ListenerConfig")

# 添加索引
Index('idx_external_events_timestamp', ExternalEvent.timestamp)
Index('idx_external_events_type', ExternalEvent.event_type)
Index('idx_external_events_config', ExternalEvent.config_id)
Index('idx_listener_configs_type', ListenerConfig.listener_type)

# 热力图相关表模型
class HeatmapMap(Base):
    """热力图地图表"""
    __tablename__ = "heatmap_maps"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="地图名称")
    file_path = Column(String(500), nullable=False, comment="地图文件路径")
    file_name = Column(String(255), nullable=False, comment="原始文件名")
    file_size = Column(Integer, nullable=False, comment="文件大小(字节)")
    mime_type = Column(String(100), nullable=False, comment="文件MIME类型")
    width = Column(Integer, comment="图片宽度")
    height = Column(Integer, comment="图片高度")
    scale_factor = Column(Float, default=1.0, comment="比例尺(像素/米)")
    description = Column(Text, comment="地图描述")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    is_active = Column(Boolean, default=True, comment="是否激活")
    created_by = Column(String(100), comment="创建人")
    
    # 关系
    areas = relationship("HeatmapArea", back_populates="map", cascade="all, delete-orphan")
    dashboard_configs = relationship("HeatmapDashboardConfig", back_populates="map", cascade="all, delete-orphan")

class HeatmapArea(Base):
    """热力图区域表"""
    __tablename__ = "heatmap_areas"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    map_id = Column(Integer, ForeignKey('heatmap_maps.id'), nullable=False, comment="关联地图ID")
    name = Column(String(255), nullable=False, comment="区域名称")
    points = Column(JSONB, nullable=False, comment="区域多边形坐标点")
    color = Column(String(50), default='rgba(74, 144, 226, 0.5)', comment="区域颜色")
    area_size = Column(Float, default=0, comment="区域面积(平方米)")
    max_capacity = Column(Integer, comment="最大容量")
    description = Column(Text, comment="区域描述")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    is_active = Column(Boolean, default=True, comment="是否激活")
    
    # 关系
    map = relationship("HeatmapMap", back_populates="areas")
    bindings = relationship("HeatmapBinding", back_populates="area", cascade="all, delete-orphan")
    history = relationship("HeatmapHistory", back_populates="area", cascade="all, delete-orphan")

class HeatmapBinding(Base):
    """热力图数据绑定表"""
    __tablename__ = "heatmap_bindings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    area_id = Column(Integer, ForeignKey('heatmap_areas.id'), nullable=False, comment="关联区域ID")
    data_source_type = Column(String(50), nullable=False, comment="数据源类型(crowd_analysis,manual,api)")
    data_source_id = Column(String(100), comment="数据源ID(如人群分析任务ID)")
    data_source_name = Column(String(255), comment="数据源名称")
    refresh_interval = Column(Integer, default=30, comment="刷新间隔(秒)")
    last_update_time = Column(DateTime, comment="最后更新时间")
    current_count = Column(Integer, default=0, comment="当前人数")
    config = Column(JSONB, comment="绑定配置信息")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    is_active = Column(Boolean, default=True, comment="是否激活")
    
    # 关系
    area = relationship("HeatmapArea", back_populates="bindings")

class HeatmapDashboardConfig(Base):
    """热力图展板配置表"""
    __tablename__ = "heatmap_dashboard_config"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    map_id = Column(Integer, ForeignKey('heatmap_maps.id'), nullable=False, comment="关联地图ID")
    display_mode = Column(Enum('preview', 'mini', 'full', name='display_mode_enum'), default='preview', comment="显示模式")
    max_areas = Column(Integer, default=6, comment="最大显示区域数")
    refresh_interval = Column(Integer, default=30, comment="刷新间隔(秒)")
    config = Column(JSONB, comment="其他配置信息")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    is_active = Column(Boolean, default=True, comment="是否激活")
    
    # 关系
    map = relationship("HeatmapMap", back_populates="dashboard_configs")

class HeatmapHistory(Base):
    """热力图历史数据表 (可选，用于存储历史统计)"""
    __tablename__ = "heatmap_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    area_id = Column(Integer, ForeignKey('heatmap_areas.id'), nullable=False, comment="关联区域ID")
    people_count = Column(Integer, nullable=False, comment="人数")
    density = Column(Float, comment="人口密度")
    record_time = Column(DateTime, default=datetime.now, comment="记录时间")
    data_source = Column(String(100), comment="数据来源")
    
    # 关系
    area = relationship("HeatmapArea", back_populates="history")

# 添加热力图相关索引
Index('idx_heatmap_areas_map_id', HeatmapArea.map_id)
Index('idx_heatmap_bindings_area_id', HeatmapBinding.area_id)
Index('idx_heatmap_bindings_data_source', HeatmapBinding.data_source_type, HeatmapBinding.data_source_id)
Index('idx_heatmap_dashboard_config_map_id', HeatmapDashboardConfig.map_id)
Index('idx_heatmap_history_area_time', HeatmapHistory.area_id, HeatmapHistory.record_time)
Index('idx_heatmap_history_record_time', HeatmapHistory.record_time)

# 数据库依赖注入
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 