# app/core/logging.py
from __future__ import annotations

import logging
import sys
import glob
from contextvars import ContextVar
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta

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

    # 文件输出（按日期轮转，保留7天）
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)
    log_file = log_dir_path / "app.log"

    # 使用 TimedRotatingFileHandler，每天午夜轮转
    file_handler = TimedRotatingFileHandler(
        filename=str(log_file),
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    # 设置日志文件名后缀格式：app.log.YYYY-MM-DD
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(formatter)
    file_handler.addFilter(request_filter)
    root.addHandler(file_handler)
    
    # 清理超过7天的旧日志文件
    _cleanup_old_logs(log_dir_path, days=7)


def _cleanup_old_logs(log_dir: Path, days: int = 7) -> None:
    """清理超过指定天数的旧日志文件"""
    try:
        cutoff_time = datetime.now() - timedelta(days=days)
        pattern = str(log_dir / "app.log.*")
        
        for log_file in glob.glob(pattern):
            log_path = Path(log_file)
            if log_path.stat().st_mtime < cutoff_time.timestamp():
                log_path.unlink()
    except Exception:
        pass  # 忽略清理错误，不影响日志功能

