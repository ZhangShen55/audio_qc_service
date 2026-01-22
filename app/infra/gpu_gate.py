# app/infra/gpu_gate.py
from __future__ import annotations

import asyncio

from core.config import AppConfig


def create_gpu_semaphore(cfg: AppConfig) -> asyncio.Semaphore:
    """
    GPU 推理并发限制（多进程隔离）。

    实际并发行为：
    - Semaphore 允许最多 N 个请求并发到达 VAD 推理阶段
    - VadEngine 内部使用 ProcessPoolExecutor（进程池）执行推理
    - 每个进程独立加载 VAD 模型，天然线程安全，无内存竞争
    - 结果：实现管道式处理，充分利用 CPU/GPU

    优势：
    - 进程隔离：避免任何共享状态问题
    - 真正并发：多个进程可并行利用 GPU（受 GPU 调度限制）
    - 解码并行：请求 A 在解码时，请求 B-E 可并行

    建议配置：
    - gpu_infer_concurrency：HTTP 并发数控制（默认 5）
    - audio_qc.vad_num_workers：VAD 进程池大小（建议 2-3）

    示例：8 个 HTTP 并发，2 个 VAD 进程
    ├─ Request 1-8 并行执行 FFmpeg 解码（CPU）
    ├─ Request 1-2 获得 GPU 信号量 → 提交到 VAD 进程 1-2
    ├─ Request 3-8 排队等待 GPU 信号量
    └─ 进程 1-2 独立执行推理（完全隔离）

    注意：
    - gpu_infer_concurrency 和 vad_num_workers 是两个独立参数
    - 不要简单地将 HTTP 并发数配置成进程数（显存浪费）
    """
    n = cfg.server.gpu_infer_concurrency
    return asyncio.Semaphore(n)
