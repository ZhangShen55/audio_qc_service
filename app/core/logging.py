# app/core/logging.py
from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_ctx.get()
        return True


def set_request_id(request_id: str) -> None:
    _request_id_ctx.set(request_id)


def init_logging(level: str = "INFO") -> None:
    """
    初始化日志：
    - 输出到 stdout
    - 格式包含 request_id
    """
    root = logging.getLogger()
    root.setLevel(level.upper())

    # 避免重复 handler
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    fmt = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
    handler.setFormatter(logging.Formatter(fmt=fmt))
    handler.addFilter(RequestIdFilter())

    root.addHandler(handler)

