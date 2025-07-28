from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
from api.heatmap_routes import heatmap_router
from src.database import Base, engine
import uvicorn
import logging
import asyncio
# from contextlib import asynccontextmanager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 事件订阅管理器实例
# from src.smartSchemer import smart_schemer

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """应用生命周期管理"""
    
#     # 启动时初始化事件订阅管理器
#     try:
#         await smart_schemer.initialize()
#     except Exception as e:
#         logger.error(f"事件订阅管理器初始化失败: {e}")
    
#     yield
    
#     # 关闭时清理事件订阅管理器
#     try:
#         await smart_schemer.shutdown()
#     except Exception as e:
#         logger.error(f"关闭事件订阅管理器失败: {e}")

# 创建FastAPI应用
app = FastAPI(
    title="Eyris Core API",
    description="视频监控系统核心API",
    version="1.0.0",
    # lifespan=lifespan
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

# 主函数
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001) 