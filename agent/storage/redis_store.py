"""
Redis-backed session store.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional, cast

from redis.asyncio import Redis  # type: ignore[import-untyped]

from agent.storage.session_store import SessionStore


def _serialize_state(state: Dict[str, Any]) -> str:
    return json.dumps(state, default=str, ensure_ascii=False)


class RedisSessionStore(SessionStore):
    """Redis session store implementation."""

    def __init__(self, redis_url: str, key_prefix: str = "session:") -> None:
        self._client = Redis.from_url(redis_url, decode_responses=True)
        self._prefix = key_prefix

    async def init(self) -> None:
        await self._client.ping()

    def _key(self, session_id: str) -> str:
        return f"{self._prefix}{session_id}"

    async def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        raw = await self._client.get(self._key(session_id))
        if not raw:
            return None
        return cast(Dict[str, Any], json.loads(raw))

    async def set(self, session_id: str, state: Dict[str, Any], ttl_seconds: int) -> None:
        payload = _serialize_state(state)
        await self._client.setex(self._key(session_id), ttl_seconds, payload)

    async def delete(self, session_id: str) -> None:
        await self._client.delete(self._key(session_id))

    async def cleanup_expired(self) -> int:
        return 0
