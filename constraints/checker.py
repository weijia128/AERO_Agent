"""
约束检查器

检查 Agent 状态是否满足各类约束：
1. Checklist 字段收集完整性
2. 强制动作执行状态
3. FSM 状态转换前置条件
"""
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from agent.state import AgentState, FSMState
from constraints.loader import ConstraintLoader, ScenarioConstraints, get_loader


class ConstraintSeverity(Enum):
    """约束违反严重程度"""
    ERROR = "error"      # 严重错误，不能继续
    WARNING = "warning"  # 警告，建议处理
    INFO = "info"        # 信息提示


@dataclass
class ConstraintViolation:
    """约束违反详情"""
    severity: ConstraintSeverity
    code: str
    message: str
    field: Optional[str] = None
    required_value: Optional[Any] = None
    actual_value: Optional[Any] = None
    suggestion: Optional[str] = None


@dataclass
class ConstraintCheckResult:
    """约束检查结果"""
    passed: bool
    violations: List[ConstraintViolation] = field(default_factory=list)
    warnings: List[ConstraintViolation] = field(default_factory=list)

    @property
    def errors(self) -> List[ConstraintViolation]:
        return [v for v in self.violations if v.severity == ConstraintSeverity.ERROR]

    def add_violation(self, violation: ConstraintViolation):
        if violation.severity == ConstraintSeverity.ERROR:
            self.violations.append(violation)
        else:
            self.warnings.append(violation)
        self.passed = len(self.errors) == 0


class ConstraintChecker:
    """约束检查器"""

    # 错误代码常量
    ERR_MISSING_P1_FIELD = "MISSING_P1_FIELD"
    ERR_MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    ERR_MANDATORY_ACTION_NOT_DONE = "MANDATORY_ACTION_NOT_DONE"
    ERR_STATE_TRANSITION_INVALID = "STATE_TRANSITION_INVALID"
    ERR_P1_INCOMPLETE = "P1_INCOMPLETE"

    WARN_FIELD_MISSING = "FIELD_MISSING"
    WARN_ACTION_RECOMMENDED = "ACTION_RECOMMENDED"

    def __init__(self, loader: Optional[ConstraintLoader] = None):
        """
        初始化约束检查器

        Args:
            loader: 约束加载器实例
        """
        self.loader = loader or get_loader()

    def check_all(
        self,
        state: AgentState,
        strict_mode: bool = False
    ) -> ConstraintCheckResult:
        """
        执行所有约束检查

        Args:
            state: Agent 状态
            strict_mode: 严格模式，P2 字段缺失也视为错误

        Returns:
            ConstraintCheckResult 检查结果
        """
        result = ConstraintCheckResult(passed=True)
        scenario_type = state.get('scenario_type', 'oil_spill')

        try:
            constraints = self.loader.load(scenario_type)
        except Exception as e:
            # 如果加载失败，返回错误
            result.add_violation(ConstraintViolation(
                severity=ConstraintSeverity.ERROR,
                code="CONSTRAINT_LOAD_FAILED",
                message=f"加载约束配置失败: {str(e)}",
                suggestion="检查场景配置文件是否存在"
            ))
            return result

        # 1. 检查 P1 字段完整性
        self._check_p1_fields(state, constraints, result)

        # 2. 检查状态必需的字段
        fsm_state = state.get('fsm_state', FSMState.INIT.value)
        self._check_state_required_fields(state, constraints, fsm_state, result)

        # 3. 检查强制动作
        self._check_mandatory_actions(state, constraints, fsm_state, result)

        # 4. 检查 P2 字段（严格模式下）
        if strict_mode:
            self._check_p2_fields(state, constraints, result)

        return result

    def check_p1_complete(self, state: AgentState) -> Tuple[bool, Optional[str]]:
        """
        快速检查 P1 字段是否收集完整

        Args:
            state: Agent 状态

        Returns:
            (是否完整, 未完成的字段名或 None)
        """
        scenario_type = state.get('scenario_type', 'oil_spill')
        checklist = state.get('checklist', {})

        try:
            constraints = self.loader.load(scenario_type)
            p1_keys = [f.key for f in constraints.p1_fields]

            for key in p1_keys:
                if not checklist.get(key, False):
                    return False, key

            return True, None
        except Exception:
            # 如果加载失败，使用硬编码的默认 P1 字段
            default_p1 = ['fluid_type', 'continuous', 'engine_status', 'position']
            for key in default_p1:
                if not checklist.get(key, False):
                    return False, key
            return True, None

    def _check_p1_fields(
        self,
        state: AgentState,
        constraints: ScenarioConstraints,
        result: ConstraintCheckResult
    ):
        """检查 P1 字段是否全部收集"""
        checklist = state.get('checklist', {})
        p1_keys = [f.key for f in constraints.p1_fields]

        missing_fields = []
        for key in p1_keys:
            if not checklist.get(key, False):
                missing_fields.append(key)

        if missing_fields:
            # 查找字段标签
            field_labels = {f.key: f.label for f in constraints.p1_fields}
            missing_labels = [field_labels.get(f, f) for f in missing_fields]

            result.add_violation(ConstraintViolation(
                severity=ConstraintSeverity.ERROR,
                code=self.ERR_P1_INCOMPLETE,
                message=f"P1 字段未完全收集，缺少: {', '.join(missing_labels)}",
                field=", ".join(missing_fields),
                suggestion="需要收集完整的关键事实才能进行风险评估"
            ))

    def _check_state_required_fields(
        self,
        state: AgentState,
        constraints: ScenarioConstraints,
        fsm_state: str,
        result: ConstraintCheckResult
    ):
        """检查当前状态必需的字段"""
        state_constraint = constraints.state_constraints.get(fsm_state)
        if not state_constraint:
            return

        required_fields = state_constraint.required_checklist_fields
        if not required_fields:
            return

        checklist = state.get('checklist', {})
        incident = state.get('incident', {})

        for field_name in required_fields:
            # 检查是否已收集
            if not checklist.get(field_name, False):
                result.add_violation(ConstraintViolation(
                    severity=ConstraintSeverity.ERROR,
                    code=self.ERR_MISSING_REQUIRED_FIELD,
                    message=f"状态 '{fsm_state}' 缺少必需字段: {field_name}",
                    field=field_name,
                    suggestion=f"请收集 {field_name} 字段信息"
                ))
            # 检查字段值是否有效
            elif field_name in incident and incident[field_name] is None:
                result.add_violation(ConstraintViolation(
                    severity=ConstraintSeverity.WARNING,
                    code=self.WARN_FIELD_MISSING,
                    message=f"字段 '{field_name}' 已标记收集但值为空",
                    field=field_name
                ))

    def _check_mandatory_actions(
        self,
        state: AgentState,
        constraints: ScenarioConstraints,
        fsm_state: str,
        result: ConstraintCheckResult
    ):
        """检查强制动作是否执行"""
        state_constraint = constraints.state_constraints.get(fsm_state)
        if not state_constraint:
            return

        required_actions = state_constraint.required_mandatory_actions
        if not required_actions:
            return

        actions_done = state.get('mandatory_actions_done', {})

        for action in required_actions:
            # 支持两种格式：字符串 "action_name" 或 {"action": "action_name", ...}
            action_key = action if isinstance(action, str) else action.get('action', '')
            if not action_key:
                continue

            if not actions_done.get(action_key, False):
                result.add_violation(ConstraintViolation(
                    severity=ConstraintSeverity.ERROR,
                    code=self.ERR_MANDATORY_ACTION_NOT_DONE,
                    message=f"状态 '{fsm_state}' 必须执行动作: {action_key}",
                    field=action_key,
                    suggestion=f"请执行 {action_key} 动作"
                ))

    def _check_p2_fields(
        self,
        state: AgentState,
        constraints: ScenarioConstraints,
        result: ConstraintCheckResult
    ):
        """检查 P2 字段（严格模式）"""
        checklist = state.get('checklist', {})
        p2_keys = [f.key for f in constraints.p2_fields]

        missing_fields = []
        for key in p2_keys:
            if not checklist.get(key, False):
                missing_fields.append(key)

        if missing_fields:
            field_labels = {f.key: f.label for f in constraints.p2_fields}
            missing_labels = [field_labels.get(f, f) for f in missing_fields]

            result.add_violation(ConstraintViolation(
                severity=ConstraintSeverity.WARNING,
                code=self.WARN_FIELD_MISSING,
                message=f"P2 字段未收集: {', '.join(missing_labels)}",
                field=", ".join(missing_fields),
                suggestion="收集 P2 字段有助于更准确的风险评估"
            ))

    def can_proceed_to_next_phase(
        self,
        state: AgentState,
        target_phase: str
    ) -> Tuple[bool, List[str]]:
        """
        检查是否允许进入下一阶段

        Args:
            state: Agent 状态
            target_phase: 目标阶段 (如 'P1_RISK_ASSESS')

        Returns:
            (是否允许, 拒绝原因列表)
        """
        result = self.check_all(state)
        reasons = [v.message for v in result.errors]

        # 特殊检查：进入 P1_RISK_ASSESS 需要至少部分 P1 字段
        if target_phase == FSMState.P1_RISK_ASSESS.value:
            p1_complete, missing = self.check_p1_complete(state)
            if not p1_complete:
                reasons.append(f"进入风险评估前需要收集关键事实，当前缺少: {missing}")

        return len(reasons) == 0, reasons


class ChecklistValidator:
    """Checklist 字段验证器"""

    def __init__(self, scenario_type: str = "oil_spill"):
        self.scenario_type = scenario_type
        self.loader = get_loader()

    def validate_value(
        self,
        field_name: str,
        value: Any
    ) -> Tuple[bool, Optional[str]]:
        """
        验证字段值是否符合规范

        Args:
            field_name: 字段名
            value: 值

        Returns:
            (是否有效, 错误信息或 None)
        """
        try:
            constraints = self.loader.load(self.scenario_type)
        except Exception:
            return True, None  # 加载失败时跳过验证

        # 查找字段定义
        all_fields = constraints.p1_fields + constraints.p2_fields
        field_def = next((f for f in all_fields if f.key == field_name), None)

        if not field_def:
            return True, None  # 未知字段跳过

        # 验证必填
        if field_def.required and value is None:
            return False, f"字段 {field_name} 是必填项"

        # 验证枚举值
        if field_def.options and value is not None:
            valid_values = [opt['value'] for opt in field_def.options]
            if value not in valid_values:
                return False, f"字段 {field_name} 的值必须是以下之一: {', '.join(valid_values)}"

        # 验证正则
        if field_def.validation and value is not None:
            try:
                import re
                if not re.match(field_def.validation, str(value)):
                    return False, f"字段 {field_name} 的值格式不正确"
            except re.error:
                pass  # 无效正则时跳过

        return True, None


# 全局检查器实例
_default_checker: Optional[ConstraintChecker] = None


def get_checker() -> ConstraintChecker:
    """获取全局约束检查器实例"""
    global _default_checker
    if _default_checker is None:
        _default_checker = ConstraintChecker()
    return _default_checker


def check_constraints(state: AgentState, strict: bool = False) -> ConstraintCheckResult:
    """便捷函数：检查约束"""
    return get_checker().check_all(state, strict_mode=strict)


def validate_checklist_field(
    field_name: str,
    value: Any,
    scenario_type: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """便捷函数：验证 checklist 字段"""
    checker = ChecklistValidator(scenario_type or "oil_spill")
    return checker.validate_value(field_name, value)
