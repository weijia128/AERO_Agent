"""
FSM 状态定义

定义 FSM 的状态、转换和相关数据结构。
支持从 YAML 配置文件加载状态定义。
"""
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


class FSMStateEnum(str, Enum):
    """FSM 状态枚举（漏油场景）"""
    INIT = "INIT"                              # 初始状态
    P1_RISK_ASSESS = "P1_RISK_ASSESS"          # 风险评估
    P2_IMMEDIATE_CONTROL = "P2_IMMEDIATE_CONTROL"  # 立即控制
    P3_RESOURCE_DISPATCH = "P3_RESOURCE_DISPATCH"  # 资源调度
    P4_AREA_ISOLATION = "P4_AREA_ISOLATION"    # 区域隔离
    P5_CLEANUP = "P5_CLEANUP"                  # 清污执行
    P6_VERIFICATION = "P6_VERIFICATION"        # 结果确认
    P7_RECOVERY = "P7_RECOVERY"                # 区域恢复
    P8_CLOSE = "P8_CLOSE"                      # 关闭与报告
    COMPLETED = "COMPLETED"                    # 完成


@dataclass
class StateDefinition:
    """状态定义"""
    id: str
    name: str
    description: str = ""
    preconditions: List[str] = field(default_factory=list)
    triggers: List[Dict[str, Any]] = field(default_factory=list)
    is_terminal: bool = False

    def __post_init__(self):
        if self.preconditions is None:
            self.preconditions = []
        if self.triggers is None:
            self.triggers = []


@dataclass
class TransitionRule:
    """状态转换规则"""
    from_state: str
    to_states: List[str]
    condition: Optional[Callable[[Dict], bool]] = None
    priority: int = 0  # 优先级，数字越大优先级越高

    def can_transition(self, context: Dict[str, Any]) -> bool:
        """检查是否可以进行此转换"""
        if self.condition is None:
            return True
        return self.condition(context)


@dataclass
class Precondition:
    """前置条件"""
    name: str
    check_type: str  # "checklist", "mandatory", "risk_level", "custom"
    field: str
    value: Any = True
    error_message: str = ""

    def check(self, state: Dict[str, Any]) -> bool:
        """检查前置条件是否满足"""
        if self.check_type == "checklist":
            checklist = state.get("checklist", {})
            return checklist.get(self.field, False) == self.value

        elif self.check_type == "mandatory":
            mandatory = state.get("mandatory_actions_done", {})
            return mandatory.get(self.field, False) == self.value

        elif self.check_type == "risk_level":
            risk = state.get("risk_assessment", {})
            risk_level = risk.get("level")
            if isinstance(self.value, list):
                return risk_level in self.value
            return risk_level == self.value

        elif self.check_type == "checklist_complete":
            checklist = state.get("checklist", {})
            if self.field == "p1":
                p1_fields = ["fluid_type", "continuous", "engine_status", "position"]
                return all(checklist.get(f, False) for f in p1_fields)
            elif self.field == "all":
                return all(checklist.values())
            return False

        return True


@dataclass
class MandatoryAction:
    """强制动作定义"""
    name: str
    condition: Dict[str, Any]  # 触发条件
    action: str  # 要执行的动作
    params: Dict[str, Any] = field(default_factory=dict)
    check_field: str = ""  # 检查字段
    error_message: str = ""

    def is_triggered(self, state: Dict[str, Any]) -> bool:
        """检查是否触发此强制动作"""
        def match_expected(actual: Any, expected_value: Any) -> bool:
            if expected_value == "not_empty":
                return bool(actual)
            if expected_value == "empty":
                return not actual
            if isinstance(expected_value, (list, tuple, set)):
                return actual in expected_value
            return actual == expected_value

        def resolve_value(condition_key: str) -> Any:
            if condition_key == "risk_level":
                return state.get("risk_assessment", {}).get("level")
            if condition_key == "affected_runways":
                return state.get("spatial_analysis", {}).get("affected_runways", [])

            if "." in condition_key:
                prefix, field = condition_key.split(".", 1)
                if prefix == "incident":
                    return state.get("incident", {}).get(field)
                if prefix == "risk":
                    return state.get("risk_assessment", {}).get(field)
                if prefix == "mandatory":
                    return state.get("mandatory_actions_done", {}).get(field)
                if prefix == "checklist":
                    return state.get("checklist", {}).get(field)
                if prefix == "spatial":
                    return state.get("spatial_analysis", {}).get(field)

            return state.get(condition_key)

        for key, expected in self.condition.items():
            actual = resolve_value(key)
            if not match_expected(actual, expected):
                return False
        return True

    def is_completed(self, state: Dict[str, Any]) -> bool:
        """检查强制动作是否已完成"""
        mandatory = state.get("mandatory_actions_done", {})
        return mandatory.get(self.check_field, False)


@dataclass
class FSMTransitionRecord:
    """FSM 状态转换记录"""
    from_state: str
    to_state: str
    trigger: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FSMValidationResult:
    """FSM 验证结果"""
    is_valid: bool
    current_state: str
    inferred_state: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    pending_actions: List[Dict[str, Any]] = field(default_factory=list)

    def add_error(self, error: str):
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str):
        self.warnings.append(warning)

    def add_pending_action(self, action: str, params: Dict[str, Any] = None):
        self.pending_actions.append({
            "action": action,
            "params": params or {}
        })


# 默认状态定义（漏油场景）
DEFAULT_STATE_DEFINITIONS = {
    FSMStateEnum.INIT.value: StateDefinition(
        id=FSMStateEnum.INIT.value,
        name="初始状态",
        description="事件刚被报告，尚未收集足够信息"
    ),
    FSMStateEnum.P1_RISK_ASSESS.value: StateDefinition(
        id=FSMStateEnum.P1_RISK_ASSESS.value,
        name="风险评估",
        description="收集关键信息并评估风险等级",
        preconditions=["checklist.fluid_type", "checklist.position"]
    ),
    FSMStateEnum.P2_IMMEDIATE_CONTROL.value: StateDefinition(
        id=FSMStateEnum.P2_IMMEDIATE_CONTROL.value,
        name="立即控制",
        description="高风险情况下的立即控制措施",
        preconditions=["mandatory.risk_assessed"],
        triggers=[{
            "condition": {"risk_level": "HIGH"},
            "action": "notify_department",
            "params": {"department": "消防", "priority": "immediate"}
        }]
    ),
    FSMStateEnum.P3_RESOURCE_DISPATCH.value: StateDefinition(
        id=FSMStateEnum.P3_RESOURCE_DISPATCH.value,
        name="资源调度",
        description="调度必要的应急资源"
    ),
    FSMStateEnum.P4_AREA_ISOLATION.value: StateDefinition(
        id=FSMStateEnum.P4_AREA_ISOLATION.value,
        name="区域隔离",
        description="隔离受影响区域",
        preconditions=["mandatory.risk_assessed"]
    ),
    FSMStateEnum.P5_CLEANUP.value: StateDefinition(
        id=FSMStateEnum.P5_CLEANUP.value,
        name="清污执行",
        description="执行清污作业"
    ),
    FSMStateEnum.P6_VERIFICATION.value: StateDefinition(
        id=FSMStateEnum.P6_VERIFICATION.value,
        name="结果确认",
        description="确认清污结果"
    ),
    FSMStateEnum.P7_RECOVERY.value: StateDefinition(
        id=FSMStateEnum.P7_RECOVERY.value,
        name="区域恢复",
        description="恢复区域正常运行"
    ),
    FSMStateEnum.P8_CLOSE.value: StateDefinition(
        id=FSMStateEnum.P8_CLOSE.value,
        name="关闭与报告",
        description="关闭事件并生成报告",
        preconditions=["checklist.p1_complete", "mandatory.risk_assessed"]
    ),
    FSMStateEnum.COMPLETED.value: StateDefinition(
        id=FSMStateEnum.COMPLETED.value,
        name="完成",
        description="事件处理完成",
        is_terminal=True
    ),
}

# 默认转换规则
DEFAULT_TRANSITIONS = {
    FSMStateEnum.INIT.value: [FSMStateEnum.P1_RISK_ASSESS.value],
    FSMStateEnum.P1_RISK_ASSESS.value: [
        FSMStateEnum.P2_IMMEDIATE_CONTROL.value,
        FSMStateEnum.P4_AREA_ISOLATION.value
    ],
    FSMStateEnum.P2_IMMEDIATE_CONTROL.value: [FSMStateEnum.P3_RESOURCE_DISPATCH.value],
    FSMStateEnum.P3_RESOURCE_DISPATCH.value: [FSMStateEnum.P4_AREA_ISOLATION.value],
    FSMStateEnum.P4_AREA_ISOLATION.value: [FSMStateEnum.P5_CLEANUP.value],
    FSMStateEnum.P5_CLEANUP.value: [FSMStateEnum.P6_VERIFICATION.value],
    FSMStateEnum.P6_VERIFICATION.value: [
        FSMStateEnum.P7_RECOVERY.value,
        FSMStateEnum.P5_CLEANUP.value  # 可能需要重新清污
    ],
    FSMStateEnum.P7_RECOVERY.value: [FSMStateEnum.P8_CLOSE.value],
    FSMStateEnum.P8_CLOSE.value: [FSMStateEnum.COMPLETED.value],
}

# 默认强制动作
DEFAULT_MANDATORY_ACTIONS = [
    MandatoryAction(
        name="high_risk_fire_notification",
        condition={"risk_level": "HIGH"},
        action="notify_department",
        params={"department": "消防", "priority": "immediate"},
        check_field="fire_dept_notified",
        error_message="高危情况必须通知消防"
    ),
    MandatoryAction(
        name="runway_impact_atc_notification",
        condition={"affected_runways": "not_empty"},
        action="notify_department",
        params={"department": "塔台", "priority": "high"},
        check_field="atc_notified",
        error_message="影响跑道运行必须通知塔台"
    ),
]
