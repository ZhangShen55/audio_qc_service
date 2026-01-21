# app/services/metrics/clarity_v1.py
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy.signal import stft

from services.metrics.vad_utils import clamp01
from core.config import ClarityV1Config



@dataclass(frozen=True)
class ClarityDetail:
    snr_db: float
    hf_ratio: float
    spectral_flatness: float


def _spectral_flatness(power_spec: np.ndarray, eps: float = 1e-12) -> float:
    """
    power_spec: (freq, time) 的功率谱
    """
    p = np.maximum(power_spec, eps)
    geo = np.exp(np.mean(np.log(p), axis=0))
    arith = np.mean(p, axis=0)
    flat = geo / np.maximum(arith, eps)
    return float(np.mean(flat))


def _hf_ratio(freqs: np.ndarray, power_spec: np.ndarray, hf_lo: float = 3000.0, hf_hi: float = 8000.0) -> float:
    """
    计算高频能量比：E[hf_lo,hf_hi] / E[0,hf_hi]
    """
    f = freqs
    ps = power_spec

    hi_mask = (f >= hf_lo) & (f <= hf_hi)
    base_mask = (f >= 0.0) & (f <= hf_hi)

    e_hi = float(np.sum(ps[hi_mask, :]))
    e_base = float(np.sum(ps[base_mask, :])) + 1e-12
    return float(e_hi / e_base)


def _snr_db_from_segments(x: np.ndarray, sr: int, speech_segments_ms: list[list[int]]) -> float:
    """
    用 VAD 语音段估计 speech power，非语音段估计 noise power。
    简化实现：按样本区间做能量比。
    """
    n = x.size
    if n == 0:
        return -100.0

    # 构造 speech mask（样本级）
    speech = np.zeros(n, dtype=bool)
    for s_ms, e_ms in speech_segments_ms:
        s = int(round(s_ms * sr / 1000.0))
        e = int(round(e_ms * sr / 1000.0))
        s = max(0, min(n, s))
        e = max(0, min(n, e))
        if e > s:
            speech[s:e] = True

    if not speech.any():
        # 没有语音，SNR 定义上无意义，给一个很低值
        return -100.0

    ps = float(np.mean((x[speech] ** 2))) + 1e-12
    noise_part = x[~speech]
    if noise_part.size < sr:  # 非语音太少，退化用全局
        pn = float(np.mean((x ** 2))) + 1e-12
    else:
        pn = float(np.mean((noise_part ** 2))) + 1e-12

    return float(10.0 * np.log10(ps / pn))


def compute_clarity_v1(
    x: np.ndarray,
    sr: int,
    speech_segments_ms: list[list[int]],
    cfg: ClarityV1Config,
) -> tuple[float, ClarityDetail]:
    """
    清晰度 V1（规则版）：
    - SNR(dB)（用 VAD 分段估计）
    - 高频能量比 hf_ratio（3k~8k / 0~8k）
    - 谱平坦度 spectral_flatness（噪声/失真会抬高）
    输出：
    - clarity: 0~100
    - detail: 原始指标
    """
    # STFT
    # 20ms 窗，10ms hop
    nperseg = max(256, int(sr * (cfg.win_ms / 1000.0)))
    noverlap = max(0, nperseg - int(sr * (cfg.hop_ms / 1000.0)))

    f, t, Zxx = stft(x.astype(np.float32, copy=False), fs=sr, nperseg=nperseg, noverlap=noverlap, padded=False, boundary=None)
    power = np.abs(Zxx) ** 2

    snr_db = _snr_db_from_segments(x, sr, speech_segments_ms)
    hf_ratio = _hf_ratio(f, power, cfg.hf_lo_hz, min(cfg.hf_hi_hz, float(sr) / 2.0))

    flat = _spectral_flatness(power)
    # print(f"flat={flat:.4f}")

    # 归一化（可按业务调参）
    # snr_score: -5dB -> 0, 10dB -> 1
    snr_score = clamp01((snr_db - cfg.snr_min_db) / (cfg.snr_max_db - cfg.snr_min_db))
    # hf_score: 0.0 -> 0, 0.02 -> 1（闷音/带宽窄会很低）
    hf_score = clamp01(hf_ratio / cfg.hf_ref)
    # flat_score: 0.0 -> 1, 0.1 -> 0（越平坦越像噪声） flat越小越好
    flat_score = 1.0 - clamp01(flat / cfg.flat_ref)

    # print(f"flat_score={flat_score:.4f}")
    ws = np.array([cfg.w_snr, cfg.w_hf, cfg.w_flat], dtype=np.float64)
    ws = ws / max(1e-12, float(ws.sum()))
    clarity = 100.0 * (ws[0] * snr_score + ws[1] * hf_score + ws[2] * flat_score)
    detail = ClarityDetail(snr_db=float(snr_db), hf_ratio=float(hf_ratio), spectral_flatness=float(flat))
    return float(round(clarity, 4)), detail
