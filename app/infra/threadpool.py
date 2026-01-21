# app/infra/threadpool.py
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from core.config import AppConfig


def create_threadpool(cfg: AppConfig) -> ThreadPoolExecutor:
    """
    创建线程池：用于解码/特征/CPU 密集任务的 offload，避免阻塞事件循环。
    """
    workers = cfg.server.threadpool_workers
    return ThreadPoolExecutor(max_workers=workers, thread_name_prefix="aqc")
