"""
FSM 引擎

核心职责：
1. 管理 FSM 状态转换
2. 根据 Agent 状态推断当前 FSM 状态
3. 记录状态转换历史
4. 提供状态查询接口

设计原则：
- FSM 不驱动流程，而是验证和追踪
- Agent 通过完成工作来推动 FSM 状态变化
- 支持从 YAML 配置加载
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import yaml
from pathlib import Path

from agent.state import risk_level_rank

from .states import (
    FSMStateEnum,
    StateDefinition,
    TransitionRule,
    MandatoryAction,
    FSMTransitionRecord,
    FSMValidationResult,
    DEFAULT_STATE_DEFINITIONS,
    DEFAULT_TRANSITIONS,
    DEFAULT_MANDATORY_ACTIONS,
)

logger = logging.getLogger(__name__)


class FSMEngine:
    """
    FSM 引擎

    融合设计核心：
    - 不主动驱动流程
    - 根据 Agent 完成的工作推断状态
    - 验证状态转换合规性
    - 记录完整的状态历史
    """

    def __init__(
        self,
        scenario_type: str = "oil_spill",
        config_path: Optional[str] = None
    ):
        """
        初始化 FSM 引擎

        Args:
            scenario_type: 场景类型
            config_path: 配置文件路径，如果提供则从 YAML 加载
        """
        self.scenario_type = scenario_type
        self.current_state = FSMStateEnum.INIT.value
        self.history: List[FSMTransitionRecord] = []

        # 加载配置
        if config_path:
            self._load_from_yaml(config_path)
        else:
            self._load_defaults()

    def _load_defaults(self):
        """加载默认配置"""
        self.state_definitions = DEFAULT_STATE_DEFINITIONS.copy()
        self.transitions = DEFAULT_TRANSITIONS.copy()
        mandatory_from_config = self._load_mandatory_actions_from_config()
        if mandatory_from_config:
            self.mandatory_actions = mandatory_from_config
        else:
            self.mandatory_actions = DEFAULT_MANDATORY_ACTIONS.copy()

    def _load_from_yaml(self, config_path: str):
        """从 YAML 文件加载配置"""
        path = Path(config_path)
        if not path.exists():
            self._load_defaults()
            return

        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # 解析状态定义
        self.state_definitions = {}
        fsm_states = config.get("fsm_states", [])
        for state_config in fsm_states:
            state_id = state_config.get("id")
            self.state_definitions[state_id] = StateDefinition(
                id=state_id,
                name=state_config.get("name", state_id),
                description=state_config.get("description", ""),
                preconditions=state_config.get("preconditions", []),
                triggers=state_config.get("triggers", []),
            )

        # 如果没有定义完整的状态，使用默认值补充
        for state_id, default_def in DEFAULT_STATE_DEFINITIONS.items():
            if state_id not in self.state_definitions:
                self.state_definitions[state_id] = default_def

        # 使用默认转换规则
        self.transitions = DEFAULT_TRANSITIONS.copy()

        # 解析强制动作
        self.mandatory_actions = []
        mandatory_triggers = config.get("mandatory_triggers", [])
        for trigger in mandatory_triggers:
            self.mandatory_actions.append(MandatoryAction(
                name=trigger.get("name", ""),
                condition=trigger.get("condition", {}),
                action=trigger.get("action", ""),
                params=trigger.get("params", {}),
                check_field=trigger.get("check_field", ""),
                error_message=trigger.get("error_message", ""),
            ))

        # 如果没有定义强制动作，尝试从场景配置读取
        if not self.mandatory_actions:
            mandatory_from_config = self._load_mandatory_actions_from_config()
            if mandatory_from_config:
                self.mandatory_actions = mandatory_from_config
            else:
                self.mandatory_actions = DEFAULT_MANDATORY_ACTIONS.copy()

    def _load_mandatory_actions_from_config(self) -> List[MandatoryAction]:
        """从场景配置读取强制动作"""
        config_path = (
            Path(__file__).resolve().parents[1]
            / "scenarios"
            / self.scenario_type
            / "config.yaml"
        )
        if not config_path.exists():
            return []

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        mandatory_triggers = config.get("mandatory_triggers", [])
        actions: List[MandatoryAction] = []
        for trigger in mandatory_triggers:
            actions.append(MandatoryAction(
                name=trigger.get("name", ""),
                condition=trigger.get("condition", {}),
                action=trigger.get("action", ""),
                params=trigger.get("params", {}),
                check_field=trigger.get("check_field", ""),
                error_message=trigger.get("error_message", ""),
            ))

        return actions

    def infer_state(self, agent_state: Dict[str, Any]) -> str:
        """
        根据 Agent 状态推断当前 FSM 状态

        这是融合方案的核心：
        - 不是 FSM 驱动 Agent
        - 而是根据 Agent 已完成的工作推断 FSM 状态

        Args:
            agent_state: Agent 当前状态

        Returns:
            推断出的 FSM 状态
        """
        mandatory = agent_state.get("mandatory_actions_done", {})
        risk = agent_state.get("risk_assessment", {})
        spatial = agent_state.get("spatial_analysis", {})
        checklist = agent_state.get("checklist", {})
        actions = agent_state.get("actions_taken", [])
        final_report = agent_state.get("final_report", {})

        # 从后往前推断状态（优先匹配更高级的状态）

        # 检查是否完成报告生成
        if final_report:
            return FSMStateEnum.COMPLETED.value

        # 检查 Checklist 和风险评估完成情况
        p1_fields = self._get_p1_fields(agent_state)
        p1_complete = all(checklist.get(f, False) for f in p1_fields)
        risk_assessed = mandatory.get("risk_assessed", False)

        # 完成所有必要步骤，可以关闭
        if p1_complete and risk_assessed:
            # 检查是否有区域隔离
            if spatial.get("isolated_nodes"):
                return FSMStateEnum.P4_AREA_ISOLATION.value
            return FSMStateEnum.P8_CLOSE.value

        # 检查是否完成风险评估
        if risk_assessed:
            risk_level = risk.get("level", "")
            if risk_level_rank(risk_level) >= 3:
                if mandatory.get("fire_dept_notified", False):
                    return FSMStateEnum.P3_RESOURCE_DISPATCH.value
                return FSMStateEnum.P2_IMMEDIATE_CONTROL.value
            # 中低风险直接进入区域隔离
            return FSMStateEnum.P4_AREA_ISOLATION.value

        # 检查是否有足够信息进行风险评估
        if checklist.get("fluid_type") and checklist.get("position"):
            return FSMStateEnum.P1_RISK_ASSESS.value

        return FSMStateEnum.INIT.value

    def _get_p1_fields(self, agent_state: Dict[str, Any]) -> List[str]:
        """从场景配置获取 P1 字段列表"""
        scenario_type = agent_state.get("scenario_type", self.scenario_type)
        try:
            from constraints.loader import get_loader
            return get_loader().get_all_p1_keys(scenario_type)
        except Exception as exc:
            logger.warning(
                "Failed to load P1 fields for scenario %s: %s",
                scenario_type,
                exc,
                exc_info=True,
            )
            return ["fluid_type", "continuous", "engine_status", "position"]

    def can_transition(self, from_state: str, to_state: str) -> bool:
        """
        检查状态转换是否合法

        Args:
            from_state: 源状态
            to_state: 目标状态

        Returns:
            是否允许转换
        """
        if from_state == to_state:
            return True

        allowed = self.transitions.get(from_state, [])
        return to_state in allowed

    def transition(
        self,
        to_state: str,
        trigger: str = "agent_action",
        context: Dict[str, Any] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        执行状态转换

        Args:
            to_state: 目标状态
            trigger: 触发原因
            context: 上下文信息

        Returns:
            (是否成功, 错误信息)
        """
        from_state = self.current_state

        # 检查转换是否合法
        if not self.can_transition(from_state, to_state):
            return False, f"不允许从 {from_state} 转换到 {to_state}"

        # 记录转换
        record = FSMTransitionRecord(
            from_state=from_state,
            to_state=to_state,
            trigger=trigger,
            context=context or {}
        )
        self.history.append(record)

        # 更新当前状态
        self.current_state = to_state

        return True, None

    def sync_with_agent_state(
        self,
        agent_state: Dict[str, Any],
        trigger: str = "sync"
    ) -> FSMValidationResult:
        """
        与 Agent 状态同步

        根据 Agent 状态推断 FSM 状态并同步

        Args:
            agent_state: Agent 状态
            trigger: 触发原因

        Returns:
            同步结果
        """
        inferred_state = self.infer_state(agent_state)
        result = FSMValidationResult(
            is_valid=True,
            current_state=self.current_state,
            inferred_state=inferred_state
        )

        # 如果状态需要变化
        if self.current_state != inferred_state:
            # 检查是否可以转换
            if self.can_transition(self.current_state, inferred_state):
                success, error = self.transition(inferred_state, trigger)
                if not success:
                    result.add_warning(f"状态转换警告: {error}")
            else:
                # 允许跳过中间状态（灵活性）
                # 但记录警告
                result.add_warning(
                    f"跳过状态转换: {self.current_state} -> {inferred_state}"
                )
                # 直接更新状态
                self.history.append(FSMTransitionRecord(
                    from_state=self.current_state,
                    to_state=inferred_state,
                    trigger=f"{trigger}_skip"
                ))
                self.current_state = inferred_state

        return result

    def get_state_definition(self, state_id: str) -> Optional[StateDefinition]:
        """获取状态定义"""
        return self.state_definitions.get(state_id)

    def get_current_definition(self) -> Optional[StateDefinition]:
        """获取当前状态定义"""
        return self.get_state_definition(self.current_state)

    def get_allowed_transitions(self) -> List[str]:
        """获取当前状态允许的转换目标"""
        return self.transitions.get(self.current_state, [])

    def get_history(self) -> List[Dict[str, Any]]:
        """获取状态转换历史"""
        return [
            {
                "from_state": record.from_state,
                "to_state": record.to_state,
                "trigger": record.trigger,
                "timestamp": record.timestamp,
                "context": record.context,
            }
            for record in self.history
        ]

    def is_terminal(self) -> bool:
        """检查是否处于终态"""
        state_def = self.get_current_definition()
        if state_def:
            return state_def.is_terminal
        return self.current_state == FSMStateEnum.COMPLETED.value

    def reset(self):
        """重置 FSM 到初始状态"""
        self.current_state = FSMStateEnum.INIT.value
        self.history = []

    def get_progress(self) -> Dict[str, Any]:
        """
        获取处理进度

        Returns:
            包含进度信息的字典
        """
        # 定义状态顺序
        state_order = [
            FSMStateEnum.INIT.value,
            FSMStateEnum.P1_RISK_ASSESS.value,
            FSMStateEnum.P2_IMMEDIATE_CONTROL.value,
            FSMStateEnum.P3_RESOURCE_DISPATCH.value,
            FSMStateEnum.P4_AREA_ISOLATION.value,
            FSMStateEnum.P5_CLEANUP.value,
            FSMStateEnum.P6_VERIFICATION.value,
            FSMStateEnum.P7_RECOVERY.value,
            FSMStateEnum.P8_CLOSE.value,
            FSMStateEnum.COMPLETED.value,
        ]

        current_index = state_order.index(self.current_state) if self.current_state in state_order else 0
        total = len(state_order) - 1  # 不包括 INIT

        # 计算进度百分比
        progress_percent = (current_index / total) * 100 if total > 0 else 0

        return {
            "current_state": self.current_state,
            "current_state_name": self.state_definitions.get(
                self.current_state, StateDefinition(id=self.current_state, name=self.current_state)
            ).name,
            "progress_percent": round(progress_percent, 1),
            "steps_completed": current_index,
            "total_steps": total,
            "is_terminal": self.is_terminal(),
            "transitions_count": len(self.history),
        }

    def __repr__(self) -> str:
        return f"FSMEngine(scenario={self.scenario_type}, state={self.current_state})"
