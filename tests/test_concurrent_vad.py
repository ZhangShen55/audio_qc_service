"""
验证 GPU 信号量的真并发限制行为。
演示：7 个请求同时到达，gpu_infer_concurrency=5 时的处理过程。
"""

import asyncio
import time
from pathlib import Path


async def simulate_vad_inference(task_id: int, sem: asyncio.Semaphore, duration: float = 0.5):
    """
    模拟 VAD 推理：
    - 等待信号量（如果没有名额就排队）
    - 执行 GPU 推理（模拟耗时）
    - 释放信号量
    """
    acquire_start = time.time()
    await sem.acquire()
    acquire_time = time.time() - acquire_start

    infer_start = time.time()
    print(f"[{infer_start:.3f}] Task {task_id}: 获得 GPU 时间 {acquire_time:.3f}s，开始推理")

    # 模拟 GPU 推理耗时
    await asyncio.sleep(duration)

    infer_time = time.time() - infer_start
    print(f"[{time.time():.3f}] Task {task_id}: 推理完成，耗时 {infer_time:.3f}s")

    sem.release()


async def test_concurrent_vad():
    """
    场景：7 个请求同时到达，gpu_infer_concurrency=5

    预期行为：
    - Task 1-5: 立即获得信号量，开始推理
    - Task 6-7: 等待，直到 Task 1 或 2 完成释放信号量
    """
    gpu_infer_concurrency = 5
    total_tasks = 7

    sem = asyncio.Semaphore(gpu_infer_concurrency)

    print(f"\n=== 开始测试 ===")
    print(f"GPU 并发限制: {gpu_infer_concurrency}")
    print(f"总请求数: {total_tasks}")
    print(f"推理耗时: 0.5s\n")

    start_time = time.time()

    # 创建 7 个任务，同时提交
    tasks = [
        simulate_vad_inference(i + 1, sem, duration=0.5)
        for i in range(total_tasks)
    ]

    # 并发运行
    await asyncio.gather(*tasks)

    total_time = time.time() - start_time
    print(f"\n总耗时: {total_time:.3f}s")
    print(f"理论最少耗时: {0.5 + 0.5 + 0.5:.3f}s (5 并发 + 2 个任务序列等待)")
    print(f"\n=== 测试完成 ===\n")


if __name__ == "__main__":
    asyncio.run(test_concurrent_vad())
