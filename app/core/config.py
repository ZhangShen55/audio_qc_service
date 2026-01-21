# app/core/config.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

# Python 3.11+ 用 tomllib；3.10 可用 tomli 替代
import tomli as tomllib


@dataclass(frozen=True)
class ServerConfig:
    # 线程池：解码/特征/CPU 计算（异步接口会把重活丢到线程池）
    threadpool_workers: int = 8
    # GPU 推理并发（同一进程内，同一张卡建议 1~2）
    gpu_infer_concurrency: int = 1


@dataclass(frozen=True)
class AudioQCConfig:
    # VAD
    vad_model: str = "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
    device: str = "cuda:0"  # 或 "cpu"

    # 输出
    return_segments: bool = True
    merge_gap_ms: int = 120

    # 静音阈值
    silence_dbfs: float = -60.0

    # 服务保护
    max_file_size_mb: int = 300
    min_duration_ms: int = 180000      # 3min 默认
    max_duration_ms: int = 3300000     # 55min 默认

    # 清晰度（V1规则版）
    need_clarity: bool = True


@dataclass(frozen=True)
class AppConfig:
    server: ServerConfig = ServerConfig()
    audio_qc: AudioQCConfig = AudioQCConfig()


def _get_table(d: Dict[str, Any], key: str) -> Dict[str, Any]:
    v = d.get(key, {})
    return v if isinstance(v, dict) else {}


def load_config(path: str | Path = "config.toml") -> AppConfig:
    """
    从 config.toml 读取配置。
    - 缺失字段使用 dataclass 默认值
    - 类型尽量做强转，避免 toml 里写成字符串导致的类型问题
    """
    p = Path(path)
    raw = tomllib.loads(p.read_text(encoding="utf-8"))

    server = _get_table(raw, "server")
    audio = _get_table(raw, "audio_qc")

    server_cfg = ServerConfig(
        threadpool_workers=int(server.get("threadpool_workers", ServerConfig.threadpool_workers)),
        gpu_infer_concurrency=int(server.get("gpu_infer_concurrency", ServerConfig.gpu_infer_concurrency)),
    )

    audio_cfg = AudioQCConfig(
        vad_model=str(audio.get("vad_model", AudioQCConfig.vad_model)),
        device=str(audio.get("device", AudioQCConfig.device)),
        return_segments=bool(audio.get("return_segments", AudioQCConfig.return_segments)),
        merge_gap_ms=int(audio.get("merge_gap_ms", AudioQCConfig.merge_gap_ms)),
        silence_dbfs=float(audio.get("silence_dbfs", AudioQCConfig.silence_dbfs)),
        max_file_size_mb=int(audio.get("max_file_size_mb", AudioQCConfig.max_file_size_mb)),
        min_duration_ms=int(audio.get("min_duration_ms", AudioQCConfig.min_duration_ms)),
        max_duration_ms=int(audio.get("max_duration_ms", AudioQCConfig.max_duration_ms)),
        need_clarity=bool(audio.get("need_clarity", AudioQCConfig.need_clarity)),
    )

    # 基础校验：避免明显错误配置
    if server_cfg.threadpool_workers <= 0:
        raise ValueError("server.threadpool_workers must be > 0")
    if server_cfg.gpu_infer_concurrency <= 0:
        raise ValueError("server.gpu_infer_concurrency must be > 0")
    if audio_cfg.merge_gap_ms < 0:
        raise ValueError("audio_qc.merge_gap_ms must be >= 0")
    if audio_cfg.max_file_size_mb <= 0:
        raise ValueError("audio_qc.max_file_size_mb must be > 0")
    if audio_cfg.min_duration_ms < 0 or audio_cfg.max_duration_ms <= 0:
        raise ValueError("audio_qc min/max duration must be valid")
    if audio_cfg.min_duration_ms > audio_cfg.max_duration_ms:
        raise ValueError("audio_qc.min_duration_ms must be <= audio_qc.max_duration_ms")

    return AppConfig(server=server_cfg, audio_qc=audio_cfg)

