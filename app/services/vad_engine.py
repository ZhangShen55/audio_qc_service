# app/services/vad_engine.py
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tempfile
import logging

from funasr import AutoModel


logger = logging.getLogger(__name__)


class VadInferError(RuntimeError):
    pass


@dataclass(frozen=True)
class VadOutput:
    segments_ms: list[list[int]]  # [[start_ms, end_ms], ...]


def _infer_segments_worker(model_id: str, device: str, wav_path: str) -> list[list[int]]:
    """
    在子进程中执行 VAD 推理（完全隔离，无线程安全问题）。

    每个进程独立加载模型，不共享 GPU 显存。
    """
    try:
        model = AutoModel(model=model_id, device=device, disable_update=True, disable_pbar=True)
        res = model.generate(input=wav_path)
        segments = _extract_segments_ms(res)
        return segments
    except Exception as e:
        raise VadInferError(f"VAD infer failed: {e}") from e


class VadEngine:
    """
    FunASR AutoModel 封装，使用进程池实现多进程推理。

    约定输出 segments_ms 的单位为毫秒。
    """

    def __init__(self, model_id: str, device: str, num_workers: int = 2):
        self.model_id = model_id
        self.device = device
        self.num_workers = num_workers
        # 创建进程池（每个 worker 进程独立加载模型）
        self.executor = ProcessPoolExecutor(max_workers=num_workers)
        self._warmup_done = False

    def warmup(self) -> None:
        """
        热加载所有 worker 进程中的 VAD 模型。

        在启动时执行，避免第一个请求的延迟。
        使用一个虚拟音频进行推理以加载模型到 GPU。
        """
        if self._warmup_done:
            logger.debug("[VAD] Warmup already done, skipping")
            return

        logger.info(f"[VAD] Starting warmup with {self.num_workers} workers...")

        # 生成虚拟 16k mono wav（100ms，用于快速推理）
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            dummy_wav_path = f.name
            try:
                import wave
                sr = 16000
                duration_ms = 100
                n_frames = sr * duration_ms // 1000
                with wave.open(dummy_wav_path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sr)
                    wf.writeframes(b"\x00\x00" * n_frames)

                # 提交 num_workers 个任务，每个 worker 进程执行一次推理
                futures = []
                for i in range(self.num_workers):
                    future = self.executor.submit(
                        _infer_segments_worker,
                        self.model_id,
                        self.device,
                        dummy_wav_path,
                    )
                    futures.append(future)

                # 等待所有 warmup 任务完成
                for i, future in enumerate(futures):
                    try:
                        future.result(timeout=300)
                        logger.debug(f"[VAD] Worker {i+1} warmup completed")
                    except Exception as e:
                        logger.error(f"[VAD] Worker {i+1} warmup failed: {e}")
                        raise

                logger.info(f"[VAD] All {self.num_workers} workers warmed up successfully")
                self._warmup_done = True
            finally:
                # 清理虚拟文件
                try:
                    Path(dummy_wav_path).unlink()
                except Exception:
                    pass

    def infer_segments_ms(self, wav_path: Path) -> VadOutput:
        """
        执行 VAD 推理（同步接口）。

        内部使用进程池异步执行，等待结果。
        """
        future = self.executor.submit(
            _infer_segments_worker,
            self.model_id,
            self.device,
            str(wav_path),
        )
        segments = future.result(timeout=300)  # 等待推理完成
        return VadOutput(segments_ms=segments)

    def infer_segments_ms_async(self, wav_path: Path):
        """
        执行 VAD 推理（异步接口）。

        返回 Future 对象，调用者可以 await 或轮询。
        """
        return self.executor.submit(
            _infer_segments_worker,
            self.model_id,
            self.device,
            str(wav_path),
        )

    def shutdown(self):
        """关闭进程池（清理资源）。"""
        self.executor.shutdown(wait=True)


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
