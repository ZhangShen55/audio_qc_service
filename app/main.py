from __future__ import annotations

import asyncio

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import load_config
from core.logging import init_logging
from core.stats import ServiceStats
from infra.threadpool import create_threadpool
from infra.gpu_gate import create_gpu_semaphore

from services.vad_engine import VadEngine
from services.qc_service import AudioQCService

from api.routes import router as api_router
from api.health_router import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="Audio QC Service", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def on_startup() -> None:
        # Path(__file__).resolve() # output: /path/to/audio_qc_service/app/main.py
        CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.toml" # /path/to/audio_qc_service
        LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
        cfg = load_config(CONFIG_PATH)
        init_logging(cfg.server.log_level, log_dir=LOG_DIR)

        executor = create_threadpool(cfg)
        loop = asyncio.get_running_loop()
        loop.set_default_executor(executor)

        gpu_sem = create_gpu_semaphore(cfg)

        vad_engine = VadEngine(
            model_id=cfg.audio_qc.vad_model,
            device=cfg.audio_qc.device,
            num_workers=cfg.audio_qc.vad_num_workers,
        )

        # 热加载 VAD 模型到所有 worker 进程
        await asyncio.to_thread(vad_engine.warmup)

        service = AudioQCService(cfg=cfg, vad_engine=vad_engine, gpu_sem=gpu_sem)
        stats = ServiceStats()

        app.state.cfg = cfg
        app.state.executor = executor
        app.state.gpu_sem = gpu_sem
        app.state.vad_engine = vad_engine
        app.state.service = service
        app.state.stats = stats

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        executor = getattr(app.state, "executor", None)
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)

        # 清理 VAD 进程池
        vad_engine = getattr(app.state, "vad_engine", None)
        if vad_engine is not None:
            vad_engine.shutdown()

    app.include_router(health_router)
    app.include_router(api_router)
    return app


app = create_app()


# uvicorn main:app --app-dir app --host 0.0.0.0 --port 8090 --reload
# 后台挂起
# nohup uvicorn main:app --app-dir app --host 0.0.0.0 --port 8090 > uvicorn.log 2>&1 &
# sudo ss -lntp | grep ':8090'
