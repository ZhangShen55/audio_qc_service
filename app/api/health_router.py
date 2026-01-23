from __future__ import annotations

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

router = APIRouter(prefix="/audio", tags=["health"])


@router.get("/health")
async def health_check(request: Request):
    """
    健康检查接口，返回服务状态信息
    
    应答参数说明：
    | 参数名              | 类型           | 说明                                           |
    |---------------------|---------------|------------------------------------------------|
    | status              | string        | 服务状态，固定返回 "healthy"                    |
    | version             | string        | 服务版本号                                      |
    | start_time          | string        | 服务启动时间（格式：YYYY-MM-DD HH:MM:SS）       |
    | uptime_seconds      | int           | 运行时长（秒）                                  |
    | uptime_formatted    | string        | 格式化的运行时长（如："1d 2h 30m 15s"）         |
    | total_requests      | int           | 接收到的总请求数                                |
    | success_count       | int           | 成功处理的请求数                                |
    | failed_count        | int           | 处理失败的请求数                                |
    | processing_count    | int           | 正在处理中的任务数量                            |
    | processing_ids      | array[string] | 正在处理中的任务ID列表（按字母顺序排序）         |
    | queued_count        | int           | 排队等待的任务数量                              |
    | queued_ids          | array[string] | 排队等待的任务ID列表（按字母顺序排序）           |
    
    响应示例：
    {
      "status": "healthy",
      "version": "1.0.0",
      "start_time": "2026-01-23 10:00:00",
      "uptime_seconds": 3600,
      "uptime_formatted": "1h 0m 0s",
      "total_requests": 1250,
      "success_count": 1180,
      "failed_count": 70,
      "processing_count": 2,
      "processing_ids": ["audio1_a1b2c3d4", "audio2_x9y8z7w6"],
      "queued_count": 0,
      "queued_ids": []
    }
    """
    cfg = request.app.state.cfg
    stats = request.app.state.stats
    snapshot = stats.get_snapshot()
    
    return JSONResponse(status_code=200, content={
        "status": "healthy",
        "version": cfg.server.version,
        **snapshot
    })
