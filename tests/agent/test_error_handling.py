import pytest

from agent.circuit_breaker import CircuitBreaker, CircuitState
from agent.exceptions import CircuitBreakerOpenError, LLMError
from agent.llm_guard import LLMGuard
from agent.nodes.tool_executor import tool_executor_node
from agent.retry import retry
from agent.state import ActionStatus
from tools.base import BaseTool
from tools.registry import ToolRegistry


def test_retry_retries_on_retryable_error():
    calls = {"count": 0}

    @retry(max_attempts=3, delay=0.0, backoff=1.0, exceptions=(LLMError,))
    def flaky():
        calls["count"] += 1
        if calls["count"] < 2:
            raise LLMError("temporary", retryable=True)
        return "ok"

    assert flaky() == "ok"
    assert calls["count"] == 2


def test_retry_stops_on_non_retryable_error():
    calls = {"count": 0}

    @retry(max_attempts=3, delay=0.0, backoff=1.0, exceptions=(LLMError,))
    def non_retryable():
        calls["count"] += 1
        raise LLMError("nope", retryable=False)

    with pytest.raises(LLMError):
        non_retryable()
    assert calls["count"] == 1


def test_circuit_breaker_opens_and_recovers(monkeypatch):
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=10.0, name="test")
    now = {"value": 1000.0}

    def fake_time():
        return now["value"]

    import agent.circuit_breaker as cb_module
    monkeypatch.setattr(cb_module.time, "time", fake_time)

    def fail():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        breaker.call(fail)
    with pytest.raises(ValueError):
        breaker.call(fail)

    assert breaker.state == CircuitState.OPEN

    with pytest.raises(CircuitBreakerOpenError):
        breaker.call(fail)

    now["value"] += 11.0

    def succeed():
        return "ok"

    assert breaker.call(succeed) == "ok"
    assert breaker.state == CircuitState.CLOSED


def test_llm_guard_retries():
    class FakeLLM:
        def __init__(self):
            self.calls = 0

        def invoke(self, prompt, **kwargs):
            self.calls += 1
            if self.calls < 2:
                raise RuntimeError("temporary")
            return "ok"

    llm = FakeLLM()
    guard = LLMGuard(
        max_attempts=2,
        delay=0.0,
        backoff=1.0,
        breaker=CircuitBreaker(failure_threshold=5, recovery_timeout=60.0, name="llm-test"),
    )
    assert guard.invoke("ping", llm=llm) == "ok"
    assert llm.calls == 2


def test_tool_executor_isolates_errors(monkeypatch):
    class FailingTool(BaseTool):
        name = "failing_tool"
        description = "always fails"
        max_retries = 3

        def __init__(self):
            super().__init__()
            self.calls = 0

        def execute(self, state, inputs):
            self.calls += 1
            raise TimeoutError("boom")

    tool = FailingTool()
    monkeypatch.setattr(ToolRegistry, "_tools", {tool.name: tool})
    monkeypatch.setattr(ToolRegistry, "_scenario_tools", {})

    result = tool_executor_node(
        {
            "session_id": "test-session",
            "current_action": tool.name,
            "current_action_input": {},
            "actions_taken": [],
        }
    )

    assert result["next_node"] == "reasoning"
    assert result["actions_taken"][-1]["status"] == ActionStatus.FAILED.value
    assert tool.calls == tool.max_retries
