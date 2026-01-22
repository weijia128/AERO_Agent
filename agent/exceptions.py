"""
Agent exception hierarchy.
"""
from typing import Optional


class AeroAgentError(Exception):
    """Base exception for agent errors."""

    retryable: bool = False

    def __init__(
        self,
        message: str,
        retryable: Optional[bool] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(message)
        if retryable is not None:
            self.retryable = retryable
        self.cause = cause


class ToolExecutionError(AeroAgentError):
    """Tool execution error."""

    def __init__(
        self,
        tool_name: str,
        message: str,
        retryable: bool = False,
        cause: Optional[BaseException] = None,
    ) -> None:
        self.tool_name = tool_name
        super().__init__(f"Tool {tool_name} failed: {message}", retryable=retryable, cause=cause)


class LLMError(AeroAgentError):
    """LLM invocation error."""

    def __init__(
        self,
        message: str,
        retryable: bool = True,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(f"LLM call failed: {message}", retryable=retryable, cause=cause)


class ValidationError(AeroAgentError):
    """Validation error."""


class FSMTransitionError(AeroAgentError):
    """FSM transition error."""


class CircuitBreakerOpenError(AeroAgentError):
    """Circuit breaker is open."""

    def __init__(self, breaker_name: str) -> None:
        self.breaker_name = breaker_name
        super().__init__(f"Circuit breaker {breaker_name} is open", retryable=False)
