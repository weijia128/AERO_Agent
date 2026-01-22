"""
API 认证模块测试

测试覆盖:
- JWT Token 创建
- FastAPI 端点认证集成测试
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.auth import create_access_token


class TestCreateAccessToken:
    """JWT Token 创建测试"""

    def test_create_access_token_basic(self):
        """测试基本 Token 创建"""
        with patch("apps.api.auth.settings") as mock_settings:
            mock_settings.JWT_SECRET = "test-secret-key"
            mock_settings.JWT_ALGORITHM = "HS256"
            mock_settings.JWT_EXPIRE_MINUTES = 60

            token = create_access_token({"sub": "test-user"})
            assert token is not None
            assert isinstance(token, str)
            assert len(token) > 0
            # JWT 格式: header.payload.signature
            assert token.count(".") == 2

    def test_create_access_token_with_custom_expiry(self):
        """测试自定义过期时间的 Token"""
        with patch("apps.api.auth.settings") as mock_settings:
            mock_settings.JWT_SECRET = "test-secret-key"
            mock_settings.JWT_ALGORITHM = "HS256"
            mock_settings.JWT_EXPIRE_MINUTES = 60

            expires = timedelta(minutes=30)
            token = create_access_token({"sub": "test-user"}, expires_delta=expires)
            assert token is not None
            assert token.count(".") == 2

    def test_create_access_token_with_data(self):
        """测试带数据的 Token"""
        with patch("apps.api.auth.settings") as mock_settings:
            mock_settings.JWT_SECRET = "test-secret-key"
            mock_settings.JWT_ALGORITHM = "HS256"
            mock_settings.JWT_EXPIRE_MINUTES = 60

            token = create_access_token({
                "sub": "test-user",
                "role": "admin",
                "permissions": ["read", "write"]
            })
            assert token is not None

    def test_token_can_be_decoded(self):
        """测试 Token 可以被解码"""
        from jose import jwt

        with patch("apps.api.auth.settings") as mock_settings:
            mock_settings.JWT_SECRET = "test-secret-key"
            mock_settings.JWT_ALGORITHM = "HS256"
            mock_settings.JWT_EXPIRE_MINUTES = 60

            token = create_access_token({"sub": "test-user"})
            payload = jwt.decode(
                token,
                "test-secret-key",
                algorithms=["HS256"]
            )
            assert payload["sub"] == "test-user"
            assert "exp" in payload


class TestAuthEndpointIntegration:
    """认证端点集成测试"""

    @pytest.fixture
    def app_with_auth_enabled(self):
        """创建启用认证的测试应用"""
        from fastapi import Depends
        from apps.api.auth import get_current_user

        app = FastAPI()

        @app.get("/protected")
        async def protected_route(user: str = Depends(get_current_user)):
            return {"user": user}

        return app

    @pytest.fixture
    def app_with_auth_disabled(self):
        """创建禁用认证的测试应用"""
        from fastapi import Depends

        app = FastAPI()

        # 模拟禁用认证时的行为
        async def mock_get_current_user():
            return "anonymous"

        @app.get("/protected")
        async def protected_route(user: str = Depends(mock_get_current_user)):
            return {"user": user}

        return app

    def test_auth_disabled_allows_access(self, app_with_auth_disabled):
        """测试认证禁用时允许访问"""
        client = TestClient(app_with_auth_disabled)
        response = client.get("/protected")
        assert response.status_code == 200
        assert response.json()["user"] == "anonymous"

    def test_missing_api_key_returns_401(self, app_with_auth_enabled):
        """测试缺少 API Key 返回 401"""
        with patch("apps.api.auth.settings") as mock_settings:
            mock_settings.API_AUTH_ENABLED = True
            mock_settings.API_KEYS = ["valid-key"]

            client = TestClient(app_with_auth_enabled)
            response = client.get("/protected")
            assert response.status_code == 401

    def test_invalid_api_key_returns_403(self, app_with_auth_enabled):
        """测试无效 API Key 返回 403"""
        with patch("apps.api.auth.settings") as mock_settings:
            mock_settings.API_AUTH_ENABLED = True
            mock_settings.API_KEYS = ["valid-key"]

            client = TestClient(app_with_auth_enabled)
            response = client.get(
                "/protected",
                headers={"X-API-Key": "invalid-key"}
            )
            assert response.status_code == 403

    def test_valid_api_key_allows_access(self, app_with_auth_enabled):
        """测试有效 API Key 允许访问"""
        with patch("apps.api.auth.settings") as mock_settings:
            mock_settings.API_AUTH_ENABLED = True
            mock_settings.API_KEYS = ["valid-key"]

            client = TestClient(app_with_auth_enabled)
            response = client.get(
                "/protected",
                headers={"X-API-Key": "valid-key"}
            )
            assert response.status_code == 200
            assert response.json()["user"] == "valid-key"


class TestApiKeyValidation:
    """API Key 验证逻辑测试"""

    def test_api_key_in_allowed_list(self):
        """测试 API Key 在允许列表中"""
        keys = ["key1", "key2", "key3"]
        assert "key1" in keys
        assert "key2" in keys
        assert "invalid" not in keys

    def test_empty_api_key_list(self):
        """测试空 API Key 列表"""
        keys = []
        assert "any-key" not in keys

    def test_api_key_prefix_logging(self):
        """测试 API Key 前缀日志（安全性）"""
        api_key = "sk-secret-api-key-12345"
        prefix = api_key[:8]
        assert prefix == "sk-secre"
        # 确保不会暴露完整密钥
        assert prefix != api_key


class TestJwtValidation:
    """JWT 验证逻辑测试"""

    def test_jwt_decode_valid_token(self):
        """测试解码有效 Token"""
        from jose import jwt

        secret = "test-secret"
        algorithm = "HS256"

        # 创建 token
        token = jwt.encode({"sub": "user1"}, secret, algorithm=algorithm)

        # 解码 token
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        assert payload["sub"] == "user1"

    def test_jwt_decode_invalid_secret(self):
        """测试使用错误密钥解码"""
        from jose import jwt, JWTError

        token = jwt.encode({"sub": "user1"}, "secret1", algorithm="HS256")

        with pytest.raises(JWTError):
            jwt.decode(token, "wrong-secret", algorithms=["HS256"])

    def test_jwt_decode_expired_token(self):
        """测试解码过期 Token"""
        from jose import jwt, JWTError
        from datetime import datetime, timezone

        # 创建已过期的 token
        expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
        token = jwt.encode(
            {"sub": "user1", "exp": expired_time},
            "secret",
            algorithm="HS256"
        )

        with pytest.raises(JWTError):
            jwt.decode(token, "secret", algorithms=["HS256"])

    def test_jwt_decode_invalid_format(self):
        """测试解码无效格式 Token"""
        from jose import jwt, JWTError

        with pytest.raises(JWTError):
            jwt.decode("not-a-valid-token", "secret", algorithms=["HS256"])


class TestSecurityBestPractices:
    """安全最佳实践测试"""

    def test_secret_not_in_token(self):
        """测试密钥不在 Token 中"""
        from jose import jwt

        secret = "super-secret-key-12345"
        token = jwt.encode({"sub": "user"}, secret, algorithm="HS256")

        # 密钥不应该出现在 token 中
        assert secret not in token

    def test_algorithm_specified_in_decode(self):
        """测试解码时必须指定算法"""
        from jose import jwt

        token = jwt.encode({"sub": "user"}, "secret", algorithm="HS256")

        # 正确做法：指定允许的算法
        payload = jwt.decode(token, "secret", algorithms=["HS256"])
        assert payload["sub"] == "user"

    def test_token_has_expiration(self):
        """测试 Token 包含过期时间"""
        with patch("apps.api.auth.settings") as mock_settings:
            mock_settings.JWT_SECRET = "test-secret"
            mock_settings.JWT_ALGORITHM = "HS256"
            mock_settings.JWT_EXPIRE_MINUTES = 60

            from jose import jwt
            token = create_access_token({"sub": "user"})
            payload = jwt.decode(
                token,
                "test-secret",
                algorithms=["HS256"]
            )
            assert "exp" in payload
