from __future__ import annotations

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

router = APIRouter(prefix="/audio", tags=["health"])


@router.get("/health")
async def health_check(request: Request):
    """
    健康检查接口，返回服务状态信息
    """
    cfg = request.app.state.cfg
    stats = request.app.state.stats
    snapshot = stats.get_snapshot()
    
    return JSONResponse(status_code=200, content={
        "status": "healthy",
        "version": cfg.server.version,
        **snapshot
    })
