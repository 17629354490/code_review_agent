"""FastAPI 应用入口：注册路由、启动后台 Worker。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import settings
from app.api.v1 import review, webhook
from app.worker import start_background_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时启动 Worker，关闭时不做特殊处理。"""
    worker_thread = start_background_worker()
    yield
    # 如需优雅关闭，可在这里 set stop_event 并 join worker_thread


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="代码审查智能体 API：触发审查、查询任务、获取报告",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(review.router, prefix=settings.api_prefix)
app.include_router(webhook.router, prefix=settings.api_prefix)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}
