# app/infra/gpu_gate.py
from __future__ import annotations

import asyncio

from core.config import AppConfig


def create_gpu_semaphore(cfg: AppConfig) -> asyncio.Semaphore:
    """
    GPU 推理并发限制（受 VAD 模型线程安全限制）。

    实际并发行为：
    - Semaphore 允许最多 N 个请求并发到达 VAD 推理阶段
    - VadEngine 内部用互斥锁序列化所有推理调用（FunASR 不是线程安全的）
    - 结果：同一时刻最多 1 个推理执行，但支持 N 个请求的"管道式"处理

    优势对比排序队列：
    - 请求 A 在做 FFmpeg 解码时，请求 B-E 可以并行
    - 最大化 CPU 解码和 GPU 推理的重叠

    建议配置：
    - 单卡：1-2（避免 OOM 和过多上下文切换）
    - 多卡：可增加到 3-5

    示例：gpu_infer_concurrency = 2 时的流程
    ├─ Request 1: [解码] → [推理中] → [后处理]
    ├─ Request 2: [解码]        → [排队等待推理]
    ├─ Request 3: [排队等待解码]
    └─ ...
    """
    n = cfg.server.gpu_infer_concurrency
    return asyncio.Semaphore(n)
