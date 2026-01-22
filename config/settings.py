"""
全局配置模块
"""
import os
from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """系统全局配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # 项目路径
    PROJECT_ROOT: Path = Path(__file__).parent.parent
    
    # 环境
    ENV: str = Field(default="development", description="运行环境")
    DEBUG: bool = Field(default=True, description="调试模式")
    
    # LLM 配置
    LLM_PROVIDER: str = Field(default="zhipu", description="LLM 提供商: zhipu, openai")
    LLM_MODEL: str = Field(default="glm-4.7", description="模型名称")
    LLM_API_KEY: Optional[str] = Field(default=None, description="API Key")
    LLM_BASE_URL: Optional[str] = Field(default=None, description="API Base URL")
    LLM_TEMPERATURE: float = Field(default=0.1, description="温度参数")
    LLM_MAX_TOKENS: int = Field(default=4096, description="最大 Token 数")
    
    # Agent 配置
    MAX_ITERATIONS: int = Field(default=15, description="最大迭代次数")
    TIMEOUT_SECONDS: int = Field(default=120, description="超时时间(秒)")
    SESSION_TTL_SECONDS: int = Field(default=3600, description="会话存活时间(秒)")
    SESSION_STORE_BACKEND: str = Field(default="memory", description="会话存储后端(兼容字段)")
    STORAGE_BACKEND: Optional[str] = Field(
        default=None, description="存储后端: memory, postgres, redis"
    )

    # 存储配置
    POSTGRES_HOST: str = Field(default="localhost", description="PostgreSQL 主机")
    POSTGRES_PORT: int = Field(default=5432, description="PostgreSQL 端口")
    POSTGRES_USER: str = Field(default="aero", description="PostgreSQL 用户")
    POSTGRES_PASSWORD: str = Field(default="", description="PostgreSQL 密码")
    POSTGRES_DB: str = Field(default="aero_agent", description="PostgreSQL 数据库")
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis 连接地址")

    # 语义理解配置
    ENABLE_SEMANTIC_UNDERSTANDING: bool = Field(default=True, description="启用语义理解层")

    # 交叉验证配置
    ENABLE_CROSS_VALIDATION: bool = Field(default=True, description="启用规则引擎 + LLM 交叉验证")

    # 知识库配置
    KNOWLEDGE_BASE_PATH: Path = Field(
        default=Path(__file__).parent.parent / "knowledge" / "data",
        description="知识库路径"
    )
    EMBEDDING_MODEL: str = Field(
        default="BAAI/bge-small-zh-v1.5",
        description="Embedding 模型"
    )
    
    # 空间数据配置
    TOPOLOGY_FILE: Path = Field(
        default=Path(__file__).parent.parent / "data" / "spatial" / "airport_topology.json",
        description="机场拓扑文件"
    )
    
    # API 配置
    API_HOST: str = Field(default="0.0.0.0", description="API 主机")
    API_PORT: int = Field(default=8000, description="API 端口")
    CORS_ALLOW_ORIGINS: List[str] = Field(default=["*"], description="CORS 允许来源")

    # API 认证配置
    API_AUTH_ENABLED: bool = Field(default=False, description="是否启用 API 认证")
    API_KEYS: List[str] = Field(default=[], description="允许的 API Keys")
    JWT_SECRET: str = Field(default="change-me-in-production", description="JWT 密钥")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT 算法")
    JWT_EXPIRE_MINUTES: int = Field(default=60, description="JWT 过期时间(分钟)")

    # 速率限制配置
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="是否启用速率限制")
    RATE_LIMIT_REQUESTS: int = Field(default=100, description="每分钟最大请求数")

    # 模板/Jinja 配置
    TEMPLATE_ROOT: Path = Field(
        default=Path(__file__).parent.parent / "agent" / "templates",
        description="报告模板根目录",
    )
    JINJA_AUTO_RELOAD: bool = Field(default=True, description="开发模式下自动重载模板")
    JINJA_CACHE_SIZE: int = Field(default=50, description="Jinja 模板缓存大小")
    
    # 日志配置
    LOG_LEVEL: str = Field(default="INFO", description="日志级别")
    LOG_FORMAT: str = Field(default="text", description="日志格式: text, json")
    LOG_FILE: Optional[Path] = Field(default=None, description="日志文件路径")

    # LangSmith 追踪配置
    LANGCHAIN_TRACING_V2: bool = Field(default=False, description="是否启用 LangSmith 追踪")
    LANGCHAIN_API_KEY: Optional[str] = Field(default=None, description="LangSmith API Key")
    LANGCHAIN_PROJECT: Optional[str] = Field(default=None, description="LangSmith 项目名称")
    LANGCHAIN_ENDPOINT: str = Field(default="https://api.smith.langchain.com", description="LangSmith API 端点")

    @property
    def postgres_url(self) -> str:
        """PostgreSQL 连接地址（异步驱动）"""
        return (
            "postgresql+asyncpg://"
            f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

# 全局配置实例
settings = Settings()


# 场景配置路径
SCENARIOS_PATH = settings.PROJECT_ROOT / "scenarios"

# 约束配置路径
CONSTRAINTS_PATH = settings.PROJECT_ROOT / "constraints"

# 规则配置路径
RULES_PATH = settings.PROJECT_ROOT / "rules"
