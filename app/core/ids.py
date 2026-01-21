# app/core/ids.py
from __future__ import annotations

import uuid


def new_request_id() -> str:
    """
    生成 request_id：默认 UUID4（无状态、低冲突、简单可靠）
    需要雪花ID的话后续可以替换实现，但接口保持不变。
    """
    return uuid.uuid4().hex

