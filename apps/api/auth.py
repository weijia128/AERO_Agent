"""
API 认证模块

支持 API Key 和 JWT Token 两种认证方式。
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPBearer
from jose import JWTError, jwt

from config.settings import settings

logger = logging.getLogger(__name__)

# 安全方案定义
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """
    验证 API Key

    Args:
        api_key: 请求头中的 API Key

    Returns:
        验证通过的 API Key

    Raises:
        HTTPException: 认证失败
    """
    # 未启用认证时直接通过
    if not settings.API_AUTH_ENABLED:
        return "anonymous"

    if not api_key:
        logger.warning("API 认证失败: 缺少 API Key")
        raise HTTPException(status_code=401, detail="缺少 API Key")

    if api_key not in settings.API_KEYS:
        logger.warning(f"API 认证失败: 无效的 API Key (前缀: {api_key[:8]}...)")
        raise HTTPException(status_code=403, detail="无效的 API Key")

    logger.debug(f"API 认证成功: {api_key[:8]}...")
    return api_key


async def verify_jwt_token(
    credentials=Security(bearer_scheme),
) -> dict:
    """
    验证 JWT Token

    Args:
        credentials: Bearer token credentials

    Returns:
        解码后的 token payload

    Raises:
        HTTPException: 认证失败
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="缺少认证令牌")

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT 验证失败: {str(e)}")
        raise HTTPException(status_code=401, detail=f"令牌无效: {str(e)}")


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    创建 JWT Token

    Args:
        data: 要编码到 token 中的数据
        expires_delta: 过期时间增量

    Returns:
        编码后的 JWT token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


async def get_current_user(api_key: str = Security(verify_api_key)) -> str:
    """
    获取当前用户（基于 API Key）

    用于需要认证的端点的依赖注入。
    """
    return api_key
