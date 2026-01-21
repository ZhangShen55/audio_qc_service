# app/core/logging.py
from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from pathlib import Path

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_ctx.get()
        return True


def set_request_id(request_id: str) -> None:
    _request_id_ctx.set(request_id)


def init_logging(level: str = "INFO", log_dir: str | Path = "logs") -> None:
    """
    初始化日志：
    - 输出到 stdout（控制台）
    - 输出到文件（log_dir/app.log）
    - 格式包含 request_id
    """
    root = logging.getLogger()
    root.setLevel(level.upper())

    # 避免重复 handler
    root.handlers.clear()

    fmt = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
    formatter = logging.Formatter(fmt=fmt)
    request_filter = RequestIdFilter()

    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(request_filter)
    root.addHandler(console_handler)

    # 文件输出
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)
    log_file = log_dir_path / "app.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(request_filter)
    root.addHandler(file_handler)

