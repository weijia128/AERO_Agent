"""
会话存储接口与内存实现
"""
from __future__ import annotations

from abc import ABC, abstractmethod
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


class SessionStore(ABC):
    """会话存储抽象类"""

    async def init(self) -> None:
        """初始化存储后端（可选）"""
        return None

    @abstractmethod
    async def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def set(self, session_id: str, state: Dict[str, Any], ttl_seconds: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, session_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def cleanup_expired(self) -> int:
        raise NotImplementedError


class MemorySessionStore(SessionStore):
    """基于内存的会话存储"""

    def __init__(self) -> None:
        self._records: Dict[str, SessionRecord] = {}

    async def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        record = self._records.get(session_id)
        if not record:
            return None
        if record.is_expired():
            await self.delete(session_id)
            return None
        return record.state

    async def set(self, session_id: str, state: Dict[str, Any], ttl_seconds: int) -> None:
        self._records[session_id] = SessionRecord(
            state=state,
            updated_at=datetime.now(),
            ttl_seconds=ttl_seconds,
        )

    async def delete(self, session_id: str) -> None:
        self._records.pop(session_id, None)

    async def cleanup_expired(self) -> int:
        now = datetime.now()
        expired = [sid for sid, record in self._records.items() if record.is_expired(now)]
        for sid in expired:
            self._records.pop(sid, None)
        return len(expired)


_store_instance: Optional[SessionStore] = None
_store_backend: Optional[str] = None


def get_session_store(backend: Optional[str] = "memory") -> SessionStore:
    """获取会话存储实例"""
    global _store_instance, _store_backend

    resolved = (backend or "memory").lower()
    if resolved in {"postgresql", "pg"}:
        resolved = "postgres"

    if _store_instance is None or _store_backend != resolved:
        if resolved == "memory":
            _store_instance = MemorySessionStore()
        elif resolved == "postgres":
            from agent.storage.postgres_store import PostgresSessionStore
            from config.settings import settings

            _store_instance = PostgresSessionStore(settings.postgres_url)
        elif resolved == "redis":
            from agent.storage.redis_store import RedisSessionStore
            from config.settings import settings

            _store_instance = RedisSessionStore(settings.REDIS_URL)
        else:
            raise ValueError(f"Unsupported session store backend: {backend}")
        _store_backend = resolved

    return _store_instance
