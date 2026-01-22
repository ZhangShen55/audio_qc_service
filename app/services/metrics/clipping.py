# app/services/metrics/clipping.py
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class ClippingResult:
    count: int
    times_ms: list[int]  # 每个爆音事件的开始时间（毫秒）


def detect_clipping_events(
    x: np.ndarray,
    sr: int,
    clip_threshold: float = 0.99,
    min_event_samples: int = 10,
) -> ClippingResult:
    """
    检测数字削波(clipping)事件：
    - |x| >= clip_threshold 的连续区间算一次事件
    - 连续区间长度 < min_event_samples 的忽略
    返回事件计数和每个事件的开始时间点（毫秒）
    """
    if x.size == 0 or sr <= 0:
        return ClippingResult(count=0, times_ms=[])

    mask = np.abs(x) >= float(clip_threshold)
    if not mask.any():
        return ClippingResult(count=0, times_ms=[])

    # 找连续 True 区间
    idx = np.flatnonzero(mask)
    # 分割点：相邻索引不连续
    splits = np.where(np.diff(idx) > 1)[0]
    starts = np.r_[0, splits + 1]
    ends = np.r_[splits, len(idx) - 1]

    cnt = 0
    times_ms = []
    for s_i, e_i in zip(starts, ends):
        run_len = int(idx[e_i] - idx[s_i] + 1)
        if run_len >= int(min_event_samples):
            cnt += 1
            # 计算该事件开始时间（毫秒）
            start_sample = int(idx[s_i])
            start_time_ms = int(round(start_sample * 1000.0 / sr))
            times_ms.append(start_time_ms)
    
    return ClippingResult(count=cnt, times_ms=times_ms)
