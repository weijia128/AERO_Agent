"""
FSM 验证模块

提供有限状态机验证功能，用于验证 Agent 的行为是否符合规范流程。

核心设计：
- FSM 不驱动流程，而是验证
- 根据 Agent 完成的工作推断 FSM 状态
- 检查前置条件和强制动作
- 提供清晰的错误信息供 Agent 补救

使用示例:
    from fsm import FSMEngine, FSMValidator, create_validator

    # 方式1: 直接创建验证器
    validator = create_validator(scenario_type="oil_spill")
    result = validator.validate(agent_state)

    # 方式2: 分别使用引擎和验证器
    engine = FSMEngine(scenario_type="oil_spill")
    validator = FSMValidator(engine)
    result = validator.validate(agent_state)

    # 检查验证结果
    if not result.is_valid:
        print("验证错误:", result.errors)
        print("待执行动作:", result.pending_actions)
"""

from .states import (
    # 枚举
    FSMStateEnum,
    # 数据类
    StateDefinition,
    TransitionRule,
    Precondition,
    MandatoryAction,
    FSMTransitionRecord,
    FSMValidationResult,
    # 默认配置
    DEFAULT_STATE_DEFINITIONS,
    DEFAULT_TRANSITIONS,
    DEFAULT_MANDATORY_ACTIONS,
)

from .engine import FSMEngine

from .validator import (
    FSMValidator,
    create_validator,
)

__all__ = [
    # 核心类
    "FSMEngine",
    "FSMValidator",
    # 工厂函数
    "create_validator",
    # 枚举
    "FSMStateEnum",
    # 数据类
    "StateDefinition",
    "TransitionRule",
    "Precondition",
    "MandatoryAction",
    "FSMTransitionRecord",
    "FSMValidationResult",
    # 默认配置
    "DEFAULT_STATE_DEFINITIONS",
    "DEFAULT_TRANSITIONS",
    "DEFAULT_MANDATORY_ACTIONS",
]
