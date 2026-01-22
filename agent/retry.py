"""
Retry helper with exponential backoff.
"""
from __future__ import annotations

import asyncio
import functools
import logging
import time
from typing import Any, Callable, Optional, Tuple, Type


logger = logging.getLogger(__name__)


RetryCallback = Callable[[int, BaseException, float], None]
RetryPredicate = Callable[[BaseException], bool]


def _should_retry(
    exc: BaseException,
    retry_if: Optional[RetryPredicate],
) -> bool:
    retryable = getattr(exc, "retryable", True)
    if retryable is False:
        return False
    if retry_if is not None and not retry_if(exc):
        return False
    return True


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    on_retry: Optional[RetryCallback] = None,
    retry_if: Optional[RetryPredicate] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Retry decorator with exponential backoff."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exc: Optional[BaseException] = None
                for attempt in range(1, max_attempts + 1):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as exc:
                        if not _should_retry(exc, retry_if):
                            raise
                        last_exc = exc
                        if attempt >= max_attempts:
                            break
                        wait_time = delay * (backoff ** (attempt - 1))
                        logger.warning(
                            "Retrying %s (attempt %s/%s), wait %.2fs, error: %s",
                            func.__name__,
                            attempt,
                            max_attempts,
                            wait_time,
                            exc,
                        )
                        if on_retry:
                            on_retry(attempt, exc, wait_time)
                        await asyncio.sleep(wait_time)
                if last_exc is not None:
                    raise last_exc
                raise RuntimeError("Retry exhausted without exception")

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Optional[BaseException] = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if not _should_retry(exc, retry_if):
                        raise
                    last_exc = exc
                    if attempt >= max_attempts:
                        break
                    wait_time = delay * (backoff ** (attempt - 1))
                    logger.warning(
                        "Retrying %s (attempt %s/%s), wait %.2fs, error: %s",
                        func.__name__,
                        attempt,
                        max_attempts,
                        wait_time,
                        exc,
                    )
                    if on_retry:
                        on_retry(attempt, exc, wait_time)
                    time.sleep(wait_time)
            if last_exc is not None:
                raise last_exc
            raise RuntimeError("Retry exhausted without exception")

        return sync_wrapper

    return decorator
