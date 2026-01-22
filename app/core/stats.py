# app/core/stats.py
from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Set, Optional


@dataclass
class ServiceStats:
    """服务运行状态统计"""
    start_time: float = field(default_factory=time.time)
    total_requests: int = 0
    success_count: int = 0
    failed_count: int = 0
    processing_ids: Set[str] = field(default_factory=set)
    queued_ids: Set[str] = field(default_factory=set)
    _lock: Lock = field(default_factory=Lock, repr=False)
    
    # 快照缓存（避免高并发时重复计算）
    _cached_snapshot: Optional[dict] = field(default=None, repr=False)
    _cache_time: float = field(default=0.0, repr=False)
    _cache_ttl: float = field(default=0.5, repr=False)  # 缓存0.5秒

    def add_processing(self, request_id: str) -> None:
        """添加正在处理的任务"""
        with self._lock:
            self.total_requests += 1
            if request_id in self.queued_ids:
                self.queued_ids.remove(request_id)
            self.processing_ids.add(request_id)
            self._invalidate_cache()

    def add_queued(self, request_id: str) -> None:
        """添加排队任务"""
        with self._lock:
            self.queued_ids.add(request_id)
            self._invalidate_cache()

    def finish_success(self, request_id: str) -> None:
        """标记任务成功完成"""
        with self._lock:
            self.success_count += 1
            self.processing_ids.discard(request_id)
            self._invalidate_cache()

    def finish_failed(self, request_id: str) -> None:
        """标记任务失败"""
        with self._lock:
            self.failed_count += 1
            self.processing_ids.discard(request_id)
            self._invalidate_cache()
    
    def _invalidate_cache(self) -> None:
        """清除缓存（必须在锁内调用）"""
        self._cached_snapshot = None
        self._cache_time = 0.0

    def get_snapshot(self) -> dict:
        """获取当前状态快照（带缓存，高性能无阻塞）"""
        now = time.time()
        
        # 检查缓存是否有效
        with self._lock:
            if self._cached_snapshot is not None and (now - self._cache_time) < self._cache_ttl:
                return self._cached_snapshot.copy()
            
            # 缓存失效，复制数据（锁内最小操作）
            start_time = self.start_time
            total_requests = self.total_requests
            success_count = self.success_count
            failed_count = self.failed_count
            processing_ids = list(self.processing_ids)
            queued_ids = list(self.queued_ids)
        
        # 锁外进行耗时操作（排序、格式化等）
        uptime_seconds = int(now - start_time)
        snapshot = {
            "start_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time)),
            "uptime_seconds": uptime_seconds,
            "uptime_formatted": self._format_uptime(uptime_seconds),
            "total_requests": total_requests,
            "success_count": success_count,
            "failed_count": failed_count,
            "processing_count": len(processing_ids),
            "processing_ids": sorted(processing_ids),
            "queued_count": len(queued_ids),
            "queued_ids": sorted(queued_ids),
        }
        
        # 更新缓存
        with self._lock:
            self._cached_snapshot = snapshot
            self._cache_time = now
        
        return snapshot

    @staticmethod
    def _format_uptime(seconds: int) -> str:
        """格式化运行时间"""
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")
        
        return " ".join(parts)
