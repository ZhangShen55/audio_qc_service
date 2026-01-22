# app/services/qc_service.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import tempfile
import logging

import numpy as np

from core.config import AppConfig
from core import status_codes

from services.decoder import ffmpeg_to_wav16k_mono, DecodeError
from services.audio_io import read_wav_mono_float32, validate_audio_array, AudioReadError
from services.vad_engine import VadEngine, VadInferError
from services.metrics.vad_utils import merge_segments_ms, speech_ms_from_segments, clamp01
from services.metrics.silence import is_silent_by_frames
from services.metrics.clipping import count_clipping_events
from services.metrics.clarity_v1 import compute_clarity_v1

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QCResult:
    ok: bool
    status_code: int
    data: dict


class AudioQCService:
    """
    主业务编排：
    - 文件大小检查
    - ffmpeg 解码+重采样到 mono16k wav（临时文件）
    - 读取 wav，校验采样率、时长范围、数据有效性
    - VAD 推理 -> segments_ms 合并 -> speech_ratio
    - 静音、爆音、清晰度(V1) 计算
    """

    def __init__(
        self,
        cfg: AppConfig,
        vad_engine: VadEngine,
        gpu_sem: asyncio.Semaphore | None = None,
    ):
        self.cfg = cfg
        self.vad_engine = vad_engine
        self.gpu_sem = gpu_sem

    async def run(self, src_path: Path, file_size_bytes: int) -> QCResult:
        aqc = self.cfg.audio_qc

        # 1003: 文件过大
        if file_size_bytes > aqc.max_file_size_mb * 1024 * 1024:
            logger.warning(f"[qc_service] File size check failed. size={file_size_bytes}bytes, max={aqc.max_file_size_mb}MB")
            return QCResult(ok=False, status_code=status_codes.FILE_TOO_LARGE, data={})

        logger.info(f"[qc_service] Starting FFmpeg decode and resample. file_size={file_size_bytes}bytes")

        # 临时 wav 输出
        with tempfile.TemporaryDirectory(prefix="aqc_") as td:
            td_path = Path(td)
            wav_path = td_path / "input_16k_mono.wav"

            # 解码 + 重采样
            try:
                ffmpeg_to_wav16k_mono(src_path, wav_path)
                logger.debug(f"[qc_service] FFmpeg decode completed successfully. wav_path={wav_path}")
            except DecodeError as e:
                logger.error(f"[qc_service] FFmpeg decode/resample failed. error={str(e)}")
                return QCResult(ok=False, status_code=status_codes.DECODE_FAILED, data={})
            except Exception as e:
                # 兜底按解码失败
                logger.error(f"[qc_service] Unexpected error during decode. error={str(e)}")
                return QCResult(ok=False, status_code=status_codes.DECODE_FAILED, data={})

            # 读取 wav
            logger.debug(f"[qc_service] Reading WAV file. wav_path={wav_path}")
            try:
                audio = read_wav_mono_float32(wav_path)
                logger.debug(f"[qc_service] WAV file read successfully. sample_rate={audio.sample_rate}, duration_ms={audio.duration_ms}")
            except AudioReadError as e:
                logger.error(f"[qc_service] Failed to read WAV file. error={str(e)}")
                return QCResult(ok=False, status_code=status_codes.INVALID_AUDIO, data={})

            # 采样率/声道校验（理论上不会失败，因为 ffmpeg 强制了）
            if audio.sample_rate != 16000:
                logger.warning(f"[qc_service] Invalid sample rate. sample_rate={audio.sample_rate}")
                return QCResult(ok=False, status_code=status_codes.RESAMPLE_FAILED, data={})

            # 2003: NaN/Inf/空
            if not validate_audio_array(audio.wav):
                logger.warning(f"[qc_service] Audio array validation failed (NaN/Inf/empty)")
                return QCResult(ok=False, status_code=status_codes.INVALID_AUDIO, data={})

            # 1002: 时长范围（min/max 都来自 config，可改）
            if not (aqc.min_duration_ms <= audio.duration_ms <= aqc.max_duration_ms):
                logger.warning(f"[qc_service] Duration out of range. duration_ms={audio.duration_ms}, min={aqc.min_duration_ms}, max={aqc.max_duration_ms}")
                return QCResult(ok=False, status_code=status_codes.DURATION_OUT_OF_RANGE, data={})

            # 计算静音
            logger.debug(f"[qc_service] Computing silence detection. silence_dbfs={aqc.silence_dbfs}")
            silent = is_silent_by_frames(
                x=audio.wav,
                sr=audio.sample_rate,
                silence_dbfs=aqc.silence_dbfs,
            )
            logger.debug(f"[qc_service] Silence detection completed. is_silent={silent}")

            # VAD 推理（多进程池处理，天然线程安全）
            #
            # 并发流程说明：
            # 1. Semaphore.acquire() - 最多 N 个请求并发到达 VAD 阶段
            # 2. asyncio.to_thread() - 在线程池线程中执行推理
            # 3. VadEngine.infer_segments_ms() - 提交到进程池异步执行
            # 4. 各进程独立加载模型，完全隔离，无线程竞争
            # 5. Semaphore.release() - 释放信号量给下一个请求
            logger.info(f"[qc_service] Starting VAD inference")
            try:
                if self.gpu_sem is not None:
                    await self.gpu_sem.acquire()
                try:
                    vad_out = await asyncio.to_thread(self.vad_engine.infer_segments_ms, wav_path)
                    logger.debug(f"[qc_service] VAD inference completed. segments_count={len(vad_out.segments_ms)}")
                finally:
                    if self.gpu_sem is not None:
                        self.gpu_sem.release()
            except VadInferError as e:
                logger.error(f"[qc_service] VAD inference error. error={str(e)}")
                return QCResult(ok=False, status_code=status_codes.VAD_INFER_FAILED, data={})
            except Exception as e:
                logger.error(f"[qc_service] Unexpected error during VAD inference. error={str(e)}")
                return QCResult(ok=False, status_code=status_codes.VAD_INFER_FAILED, data={})

            # segments 合并
            logger.debug(f"[qc_service] Original VAD segments: {vad_out.segments_ms}")
            merged = merge_segments_ms(vad_out.segments_ms, aqc.merge_gap_ms)
            logger.debug(f"[qc_service] Merged VAD segments (merge_gap_ms={aqc.merge_gap_ms}): {merged}")

            speech_ms = speech_ms_from_segments(merged)
            speech_ratio = float(round(clamp01(speech_ms / max(1, audio.duration_ms)), 4))
            logger.debug(f"[qc_service] Speech analysis completed. speech_ms={speech_ms}, speech_ratio={speech_ratio}")

            # has_speech：可按业务再调阈值，这里给个稳妥的最小语音 300ms
            has_speech = speech_ms >= 300
            logger.debug(f"[qc_service] Speech detection result. has_speech={has_speech}")

            # 爆音次数
            logger.debug(f"[qc_service] Computing clipping events")
            clip_count = count_clipping_events(audio.wav)
            logger.debug(f"[qc_service] Clipping detection completed. clip_count={clip_count}")

            # 清晰度（V1规则版）
            if aqc.need_clarity:
                logger.debug(f"[qc_service] Computing clarity score (V1)")
                clarity, detail = compute_clarity_v1(
                                    audio.wav,
                                    audio.sample_rate,
                                    merged,
                                    self.cfg.audio_qc.clarity_v1,
                                )
                logger.debug(f"[qc_service] Clarity computation completed. clarity={clarity}, snr_db={detail.snr_db}, hf_ratio={detail.hf_ratio}, spectral_flatness={detail.spectral_flatness}")
                clarity_detail = {
                    "snr_db": float(round(detail.snr_db, 4)),
                    "hf_ratio": float(round(detail.hf_ratio, 6)),
                    "spectral_flatness": float(round(detail.spectral_flatness, 6)),
                }
            else:
                logger.debug(f"[qc_service] Clarity computation skipped (need_clarity=False)")
                clarity = None
                clarity_detail = None

            # 组装 data（符合你给的结构 + 你采纳的工程建议）
            data = {
                "is_silent": bool(silent),
                "has_speech": bool(has_speech),
                "speech_ratio": float(speech_ratio),
                "clip_count": int(clip_count),
                "clarity": clarity,                 # need_clarity=false 时为 null
                "clarity_detail": clarity_detail,   # need_clarity=false 时为 null
                "vad": {
                    "segments_ms": merged if aqc.return_segments else [],
                    "speech_ms": int(speech_ms),
                },
            }

            logger.info(f"[qc_service] Audio QC processing complete. All metrics computed successfully")
            return QCResult(ok=True, status_code=status_codes.OK, data=data)

