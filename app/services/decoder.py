# app/services/decoder.py
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FfmpegResult:
    cmd: list[str]
    returncode: int
    stderr: str


class DecodeError(RuntimeError):
    def __init__(self, msg: str, result: FfmpegResult | None = None):
        super().__init__(msg)
        self.result = result


def ffmpeg_to_wav16k_mono(src: Path, dst: Path) -> None:
    """
    使用 ffmpeg 将任意音频解码并重采样为:
      - wav (PCM)
      - 单声道
      - 16kHz
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-vn",
        "-f",
        "wav",
        str(dst),
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stderr = p.stderr.decode("utf-8", errors="ignore").strip()

    if p.returncode != 0:
        raise DecodeError(
            "ffmpeg decode/resample failed",
            FfmpegResult(cmd=cmd, returncode=p.returncode, stderr=stderr),
        )
