from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
from api.heatmap_routes import heatmap_router
from src.database import Base, engine
from src.db_migrations import (
    ensure_device_rtsp_columns,
    ensure_detection_config_stream_type,
    ensure_device_group_support,
    ensure_detection_config_group_mode,
    ensure_detection_log_device_id_nullable,
    ensure_crowd_analysis_job_extensions,
    ensure_vlm_inspection_tables,
    ensure_data_push_log_table,
    ensure_edge_server_platform_columns,
    ensure_device_monitor_method,
    ensure_alert_rule_tables,
    ensure_heatmap_dashboard_screen_name,
    ensure_heatmap_area_shape_type,
)
from src.env_loader import load_env_file
import uvicorn
import logging

load_env_file()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

# 创建数据库表
Base.metadata.create_all(bind=engine)
ensure_device_rtsp_columns(engine)
ensure_detection_config_stream_type(engine)
ensure_device_group_support(engine)
ensure_detection_config_group_mode(engine)
ensure_detection_log_device_id_nullable(engine)
ensure_crowd_analysis_job_extensions(engine)
ensure_vlm_inspection_tables(engine)
ensure_data_push_log_table(engine)
ensure_edge_server_platform_columns(engine)
ensure_device_monitor_method(engine)
ensure_alert_rule_tables(engine)
ensure_heatmap_dashboard_screen_name(engine)
ensure_heatmap_area_shape_type(engine)

# 创建FastAPI应用
app = FastAPI(
    title="Eyris Core API",
    description="视频监控系统核心API",
    version="1.0.0",
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含路由
app.include_router(router, prefix="/api/v1")
app.include_router(heatmap_router, prefix="/api/v1")
# 添加事件订阅相关的API接口
from api.base_smart_scheme import router as smart_scheme_router
app.include_router(smart_scheme_router, prefix="/api/v1")
# 添加数据监听相关的API接口
from api.base_data_listener import router as data_listener_router
app.include_router(data_listener_router, prefix="/api/v1")
# 添加数据大屏相关的API接口
from api.base_dashboard import router as dashboard_router
from api.dashboard_integrations import router as dashboard_integrations_router
from api.device_monitor_settings import router as device_monitor_settings_router
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(dashboard_integrations_router, prefix="/api/v1")
app.include_router(device_monitor_settings_router, prefix="/api/v1")

from api.device_group_routes import router as device_group_router
app.include_router(device_group_router, prefix="/api/v1")

from api.alert_rule_routes import router as alert_rule_router
app.include_router(alert_rule_router, prefix="/api/v1")

# 主函数
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
