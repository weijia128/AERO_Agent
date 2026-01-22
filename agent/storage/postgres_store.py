"""
PostgreSQL-backed session store.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, cast

from sqlalchemy import DateTime, String, delete, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from agent.storage.session_store import SessionStore

class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    return cast(Dict[str, Any], json.loads(json.dumps(state, default=str, ensure_ascii=False)))


class SessionModel(Base):
    """Session storage model."""

    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    state: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class PostgresSessionStore(SessionStore):
    """PostgreSQL session store implementation."""

    def __init__(self, database_url: str) -> None:
        self._engine = create_async_engine(database_url, pool_pre_ping=True)
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._initialized = False

    async def init(self) -> None:
        if self._initialized:
            return
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self._initialized = True

    async def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(SessionModel).where(SessionModel.session_id == session_id)
            )
            row = result.scalar_one_or_none()
            if not row:
                return None
            if row.expires_at and row.expires_at <= _utcnow():
                await session.delete(row)
                await session.commit()
                return None
            return cast(Dict[str, Any], row.state)

    async def set(self, session_id: str, state: Dict[str, Any], ttl_seconds: int) -> None:
        now = _utcnow()
        expires_at = now + timedelta(seconds=ttl_seconds) if ttl_seconds else None
        payload = _serialize_state(state)

        async with self._session_factory() as session:
            existing = await session.get(SessionModel, session_id)
            if existing:
                existing.state = payload
                existing.updated_at = now
                existing.expires_at = expires_at
            else:
                session.add(
                    SessionModel(
                        session_id=session_id,
                        state=payload,
                        created_at=now,
                        updated_at=now,
                        expires_at=expires_at,
                    )
                )
            await session.commit()

    async def delete(self, session_id: str) -> None:
        async with self._session_factory() as session:
            existing = await session.get(SessionModel, session_id)
            if existing:
                await session.delete(existing)
                await session.commit()

    async def cleanup_expired(self) -> int:
        now = _utcnow()
        async with self._session_factory() as session:
            result = await session.execute(
                delete(SessionModel).where(SessionModel.expires_at <= now)
            )
            await session.commit()
            return result.rowcount or 0
