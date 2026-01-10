"""
约束系统

提供完整的约束检查和验证功能：
- ConstraintLoader: 从 YAML 配置加载约束
- ConstraintChecker: 检查 Agent 状态是否满足约束
- ChecklistValidator: 验证单个字段的值
"""

from constraints.loader import (
    ConstraintLoader,
    ScenarioConstraints,
    ChecklistField,
    MandatoryAction,
    StateConstraint,
    get_loader,
    load_constraints,
)

from constraints.checker import (
    ConstraintChecker,
    ConstraintCheckResult,
    ConstraintViolation,
    ConstraintSeverity,
    ChecklistValidator,
    get_checker,
    check_constraints,
    validate_checklist_field,
)

__all__ = [
    # Loader
    "ConstraintLoader",
    "ScenarioConstraints",
    "ChecklistField",
    "MandatoryAction",
    "StateConstraint",
    "get_loader",
    "load_constraints",
    # Checker
    "ConstraintChecker",
    "ConstraintCheckResult",
    "ConstraintViolation",
    "ConstraintSeverity",
    "ChecklistValidator",
    "get_checker",
    "check_constraints",
    "validate_checklist_field",
]
