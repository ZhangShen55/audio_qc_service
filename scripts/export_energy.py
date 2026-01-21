#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import stft


def ffmpeg_to_wav16k_mono(src: Path, dst: Path) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-ac", "1",
        "-ar", "16000",
        "-vn",
        "-f", "wav",
        str(dst),
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        err = p.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"ffmpeg failed: {err}")


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    x, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if isinstance(x, np.ndarray) and x.ndim == 2:  # just in case
        x = np.mean(x, axis=1).astype(np.float32)
    if not isinstance(x, np.ndarray) or x.ndim != 1:
        raise RuntimeError("invalid audio shape after decode")
    if x.size == 0 or sr <= 0:
        raise RuntimeError("empty audio or invalid sr")
    if not np.isfinite(x).all():
        raise RuntimeError("audio contains NaN/Inf")
    return x, int(sr)


def export_energy(
    x: np.ndarray,
    sr: int,
    out_csv: Path,
    out_json: Path,
    win_ms: float = 20.0,
    hop_ms: float = 10.0,
    hf_lo: float = 3000.0,
    hf_hi: float = 8000.0,
) -> None:
    nperseg = max(256, int(sr * win_ms / 1000.0))
    hop = max(1, int(sr * hop_ms / 1000.0))
    noverlap = max(0, nperseg - hop)

    f, t, Zxx = stft(
        x.astype(np.float32, copy=False),
        fs=sr,
        nperseg=nperseg,
        noverlap=noverlap,
        padded=False,
        boundary=None,
    )
    power = (np.abs(Zxx) ** 2).astype(np.float64)  # (freq, time)

    # 频段掩码（16k 采样时 Nyquist=8k，因此 hf_hi 会被夹到 <= 8k）
    nyq = sr / 2.0
    hf_hi_eff = min(hf_hi, nyq)
    base_hi_eff = min(8000.0, nyq)

    base_mask = (f >= 0.0) & (f <= base_hi_eff)
    hf_mask = (f >= hf_lo) & (f <= hf_hi_eff)

    e_base = np.sum(power[base_mask, :], axis=0)  # 每帧 0~8k 能量
    e_hf = np.sum(power[hf_mask, :], axis=0)      # 每帧 3~8k 能量
    hf_ratio = e_hf / (e_base + 1e-12)

    # 另外给你每帧 RMS(dBFS)（不依赖频域）
    # 这里用与 STFT 同 hop 对齐的时域滑窗估计
    frame_len = nperseg
    rms_db = []
    for i in range(len(t)):
        start = i * hop
        seg = x[start:start + frame_len]
        if seg.size == 0:
            rms_db.append(-120.0)
            continue
        r = float(np.sqrt(np.mean(seg * seg) + 1e-12))
        rms_db.append(20.0 * np.log10(max(r, 1e-12)))
    rms_db = np.array(rms_db, dtype=np.float64)

    # 写 CSV（每帧一行）
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8") as w:
        w.write("t_sec,e_0_8k,e_3_8k,hf_ratio,rms_dbfs\n")
        for i in range(len(t)):
            w.write(f"{t[i]:.6f},{e_base[i]:.10e},{e_hf[i]:.10e},{hf_ratio[i]:.6f},{rms_db[i]:.3f}\n")

    # 汇总 JSON
    duration_sec = float(x.size / sr)
    summary = {
        "sr": sr,
        "duration_sec": duration_sec,
        "stft": {
            "win_ms": win_ms,
            "hop_ms": hop_ms,
            "nperseg": nperseg,
            "hop_samples": hop,
            "noverlap": noverlap,
            "n_frames": int(len(t)),
        },
        "bands": {
            "base_band_hz": [0.0, float(base_hi_eff)],
            "hf_band_hz": [float(hf_lo), float(hf_hi_eff)],
        },
        "energy": {
            "total_e_0_8k": float(np.sum(e_base)),
            "total_e_3_8k": float(np.sum(e_hf)),
            "hf_ratio_total": float(np.sum(e_hf) / (np.sum(e_base) + 1e-12)),
            "hf_ratio_p50": float(np.percentile(hf_ratio, 50)),
            "hf_ratio_p90": float(np.percentile(hf_ratio, 90)),
            "rms_dbfs_p50": float(np.percentile(rms_db, 50)),
            "rms_dbfs_p90": float(np.percentile(rms_db, 90)),
        },
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="input audio file (wav/mp3/aac/...)")
    ap.add_argument("--out_dir", default="energy_out", help="output directory")
    ap.add_argument("--win_ms", type=float, default=20.0)
    ap.add_argument("--hop_ms", type=float, default=10.0)
    ap.add_argument("--hf_lo", type=float, default=3000.0)
    ap.add_argument("--hf_hi", type=float, default=8000.0)
    args = ap.parse_args()

    inp = Path(args.inp)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = inp.stem
    out_csv = out_dir / f"{stem}.energy.csv"
    out_json = out_dir / f"{stem}.summary.json"

    with tempfile.TemporaryDirectory(prefix="aqc_energy_") as td:
        wav16k = Path(td) / "test_audio/传播学_1124501_马道全_2025年4月24号8时30分.aac"
        ffmpeg_to_wav16k_mono(inp, wav16k)
        x, sr = read_wav(wav16k)
        export_energy(
            x, sr,
            out_csv=out_csv,
            out_json=out_json,
            win_ms=args.win_ms,
            hop_ms=args.hop_ms,
            hf_lo=args.hf_lo,
            hf_hi=args.hf_hi,
        )

    print(f"[OK] wrote:\n  {out_csv}\n  {out_json}")


if __name__ == "__main__":
    main()

# python /root/workspace/audio_qc_service/scripts/test_audio/法语音频.mp3 --out_dir /root/workspace/audio_qc_service/scripts/energy_out