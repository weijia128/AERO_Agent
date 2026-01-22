"""
LLM guard with retry and circuit breaker.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Optional

from config.llm_config import get_llm_client
from agent.circuit_breaker import CircuitBreaker
from agent.exceptions import CircuitBreakerOpenError, LLMError
from agent.retry import retry


logger = logging.getLogger(__name__)


class LLMGuard:
    """LLM invocation helper with retry and circuit breaker."""

    def __init__(
        self,
        max_attempts: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        self.max_attempts = max_attempts
        self.delay = delay
        self.backoff = backoff
        self.breaker = breaker or CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60.0,
            name="llm",
        )
        self._retry = retry(
            max_attempts=self.max_attempts,
            delay=self.delay,
            backoff=self.backoff,
            exceptions=(LLMError,),
        )

    def invoke(self, prompt: Any, *, llm: Optional[Any] = None, **kwargs: Any) -> Any:
        client = llm or get_llm_client()

        def _call() -> Any:
            return self._call_llm(client, prompt, **kwargs)

        return self._retry(_call)()

    def _call_llm(self, client: Any, prompt: Any, **kwargs: Any) -> Any:
        try:
            return self.breaker.call(client.invoke, prompt, **kwargs)
        except CircuitBreakerOpenError as exc:
            raise LLMError(str(exc), retryable=False, cause=exc) from exc
        except Exception as exc:
            raise LLMError(str(exc), retryable=True, cause=exc) from exc


@lru_cache()
def get_llm_guard() -> LLMGuard:
    return LLMGuard()


def invoke_llm(prompt: Any, *, llm: Optional[Any] = None, **kwargs: Any) -> Any:
    return get_llm_guard().invoke(prompt, llm=llm, **kwargs)
