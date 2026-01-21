# app/services/metrics/silence.py
from __future__ import annotations

import numpy as np


def rms_dbfs(x: np.ndarray, eps: float = 1e-12) -> float:
    """
    计算信号 RMS 的 dBFS（假设 x 已经归一到 [-1,1]）。
    """
    x = x.astype(np.float32, copy=False)
    r = float(np.sqrt(np.mean(x * x) + eps))
    return 20.0 * float(np.log10(max(r, eps)))


def is_silent_by_frames(
    x: np.ndarray,
    sr: int,
    silence_dbfs: float,
    frame_ms: int = 20,
    hop_ms: int = 10,
    active_ratio_thresh: float = 0.05,
) -> bool:
    """
    静音判定：
    - 分帧计算帧 RMS dBFS
    - 帧 dBFS > silence_dbfs 认为“有效帧”
    - 有效帧占比 < active_ratio_thresh 判定静音
    """
    if x.size == 0 or sr <= 0:
        return True

    frame_len = int(sr * frame_ms / 1000)
    hop = int(sr * hop_ms / 1000)
    if frame_len <= 0 or hop <= 0 or x.size < frame_len:
        # 太短就按整体 RMS 判
        return rms_dbfs(x) <= silence_dbfs

    # 逐帧 RMS
    n_frames = 1 + (x.size - frame_len) // hop
    act = 0
    for i in range(n_frames):
        seg = x[i * hop : i * hop + frame_len]
        if rms_dbfs(seg) > silence_dbfs:
            act += 1

    active_ratio = act / max(1, n_frames)
    return active_ratio < active_ratio_thresh
