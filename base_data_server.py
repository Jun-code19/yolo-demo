from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
from api.heatmap_routes import heatmap_router
from src.database import Base, engine
import uvicorn
import logging
import asyncio

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

# 创建数据库表
Base.metadata.create_all(bind=engine)

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
app.include_router(dashboard_router, prefix="/api/v1")

# 主函数
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001) 