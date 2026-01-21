# app/core/response.py
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict

from core import status_codes


@dataclass(frozen=True)
class ApiResponse:
    request_id: str
    status_code: int
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def ok(request_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    成功：status_code=200 且 data 有值
    """
    return ApiResponse(
        request_id=request_id,
        status_code=status_codes.OK,
        data=data,
    ).to_dict()


def fail(request_id: str, code: int) -> Dict[str, Any]:
    """
    失败：status_code!=200 且 data 固定为 {}
    """
    return ApiResponse(
        request_id=request_id,
        status_code=code,
        data={},
    ).to_dict()

