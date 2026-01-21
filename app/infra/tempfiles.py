# app/infra/tempfiles.py
from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile


class TempDir:
    """
    用于请求级临时目录，确保异常时也会清理。
    """
    def __init__(self, prefix: str = "aqc_req_"):
        self._dir = Path(tempfile.mkdtemp(prefix=prefix))

    @property
    def path(self) -> Path:
        return self._dir

    def cleanup(self) -> None:
        if self._dir.exists():
            shutil.rmtree(self._dir, ignore_errors=True)

    def __enter__(self) -> "TempDir":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()


def safe_filename(name: str) -> str:
    """
    简单清洗文件名，避免路径穿越与特殊字符。
    """
    base = os.path.basename(name).strip()
    if not base:
        return "upload.bin"
    # 去掉可能导致问题的字符
    bad = ['..', '/', '\\', '\x00']
    for b in bad:
        base = base.replace(b, "_")
    return base
