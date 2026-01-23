from __future__ import annotations

from pathlib import Path
from typing import Optional
import logging

from fastapi import APIRouter, File, UploadFile, Request, Form
from starlette.responses import JSONResponse

from core import status_codes
from core.ids import generate_request_id
from core.response import ok, fail
from core.logging import set_request_id

from infra.tempfiles import TempDir, safe_filename

router = APIRouter(prefix="/audio", tags=["audio_qc"])
logger = logging.getLogger(__name__)


@router.post("/qc")
async def audio_qc(request: Request,
        audio_file: Optional[UploadFile] = File(default=None),
        task_id: Optional[str] = Form(default=None),
        ):
    # 先检查文件是否存在
    if audio_file is None or not audio_file.filename:
        # 文件不存在时使用默认ID
        temp_id = "unknown"
        logger.warning(f"[/qc] 缺失或者是空文件. filename=None")
        return JSONResponse(status_code=200, content=fail(temp_id, status_codes.MISSING_AUDIO))

    # 文件存在，生成或使用 request_id
    request_id = task_id if task_id else generate_request_id(audio_file.filename)
    set_request_id(request_id)
    logger.info(f"[/qc] 接受到音频质检请求. request_id={request_id}, filename={audio_file.filename}")

    cfg = request.app.state.cfg
    service = request.app.state.service
    stats = request.app.state.stats

    # 标记任务开始处理
    stats.add_processing(request_id)

    aqc_cfg = cfg.audio_qc
    max_bytes = aqc_cfg.max_file_size_mb * 1024 * 1024

    total = 0
    try:
        with TempDir(prefix="aqc_req_") as td:
            upload_name = safe_filename(audio_file.filename)
            src_path = td.path / upload_name
            logger.info(f"[/qc] 保存文件到临时文件. request_id={request_id}, temp_path={src_path}")

            try:
                with open(src_path, "wb") as f:
                    while True:
                        chunk = await audio_file.read(1024 * 1024)  # 1MB
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes:
                            logger.warning(f"[/qc] 文件太大超过{aqc_cfg.max_file_size_mb}. request_id={request_id}, size={total}bytes, max={max_bytes}bytes")
                            stats.finish_failed(request_id)
                            return JSONResponse(status_code=200, content=fail(request_id, status_codes.FILE_TOO_LARGE))
                        f.write(chunk)
            finally:
                await audio_file.close()

            if total <= 0:
                logger.warning(f"[/qc] 文件缺失或空文件. request_id={request_id}")
                stats.finish_failed(request_id)
                return JSONResponse(status_code=200, content=fail(request_id, status_codes.MISSING_AUDIO))

            logger.info(f"[/qc] 文件加载成功. request_id={request_id}, size={total}bytes")
            logger.info(f"[/qc] 开始检测... request_id={request_id}")

            result = await service.run(src_path=Path(src_path), file_size_bytes=total)

            if result.ok:
                logger.info(f"[/qc] 检测完成. request_id={request_id}, status_code={result.status_code}")
                logger.debug(f"[/qc] 结果数据: {result.data},request_id={request_id}")
                stats.finish_success(request_id)
                return JSONResponse(status_code=200, content=ok(request_id, result.data))

            logger.warning(f"[/qc] 检测处理失败. request_id={request_id}, status_code={result.status_code}")
            stats.finish_failed(request_id)
            return JSONResponse(status_code=200, content=fail(request_id, result.status_code))
    finally:
        # 显式清理 UploadFile 的内部临时文件（Starlette SpooledTemporaryFile）
        # 当文件 > 1MB 时，Starlette 会在 /tmp 中创建临时文件
        # 不显式删除会导致 /tmp 空间泄漏
        try:
            if audio_file is not None and hasattr(audio_file, 'file') and audio_file.file is not None:
                audio_file.file.close()  # 关闭 SpooledTemporaryFile 对象
                logger.debug(f"[/qc] UploadFile内部临时文件已关闭. request_id={request_id}")
        except Exception as e:
            logger.warning(f"[/qc] 关闭UploadFile临时文件时出错: {str(e)}, request_id={request_id}")



