# app/services/audio_io.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf


class AudioReadError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioData:
    wav: np.ndarray          # float32, shape (n,)
    sample_rate: int
    duration_ms: int


def read_wav_mono_float32(path: Path) -> AudioData:
    """
    读取 wav（期望已经是 mono 16k），输出 float32 [-1, 1] 的一维数组。
    """
    try:
        data, sr = sf.read(str(path), dtype="float32", always_2d=False)
    except Exception as e:
        raise AudioReadError(f"soundfile read failed: {e}") from e

    if data is None:
        raise AudioReadError("empty audio buffer")

    # 若仍是多通道，降到 mono（理论上不会发生，因为 decoder 已经 -ac 1）
    if isinstance(data, np.ndarray) and data.ndim == 2:
        data = np.mean(data, axis=1).astype(np.float32)

    if not isinstance(data, np.ndarray) or data.ndim != 1:
        raise AudioReadError("invalid audio array shape")

    n = int(data.shape[0])
    if sr <= 0 or n <= 0:
        raise AudioReadError("invalid sample_rate or empty samples")

    duration_ms = int(round(n * 1000.0 / float(sr)))
    return AudioData(wav=data, sample_rate=int(sr), duration_ms=duration_ms)


def validate_audio_array(wav: np.ndarray) -> bool:
    """
    检测是否存在 NaN/Inf。
    """
    if wav.size == 0:
        return False
    if not np.isfinite(wav).all():
        return False
    return True
