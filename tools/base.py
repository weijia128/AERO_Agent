"""
工具基类定义

提供工具的基础抽象和输入验证功能。
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger(__name__)


class ToolInput(BaseModel):
    """工具输入基类"""
    model_config = ConfigDict(extra="ignore")


class ToolOutput(BaseModel):
    """工具输出基类"""

    observation: str = Field(..., description="观察结果")
    success: bool = Field(default=True, description="是否成功")
    error: Optional[str] = Field(default=None, description="错误信息")


class BaseTool(ABC):
    """
    工具基类

    子类可以通过设置 input_schema 属性来启用输入验证。
    现有工具继续实现 execute() 方法，验证会自动应用。
    """

    name: str = ""
    description: str = ""
    input_schema: Optional[Type[ToolInput]] = None  # 子类可覆盖指定输入模式
    enable_validation: bool = True  # 是否启用输入验证
    max_retries: int = 2  # 最大尝试次数（含首试）

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

    def execute_with_validation(
        self, state: Dict[str, Any], inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        带输入验证的工具执行

        Args:
            state: 当前 Agent 状态
            inputs: 工具输入参数

        Returns:
            包含 observation 和可能的状态更新的字典
        """
        if not self.enable_validation:
            return self.execute(state, inputs)

        # 尝试从注册表获取输入模式
        schema = self.input_schema
        if schema is None:
            from tools.schemas import get_input_schema

            schema = get_input_schema(self.name)

        # 如果有输入模式，进行验证
        if schema is not None:
            try:
                validated = schema(**inputs)
                inputs = validated.model_dump(exclude_unset=True)
            except ValidationError as e:
                error_msg = "; ".join(
                    f"{err['loc'][0]}: {err['msg']}" for err in e.errors()
                )
                logger.warning(f"工具 {self.name} 输入验证失败: {error_msg}")
                return {
                    "observation": f"输入参数无效: {error_msg}",
                    "error": True,
                }

        # 执行实际逻辑
        return self.execute(state, inputs)

    def get_description(self) -> str:
        """获取工具描述"""
        return f"**{self.name}**: {self.description}"

    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """验证输入参数（向后兼容）"""
        return True


class ToolError(Exception):
    """工具执行错误"""

    pass
