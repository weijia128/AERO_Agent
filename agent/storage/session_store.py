"""
会话存储接口与内存实现
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, Any


@dataclass
class SessionRecord:
    """会话记录"""
    state: Dict[str, Any]
    updated_at: datetime
    ttl_seconds: int

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now()
        return now - self.updated_at > timedelta(seconds=self.ttl_seconds)


class SessionStore:
    """会话存储抽象类"""

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def set(self, session_id: str, state: Dict[str, Any], ttl_seconds: int) -> None:
        raise NotImplementedError

    def delete(self, session_id: str) -> None:
        raise NotImplementedError

    def cleanup_expired(self) -> int:
        raise NotImplementedError


class MemorySessionStore(SessionStore):
    """基于内存的会话存储"""

    def __init__(self) -> None:
        self._records: Dict[str, SessionRecord] = {}

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        record = self._records.get(session_id)
        if not record:
            return None
        if record.is_expired():
            self.delete(session_id)
            return None
        return record.state

    def set(self, session_id: str, state: Dict[str, Any], ttl_seconds: int) -> None:
        self._records[session_id] = SessionRecord(
            state=state,
            updated_at=datetime.now(),
            ttl_seconds=ttl_seconds,
        )

    def delete(self, session_id: str) -> None:
        self._records.pop(session_id, None)

    def cleanup_expired(self) -> int:
        now = datetime.now()
        expired = [sid for sid, record in self._records.items() if record.is_expired(now)]
        for sid in expired:
            self._records.pop(sid, None)
        return len(expired)


_store_instance: Optional[SessionStore] = None


def get_session_store(backend: str = "memory") -> SessionStore:
    """获取会话存储实例"""
    global _store_instance
    if _store_instance is None:
        if backend == "memory":
            _store_instance = MemorySessionStore()
        else:
            raise ValueError(f"Unsupported session store backend: {backend}")
    return _store_instance
