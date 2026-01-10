from datetime import datetime, timedelta

from agent.storage.session_store import MemorySessionStore


def test_memory_session_store_ttl_expired():
    store = MemorySessionStore()
    store.set("s1", {"value": 1}, ttl_seconds=10)
    record = store._records["s1"]
    record.updated_at = datetime.now() - timedelta(seconds=20)

    assert store.get("s1") is None
    assert "s1" not in store._records
