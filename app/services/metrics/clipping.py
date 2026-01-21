# app/services/metrics/clipping.py
from __future__ import annotations

import numpy as np


def count_clipping_events(
    x: np.ndarray,
    clip_threshold: float = 0.99,
    min_event_samples: int = 10,
) -> int:
    """
    统计数字削波(clipping)事件次数：
    - |x| >= clip_threshold 的连续区间算一次事件
    - 连续区间长度 < min_event_samples 的忽略
    """
    if x.size == 0:
        return 0

    mask = np.abs(x) >= float(clip_threshold)
    if not mask.any():
        return 0

    # 找连续 True 区间
    idx = np.flatnonzero(mask)
    # 分割点：相邻索引不连续
    splits = np.where(np.diff(idx) > 1)[0]
    starts = np.r_[0, splits + 1]
    ends = np.r_[splits, len(idx) - 1]

    cnt = 0
    for s_i, e_i in zip(starts, ends):
        run_len = int(idx[e_i] - idx[s_i] + 1)
        if run_len >= int(min_event_samples):
            cnt += 1
    return cnt
