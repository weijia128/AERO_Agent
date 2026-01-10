"""
工具基类定义
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class ToolInput(BaseModel):
    """工具输入基类"""
    pass


class ToolOutput(BaseModel):
    """工具输出基类"""
    observation: str = Field(..., description="观察结果")
    success: bool = Field(default=True, description="是否成功")
    error: Optional[str] = Field(default=None, description="错误信息")


class BaseTool(ABC):
    """工具基类"""
    
    name: str = ""
    description: str = ""
    
    @abstractmethod
    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具
        
        Args:
            state: 当前 Agent 状态
            inputs: 工具输入参数
            
        Returns:
            包含 observation 和可能的状态更新的字典
        """
        pass
    
    def get_description(self) -> str:
        """获取工具描述"""
        return f"**{self.name}**: {self.description}"
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """验证输入参数"""
        return True


class ToolError(Exception):
    """工具执行错误"""
    pass
