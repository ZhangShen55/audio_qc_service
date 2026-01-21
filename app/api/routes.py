from __future__ import annotations

from pathlib import Path
from typing import Optional
import logging

from fastapi import APIRouter, File, UploadFile, Request
from starlette.responses import JSONResponse

from core import status_codes
from core.ids import new_request_id
from core.response import ok, fail
from core.logging import set_request_id

from infra.tempfiles import TempDir, safe_filename

router = APIRouter(prefix="/v1/audio", tags=["audio_qc"])
logger = logging.getLogger(__name__)


@router.post("/qc")
async def audio_qc(request: Request, 
        file: Optional[UploadFile] = File(default=None),
        task_id: Optional[str] = None
        ):
    request_id = new_request_id() if task_id is None else task_id
    set_request_id(request_id)
    logger.info(f"[START] Audio QC request received. request_id={request_id}, filename={file.filename if file else 'None'}")

    if file is None or not file.filename:
        logger.warning(f"[FAIL] Missing or empty file. request_id={request_id}")
        return JSONResponse(status_code=200, content=fail(request_id, status_codes.MISSING_AUDIO))

    cfg = request.app.state.cfg
    service = request.app.state.service

    aqc_cfg = cfg.audio_qc
    max_bytes = aqc_cfg.max_file_size_mb * 1024 * 1024

    total = 0
    with TempDir(prefix="aqc_req_") as td:
        upload_name = safe_filename(file.filename)
        src_path = td.path / upload_name
        logger.debug(f"[UPLOAD] Saving file to temp directory. request_id={request_id}, temp_path={src_path}")

        try:
            with open(src_path, "wb") as f:
                while True:
                    chunk = await file.read(1024 * 1024)  # 1MB
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        logger.warning(f"[FAIL] File too large. request_id={request_id}, size={total}bytes, max={max_bytes}bytes")
                        return JSONResponse(status_code=200, content=fail(request_id, status_codes.FILE_TOO_LARGE))
                    f.write(chunk)
        finally:
            await file.close()

        if total <= 0:
            logger.warning(f"[FAIL] Empty file after upload. request_id={request_id}")
            return JSONResponse(status_code=200, content=fail(request_id, status_codes.MISSING_AUDIO))

        logger.info(f"[UPLOAD_DONE] File uploaded successfully. request_id={request_id}, size={total}bytes")
        logger.info(f"[PROCESSING] Starting audio QC processing. request_id={request_id}")

        result = await service.run(src_path=Path(src_path), file_size_bytes=total)

        if result.ok:
            logger.info(f"[SUCCESS] Audio QC completed. request_id={request_id}, status_code={result.status_code}")
            logger.debug(f"[SUCCESS] Result data: {result.data}")
            return JSONResponse(status_code=200, content=ok(request_id, result.data))

        logger.warning(f"[FAIL] Audio QC processing failed. request_id={request_id}, status_code={result.status_code}")
        return JSONResponse(status_code=200, content=fail(request_id, result.status_code))



