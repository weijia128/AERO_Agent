from datetime import datetime, timedelta

import pytest

from agent.storage.session_store import MemorySessionStore


@pytest.mark.asyncio
async def test_memory_session_store_ttl_expired():
    store = MemorySessionStore()
    await store.set("s1", {"value": 1}, ttl_seconds=10)
    record = store._records["s1"]
    record.updated_at = datetime.now() - timedelta(seconds=20)

    assert await store.get("s1") is None
    assert "s1" not in store._records
