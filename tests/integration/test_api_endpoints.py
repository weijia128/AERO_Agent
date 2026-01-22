import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import apps.api.main as api_main
from agent.storage.session_store import MemorySessionStore
from config.settings import settings


@pytest.fixture
def client(monkeypatch):
    async def override_user():
        return "test-user"

    async def override_rate_limit():
        return None

    api_main.app.dependency_overrides[api_main.get_current_user] = override_user
    api_main.app.dependency_overrides[api_main.rate_limit_check] = override_rate_limit

    store = MemorySessionStore()
    monkeypatch.setattr(api_main, "session_store", store)

    with TestClient(api_main.app) as client:
        yield client, store

    api_main.app.dependency_overrides = {}


def test_start_event_returns_processing(client, monkeypatch):
    test_client, store = client

    result = {
        "is_complete": False,
        "final_answer": "processing",
        "final_report": {},
        "fsm_state": "INIT",
        "checklist": {"position": True},
        "risk_assessment": {"level": "R3"},
        "messages": [{"role": "assistant", "content": "need more details"}],
    }
    monkeypatch.setattr(api_main, "agent", SimpleNamespace(invoke=lambda state: result))

    response = test_client.post(
        "/event/start",
        json={"session_id": "sess-1", "message": "report incident", "scenario_type": "oil_spill"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "sess-1"
    assert payload["status"] == "processing"
    assert payload["risk_level"] == "R3"
    assert payload["next_question"] == "need more details"

    stored = asyncio.run(store.get("sess-1"))
    assert stored["checklist"]["position"] is True


def test_chat_event_updates_session(client, monkeypatch):
    test_client, store = client

    base_state = {
        "session_id": "sess-2",
        "messages": [{"role": "user", "content": "start"}],
        "checklist": {},
        "risk_assessment": {},
        "fsm_state": "INIT",
        "is_complete": False,
        "iteration_count": 0,
    }
    asyncio.run(store.set("sess-2", base_state, settings.SESSION_TTL_SECONDS))

    result = {
        "is_complete": True,
        "final_answer": "done",
        "final_report": {"summary": "ok"},
        "fsm_state": "COMPLETED",
        "checklist": {"position": True},
        "risk_assessment": {"level": "R2"},
        "messages": [{"role": "assistant", "content": "completed"}],
    }
    monkeypatch.setattr(api_main, "agent", SimpleNamespace(invoke=lambda state: result))

    response = test_client.post(
        "/event/chat",
        json={"session_id": "sess-2", "message": "more info"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["risk_level"] == "R2"

    stored = asyncio.run(store.get("sess-2"))
    assert stored["final_answer"] == "done"


def test_get_event_status_missing_session(client):
    test_client, _store = client
    response = test_client.get("/event/missing-session")
    assert response.status_code == 404
