# app/services/vad_engine.py
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from funasr import AutoModel


class VadInferError(RuntimeError):
    pass


# 全局互斥锁：FunASR AutoModel 不是线程安全的，需要保护并发调用
_vad_infer_lock = threading.Lock()


@dataclass(frozen=True)
class VadOutput:
    segments_ms: list[list[int]]  # [[start_ms, end_ms], ...]


class VadEngine:
    """
    FunASR AutoModel 封装。
    约定输出 segments_ms 的单位为毫秒。
    """

    def __init__(self, model_id: str, device: str):
        self.model_id = model_id
        self.device = device
        self.model = AutoModel(model=model_id, device=device, disable_update=True)

    def infer_segments_ms(self, wav_path: Path) -> VadOutput:
        """
        执行 VAD 推理，用互斥锁保证线程安全。

        由于 FunASR AutoModel 内部不是线程安全的（可能访问共享缓冲区），
        多个线程同时调用 model.generate() 会导致内存竞争。
        所以用全局互斥锁序列化所有 VAD 推理调用。
        """
        try:
            with _vad_infer_lock:
                res = self.model.generate(input=str(wav_path))
        except Exception as e:
            raise VadInferError(f"VAD infer failed: {e}") from e

        segments = _extract_segments_ms(res)
        return VadOutput(segments_ms=segments)


def _extract_segments_ms(res: Any) -> list[list[int]]:
    """
    兼容不同 FunASR 版本的返回结构：
    - 直接 [[beg, end], ...]
    - [{"value": [[beg,end], ...], ...}]
    - {"value": [[beg,end], ...], ...}
    """
    # case 1: already list[list[int]]
    if isinstance(res, list) and res and isinstance(res[0], list):
        if len(res[0]) == 2 and all(isinstance(x, (int, float)) for x in res[0]):
            return [[int(round(a)), int(round(b))] for a, b in res]

    # case 2: list of dict
    if isinstance(res, list) and res and isinstance(res[0], dict):
        d0 = res[0]
        if "value" in d0 and isinstance(d0["value"], list):
            v = d0["value"]
            if v and isinstance(v[0], list) and len(v[0]) == 2:
                return [[int(round(a)), int(round(b))] for a, b in v]

    # case 3: dict
    if isinstance(res, dict) and "value" in res and isinstance(res["value"], list):
        v = res["value"]
        if v and isinstance(v[0], list) and len(v[0]) == 2:
            return [[int(round(a)), int(round(b))] for a, b in v]

    # empty or unrecognized -> treat as no speech
    return []
