import argparse
import asyncio
import time
from statistics import mean

import aiohttp


async def one(session: aiohttp.ClientSession, url: str, file_path: str) -> float:
    t0 = time.time()
    data = aiohttp.FormData()
    data.add_field("file", open(file_path, "rb"), filename="x.bin", content_type="application/octet-stream")
    async with session.post(url, data=data) as resp:
        await resp.json()
    return (time.time() - t0) * 1000.0


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000/v1/audio/qc")
    ap.add_argument("--file", required=True)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--requests", type=int, default=20)
    args = ap.parse_args()

    lat = []
    connector = aiohttp.TCPConnector(limit=args.concurrency)
    timeout = aiohttp.ClientTimeout(total=None)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        sem = asyncio.Semaphore(args.concurrency)

        async def task():
            async with sem:
                l = await one(session, args.url, args.file)
                lat.append(l)

        await asyncio.gather(*[task() for _ in range(args.requests)])

    lat_sorted = sorted(lat)
    def p(pct):
        if not lat_sorted:
            return None
        k = int(round((pct / 100.0) * (len(lat_sorted) - 1)))
        return lat_sorted[k]

    print(f"count={len(lat)} avg={mean(lat):.2f}ms p50={p(50):.2f}ms p90={p(90):.2f}ms p99={p(99):.2f}ms")


if __name__ == "__main__":
    asyncio.run(main())
