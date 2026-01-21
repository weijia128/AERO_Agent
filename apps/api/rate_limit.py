"""
速率限制模块

基于内存的简单速率限制器。生产环境建议使用 Redis。
"""
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List

from fastapi import HTTPException, Request

from config.settings import settings

logger = logging.getLogger(__name__)

# 请求计数存储（内存实现，生产环境应使用 Redis）
_request_counts: Dict[str, List[datetime]] = defaultdict(list)
_lock = asyncio.Lock()


async def rate_limit_check(request: Request) -> None:
    """
    速率限制检查

    Args:
        request: FastAPI 请求对象

    Raises:
        HTTPException: 超过速率限制
    """
    if not settings.RATE_LIMIT_ENABLED:
        return

    # 获取客户端标识（优先使用 API Key，否则使用 IP）
    api_key = request.headers.get("X-API-Key")
    if api_key:
        client_id = f"key:{api_key[:16]}"
    else:
        client_id = f"ip:{request.client.host}" if request.client else "ip:unknown"

    now = datetime.now()
    window_start = now - timedelta(minutes=1)

    async with _lock:
        # 清理过期记录
        _request_counts[client_id] = [
            t for t in _request_counts[client_id] if t > window_start
        ]

        # 检查是否超限
        current_count = len(_request_counts[client_id])
        if current_count >= settings.RATE_LIMIT_REQUESTS:
            logger.warning(
                f"速率限制触发: {client_id}, "
                f"请求数: {current_count}/{settings.RATE_LIMIT_REQUESTS}"
            )
            raise HTTPException(
                status_code=429,
                detail=f"请求过于频繁，每分钟最多 {settings.RATE_LIMIT_REQUESTS} 次",
                headers={"Retry-After": "60"},
            )

        # 记录请求
        _request_counts[client_id].append(now)


async def get_rate_limit_status(request: Request) -> dict:
    """
    获取当前速率限制状态

    Args:
        request: FastAPI 请求对象

    Returns:
        速率限制状态信息
    """
    if not settings.RATE_LIMIT_ENABLED:
        return {"enabled": False}

    api_key = request.headers.get("X-API-Key")
    if api_key:
        client_id = f"key:{api_key[:16]}"
    else:
        client_id = f"ip:{request.client.host}" if request.client else "ip:unknown"

    now = datetime.now()
    window_start = now - timedelta(minutes=1)

    async with _lock:
        # 清理过期记录
        _request_counts[client_id] = [
            t for t in _request_counts[client_id] if t > window_start
        ]
        current_count = len(_request_counts[client_id])

    return {
        "enabled": True,
        "limit": settings.RATE_LIMIT_REQUESTS,
        "remaining": max(0, settings.RATE_LIMIT_REQUESTS - current_count),
        "reset_seconds": 60,
    }


def cleanup_expired_records() -> int:
    """
    清理所有过期的速率限制记录

    Returns:
        清理的客户端数量
    """
    now = datetime.now()
    window_start = now - timedelta(minutes=1)
    cleaned = 0

    for client_id in list(_request_counts.keys()):
        _request_counts[client_id] = [
            t for t in _request_counts[client_id] if t > window_start
        ]
        if not _request_counts[client_id]:
            del _request_counts[client_id]
            cleaned += 1

    return cleaned
