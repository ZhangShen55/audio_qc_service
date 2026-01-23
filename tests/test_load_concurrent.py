"""
并发压测脚本：测试多个请求同时到达时的 GPU 并发处理能力。

使用方法：
    python tests/test_load_concurrent.py --concurrency 50 --file /root/workspace/audio_qc_service/scripts/test_audio/5min.wav
    python tests/test_load_concurrent.py --concurrency 10 --file /path/to/audio.wav --iterations 2

可配置参数：
    --concurrency: 并发请求数（默认 7）
    --file: 音频文件路径（必需）
    --iterations: 重复轮次数（默认 1）
    --timeout: 单个请求超时（秒，默认 300）
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

import httpx


async def send_request(
    client: httpx.AsyncClient,
    task_id: int,
    file_path: str,
    url: str,
) -> dict:
    """
    发送单个请求，记录耗时和结果。
    """
    start_time = time.time()

    try:
        with open(file_path, "rb") as f:
            files = {"audio_file": ("audio.wav", f, "audio/wav")}
            response = await client.post(
                url,
                files=files,
                timeout=300,
            )
            elapsed = time.time() - start_time

            data = response.json() if response.status_code == 200 else {}
            return {
                "task_id": task_id,
                "status_code": response.status_code,
                "elapsed": elapsed,
                "ok": response.status_code == 200 and data.get("status_code") == 0,
                "data": data,
                "error": None,
            }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "task_id": task_id,
            "status_code": None,
            "elapsed": elapsed,
            "ok": False,
            "data": None,
            "error": str(e),
        }


async def run_concurrent_test(
    concurrency: int,
    file_path: str,
    iterations: int = 1,
    base_url: str = "http://localhost:8090",
) -> dict:
    """
    运行并发压测。

    返回统计结果：
    {
        "total_requests": int,
        "successful": int,
        "failed": int,
        "total_elapsed": float,
        "min_latency": float,
        "max_latency": float,
        "avg_latency": float,
        "requests_per_second": float,
        "details": [...]
    }
    """
    url = f"{base_url}/audio/qc"

    if not Path(file_path).exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
    print(f"\n=== 并发压测开始 ===")
    print(f"文件: {file_path}")
    print(f"文件大小: {file_size_mb:.2f} MB")
    print(f"并发数: {concurrency}")
    print(f"轮次: {iterations}")
    print(f"服务地址: {base_url}")
    print()

    all_results = []
    test_start = time.time()

    async with httpx.AsyncClient() as client:
        for iteration in range(iterations):
            iteration_start = time.time()

            # 创建并发任务
            tasks = [
                send_request(client, concurrency * iteration + i + 1, file_path, url)
                for i in range(concurrency)
            ]

            # 并发执行
            print(f"[轮次 {iteration + 1}/{iterations}] 发送 {concurrency} 个请求...")
            results = await asyncio.gather(*tasks)
            all_results.extend(results)

            iteration_elapsed = time.time() - iteration_start

            # 统计本轮
            successful = sum(1 for r in results if r["ok"])
            failed = concurrency - successful
            avg_latency = sum(r["elapsed"] for r in results) / concurrency

            print(
                f"  成功: {successful}/{concurrency}, 平均耗时: {avg_latency:.2f}s, 轮次耗时: {iteration_elapsed:.2f}s"
            )

    total_elapsed = time.time() - test_start

    # 汇总统计
    successful = sum(1 for r in all_results if r["ok"])
    failed = len(all_results) - successful
    latencies = [r["elapsed"] for r in all_results if r["elapsed"] > 0]

    return {
        "total_requests": len(all_results),
        "successful": successful,
        "failed": failed,
        "total_elapsed": total_elapsed,
        "min_latency": min(latencies) if latencies else 0,
        "max_latency": max(latencies) if latencies else 0,
        "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
        "requests_per_second": len(all_results) / total_elapsed if total_elapsed > 0 else 0,
        "details": all_results,
    }


def print_results(results: dict) -> None:
    """
    格式化打印结果。
    """
    print(f"\n=== 压测结果 ===")
    print(f"总请求数: {results['total_requests']}")
    print(f"成功: {results['successful']}")
    print(f"失败: {results['failed']}")
    print(f"成功率: {results['successful'] / results['total_requests'] * 100:.1f}%")
    print(f"\n耗时统计:")
    print(f"  总耗时: {results['total_elapsed']:.2f}s")
    print(f"  最小延迟: {results['min_latency']:.2f}s")
    print(f"  最大延迟: {results['max_latency']:.2f}s")
    print(f"  平均延迟: {results['avg_latency']:.2f}s")
    print(f"  吞吐量: {results['requests_per_second']:.2f} req/s")

    # 详细信息
    if results["failed"] > 0:
        print(f"\n失败的请求:")
        for r in results["details"]:
            if not r["ok"]:
                print(f"  Task {r['task_id']}: {r['error']}")


async def main():
    parser = argparse.ArgumentParser(
        description="GPU 并发推理压测脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python tests/test_load_concurrent.py --concurrency 7 --file audio.wav
  python tests/test_load_concurrent.py --concurrency 10 --file audio.wav --iterations 2
        """,
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=7,
        help="并发请求数 (默认: 7)",
    )
    parser.add_argument(
        "--file",
        type=str,
        required=True,
        help="音频文件路径 (必需)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="重复轮次 (默认: 1)",
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:8090",
        help="服务地址 (默认: http://localhost:8090)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="单个请求超时 (秒，默认: 300)",
    )

    args = parser.parse_args()

    try:
        results = await run_concurrent_test(
            concurrency=args.concurrency,
            file_path=args.file,
            iterations=args.iterations,
            base_url=args.url,
        )
        print_results(results)
        sys.exit(0 if results["failed"] == 0 else 1)
    except FileNotFoundError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
