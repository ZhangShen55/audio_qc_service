# app/core/ids.py
from __future__ import annotations

import uuid
import random
import string
from pathlib import Path


def new_request_id() -> str:
    """
    生成 request_id：默认 UUID4（无状态、低冲突、简单可靠）
    需要雪花ID的话后续可以替换实现，但接口保持不变。
    """
    return uuid.uuid4().hex


def generate_request_id(filename: str) -> str:
    """
    根据文件名生成 request_id: 文件名_8位随机字符
    """
    # 提取文件名（不含扩展名）
    name = Path(filename).stem
    # 生成8位随机字符（小写字母+数字）
    random_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{name}_{random_chars}"

