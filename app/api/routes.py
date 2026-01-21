from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, Request
from starlette.responses import JSONResponse

from core import status_codes
from core.ids import new_request_id
from core.response import ok, fail
from core.logging import set_request_id

from infra.tempfiles import TempDir, safe_filename

router = APIRouter(prefix="/v1/audio", tags=["audio_qc"])


@router.post("/qc")
async def audio_qc(request: Request, file: Optional[UploadFile] = File(default=None)):
    request_id = new_request_id()
    set_request_id(request_id)

    if file is None or not file.filename:
        return JSONResponse(status_code=200, content=fail(request_id, status_codes.MISSING_AUDIO))

    cfg = request.app.state.cfg
    service = request.app.state.service

    aqc_cfg = cfg.audio_qc
    max_bytes = aqc_cfg.max_file_size_mb * 1024 * 1024

    total = 0
    with TempDir(prefix="aqc_req_") as td:
        upload_name = safe_filename(file.filename)
        src_path = td.path / upload_name

        try:
            with open(src_path, "wb") as f:
                while True:
                    chunk = await file.read(1024 * 1024)  # 1MB
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        return JSONResponse(status_code=200, content=fail(request_id, status_codes.FILE_TOO_LARGE))
                    f.write(chunk)
        finally:
            await file.close()

        if total <= 0:
            return JSONResponse(status_code=200, content=fail(request_id, status_codes.MISSING_AUDIO))

        result = await service.run(src_path=Path(src_path), file_size_bytes=total)

        if result.ok:
            return JSONResponse(status_code=200, content=ok(request_id, result.data))
        return JSONResponse(status_code=200, content=fail(request_id, result.status_code))


