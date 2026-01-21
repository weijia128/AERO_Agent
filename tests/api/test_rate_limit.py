"""
速率限制模块测试

测试覆盖:
- 速率限制检查
- 限额状态查询
- 过期记录清理
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
from fastapi import HTTPException

from apps.api.rate_limit import (
    rate_limit_check,
    get_rate_limit_status,
    cleanup_expired_records,
    _request_counts,
)


@pytest.fixture(autouse=True)
def clear_rate_limit_state():
    """每个测试前清理速率限制状态"""
    _request_counts.clear()
    yield
    _request_counts.clear()


class TestRateLimitCheck:
    """速率限制检查测试"""

    @pytest.mark.asyncio
    async def test_rate_limit_disabled(self):
        """测试速率限制禁用时直接通过"""
        with patch("apps.api.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = False

            request = MagicMock()
            result = await rate_limit_check(request)
            assert result is None

    @pytest.mark.asyncio
    async def test_first_request_passes(self):
        """测试首次请求通过"""
        with patch("apps.api.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_REQUESTS = 100

            request = MagicMock()
            request.headers.get = lambda key: None
            request.client.host = "127.0.0.1"

            result = await rate_limit_check(request)
            assert result is None

    @pytest.mark.asyncio
    async def test_requests_within_limit(self):
        """测试限制范围内的请求通过"""
        with patch("apps.api.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_REQUESTS = 5

            request = MagicMock()
            request.headers.get = lambda key: None
            request.client.host = "127.0.0.1"

            # 发送4次请求（限制为5次）
            for _ in range(4):
                result = await rate_limit_check(request)
                assert result is None

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self):
        """测试超过限制抛出异常"""
        with patch("apps.api.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_REQUESTS = 3

            request = MagicMock()
            request.headers.get = lambda key: None
            request.client.host = "127.0.0.1"

            # 发送3次请求达到限制
            for _ in range(3):
                await rate_limit_check(request)

            # 第4次请求应该被拒绝
            with pytest.raises(HTTPException) as exc_info:
                await rate_limit_check(request)
            assert exc_info.value.status_code == 429
            assert "Retry-After" in exc_info.value.headers

    @pytest.mark.asyncio
    async def test_rate_limit_by_api_key(self):
        """测试按 API Key 限制"""
        with patch("apps.api.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_REQUESTS = 2

            # 请求1: API Key A
            request_a = MagicMock()
            request_a.headers.get = lambda key: "api-key-a" if key == "X-API-Key" else None
            request_a.client.host = "127.0.0.1"

            # 请求2: API Key B
            request_b = MagicMock()
            request_b.headers.get = lambda key: "api-key-b" if key == "X-API-Key" else None
            request_b.client.host = "127.0.0.1"

            # A 发送2次请求
            await rate_limit_check(request_a)
            await rate_limit_check(request_a)

            # A 的第3次请求应该被拒绝
            with pytest.raises(HTTPException):
                await rate_limit_check(request_a)

            # B 的请求应该通过（独立计数）
            result = await rate_limit_check(request_b)
            assert result is None

    @pytest.mark.asyncio
    async def test_rate_limit_by_ip(self):
        """测试按 IP 限制（无 API Key 时）"""
        with patch("apps.api.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_REQUESTS = 2

            # 请求来自 IP1
            request_ip1 = MagicMock()
            request_ip1.headers.get = lambda key: None
            request_ip1.client.host = "192.168.1.1"

            # 请求来自 IP2
            request_ip2 = MagicMock()
            request_ip2.headers.get = lambda key: None
            request_ip2.client.host = "192.168.1.2"

            # IP1 发送2次请求
            await rate_limit_check(request_ip1)
            await rate_limit_check(request_ip1)

            # IP1 的第3次请求应该被拒绝
            with pytest.raises(HTTPException):
                await rate_limit_check(request_ip1)

            # IP2 的请求应该通过（独立计数）
            result = await rate_limit_check(request_ip2)
            assert result is None


class TestGetRateLimitStatus:
    """速率限制状态查询测试"""

    @pytest.mark.asyncio
    async def test_status_when_disabled(self):
        """测试禁用时的状态"""
        with patch("apps.api.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = False

            request = MagicMock()
            status = await get_rate_limit_status(request)
            assert status["enabled"] is False

    @pytest.mark.asyncio
    async def test_status_full_remaining(self):
        """测试完整剩余量"""
        with patch("apps.api.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_REQUESTS = 100

            request = MagicMock()
            request.headers.get = lambda key: None
            request.client.host = "127.0.0.1"

            status = await get_rate_limit_status(request)
            assert status["enabled"] is True
            assert status["limit"] == 100
            assert status["remaining"] == 100
            assert status["reset_seconds"] == 60

    @pytest.mark.asyncio
    async def test_status_after_requests(self):
        """测试发送请求后的状态"""
        with patch("apps.api.rate_limit.settings") as mock_settings:
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_REQUESTS = 10

            request = MagicMock()
            request.headers.get = lambda key: None
            request.client.host = "127.0.0.1"

            # 发送3次请求
            for _ in range(3):
                await rate_limit_check(request)

            status = await get_rate_limit_status(request)
            assert status["remaining"] == 7


class TestCleanupExpiredRecords:
    """过期记录清理测试"""

    def test_cleanup_empty(self):
        """测试清理空记录"""
        cleaned = cleanup_expired_records()
        assert cleaned == 0

    def test_cleanup_expired_clients(self):
        """测试清理过期客户端记录"""
        # 手动添加过期记录
        old_time = datetime.now() - timedelta(minutes=2)
        _request_counts["ip:old-client"] = [old_time]
        _request_counts["ip:current-client"] = [datetime.now()]

        cleaned = cleanup_expired_records()
        assert cleaned == 1
        assert "ip:old-client" not in _request_counts
        assert "ip:current-client" in _request_counts

    def test_cleanup_partial_records(self):
        """测试部分记录过期的清理"""
        now = datetime.now()
        old_time = now - timedelta(minutes=2)

        # 添加混合记录
        _request_counts["ip:mixed-client"] = [old_time, old_time, now]

        cleanup_expired_records()

        # 客户端应该还在，但只有新记录
        assert "ip:mixed-client" in _request_counts
        assert len(_request_counts["ip:mixed-client"]) == 1
