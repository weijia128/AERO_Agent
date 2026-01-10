"""
全局配置模块
"""
import os
from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """系统全局配置"""
    
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
    SESSION_STORE_BACKEND: str = Field(default="memory", description="会话存储后端")

    # 语义理解配置
    ENABLE_SEMANTIC_UNDERSTANDING: bool = Field(default=True, description="启用语义理解层")
    
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
    
    # 日志配置
    LOG_LEVEL: str = Field(default="INFO", description="日志级别")
    LOG_FILE: Optional[Path] = Field(default=None, description="日志文件路径")

    # LangSmith 追踪配置
    LANGCHAIN_TRACING_V2: bool = Field(default=False, description="是否启用 LangSmith 追踪")
    LANGCHAIN_API_KEY: Optional[str] = Field(default=None, description="LangSmith API Key")
    LANGCHAIN_PROJECT: Optional[str] = Field(default=None, description="LangSmith 项目名称")
    LANGCHAIN_ENDPOINT: str = Field(default="https://api.smith.langchain.com", description="LangSmith API 端点")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 忽略 LangSmith 等额外的环境变量


# 全局配置实例
settings = Settings()


# 场景配置路径
SCENARIOS_PATH = settings.PROJECT_ROOT / "scenarios"

# 约束配置路径
CONSTRAINTS_PATH = settings.PROJECT_ROOT / "constraints"

# 规则配置路径
RULES_PATH = settings.PROJECT_ROOT / "rules"
