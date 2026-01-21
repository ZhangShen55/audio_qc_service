# app/utils/validate.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FileCheck:
    ok: bool
    code: int
    size_bytes: int


def check_uploaded_file(
    filename: str | None,
    size_bytes: int,
    max_size_mb: int,
    missing_code: int,
    too_large_code: int,
) -> FileCheck:
    """
    统一的上传文件校验：
    - 缺失/空文件：missing_code
    - 超过大小：too_large_code
    """
    if filename is None or filename == "":
        return FileCheck(ok=False, code=missing_code, size_bytes=size_bytes)

    if size_bytes <= 0:
        return FileCheck(ok=False, code=missing_code, size_bytes=size_bytes)

    if size_bytes > max_size_mb * 1024 * 1024:
        return FileCheck(ok=False, code=too_large_code, size_bytes=size_bytes)

    return FileCheck(ok=True, code=0, size_bytes=size_bytes)
