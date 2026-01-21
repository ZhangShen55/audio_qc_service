# app/services/metrics/vad_utils.py
from __future__ import annotations

from typing import List


def merge_segments_ms(segments_ms: List[List[int]], merge_gap_ms: int) -> List[List[int]]:
    """
    合并重叠/相邻片段，避免重复计时。
    merge_gap_ms：允许的间隔，小于等于该间隔视为同一段。
    """
    if not segments_ms:
        return []

    segs = sorted(segments_ms, key=lambda x: x[0])
    merged: List[List[int]] = [segs[0][:]]

    for s, e in segs[1:]:
        ps, pe = merged[-1]
        if s <= pe + merge_gap_ms:
            merged[-1][1] = max(pe, e)
        else:
            merged.append([s, e])

    # 清理非法段
    out: List[List[int]] = []
    for s, e in merged:
        s_i, e_i = int(s), int(e)
        if e_i > s_i:
            out.append([s_i, e_i])
    return out


def speech_ms_from_segments(segments_ms: List[List[int]]) -> int:
    return int(sum(max(0, e - s) for s, e in segments_ms))


def clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x
