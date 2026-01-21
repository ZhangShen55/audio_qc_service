# app/infra/gpu_gate.py
from __future__ import annotations

import asyncio

from core.config import AppConfig


def create_gpu_semaphore(cfg: AppConfig) -> asyncio.Semaphore:
    """
    同一进程内 GPU 推理并发限流。
    单卡通常建议 1~2；太大会让 latency 抖动并可能引发显存峰值。
    """
    n = cfg.server.gpu_infer_concurrency
    return asyncio.Semaphore(n)
