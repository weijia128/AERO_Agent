"""
LLM 配置与客户端工厂
"""
from typing import Optional, Any, Dict, cast
from functools import lru_cache

from config.settings import settings


class LLMConfig:
    """LLM 配置类"""
    
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        self.provider = provider or settings.LLM_PROVIDER
        self.model = model or settings.LLM_MODEL
        self.api_key = api_key or settings.LLM_API_KEY
        self.base_url = base_url or settings.LLM_BASE_URL
        self.temperature = temperature or settings.LLM_TEMPERATURE
        self.max_tokens = max_tokens or settings.LLM_MAX_TOKENS
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }


class LLMClientFactory:
    """LLM 客户端工厂"""
    
    @staticmethod
    def create_client(config: Optional[LLMConfig] = None) -> Any:
        """创建 LLM 客户端"""
        config = config or LLMConfig()
        
        if config.provider == "zhipu":
            return LLMClientFactory._create_zhipu_client(config)
        elif config.provider == "openai":
            return LLMClientFactory._create_openai_client(config)
        else:
            raise ValueError(f"Unsupported LLM provider: {config.provider}")
    
    @staticmethod
    def _create_zhipu_client(config: LLMConfig):
        """创建智谱 GLM 客户端"""
        try:
            from langchain_community.chat_models import ChatZhipuAI
            return ChatZhipuAI(
                model=config.model,
                api_key=config.api_key,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
            )
        except ImportError:
            # 使用 OpenAI 兼容接口
            from langchain_openai import ChatOpenAI
            chat_openai = cast(Any, ChatOpenAI)
            return chat_openai(
                model=config.model,
                api_key=config.api_key,
                base_url=config.base_url or "https://open.bigmodel.cn/api/anthropic",
                temperature=config.temperature,
                max_tokens=config.max_tokens,
            )
    
    @staticmethod
    def _create_openai_client(config: LLMConfig):
        """创建 OpenAI 客户端"""
        from langchain_openai import ChatOpenAI
        chat_openai = cast(Any, ChatOpenAI)
        return chat_openai(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )


@lru_cache()
def get_llm_client():
    """获取默认 LLM 客户端（单例）"""
    return LLMClientFactory.create_client()
