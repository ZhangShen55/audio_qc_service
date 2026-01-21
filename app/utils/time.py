# app/utils/time.py
from __future__ import annotations

import time
from dataclasses import dataclass


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class Stopwatch:
    """
    简单计时器，用于统计处理耗时（如需要可以打日志或返回 meta）
    """
    start_ms: int = 0

    def __post_init__(self) -> None:
        self.start_ms = now_ms()

    def elapsed_ms(self) -> int:
        return now_ms() - self.start_ms
