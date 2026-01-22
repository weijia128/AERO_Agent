"""
FSM 验证器

核心职责：
1. 验证状态转换的前置条件
2. 检查强制动作是否完成
3. 生成验证报告和待办动作列表

设计原则：
- 验证而非驱动
- 发现问题时提供清晰的错误信息
- 告诉 Agent 需要补救什么
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from agent.state import risk_level_rank

from .states import (
    FSMStateEnum,
    StateDefinition,
    MandatoryAction,
    Precondition,
    FSMValidationResult,
    DEFAULT_MANDATORY_ACTIONS,
)
from .engine import FSMEngine

logger = logging.getLogger(__name__)


class FSMValidator:
    """
    FSM 验证器

    融合设计：
    - 验证 Agent 是否完成必要步骤
    - 检查状态转换是否合规
    - 检查强制动作是否执行
    - 生成错误列表供 Agent 补救
    """

    def __init__(self, engine: FSMEngine):
        """
        初始化验证器

        Args:
            engine: FSM 引擎实例
        """
        self.engine = engine

    def validate(self, agent_state: Dict[str, Any]) -> FSMValidationResult:
        """
        执行完整验证

        Args:
            agent_state: Agent 当前状态

        Returns:
            验证结果
        """
        # 同步状态
        result = self.engine.sync_with_agent_state(agent_state)

        # 检查前置条件
        precondition_errors = self.check_preconditions(
            result.inferred_state, agent_state
        )
        for error in precondition_errors:
            result.add_error(error)

        # 检查强制动作
        mandatory_errors, pending_actions = self.check_mandatory_actions(agent_state)
        for error in mandatory_errors:
            result.add_error(error)
        for action in pending_actions:
            result.add_pending_action(action["action"], action["params"])

        return result

    def check_preconditions(
        self,
        target_state: str,
        agent_state: Dict[str, Any]
    ) -> List[str]:
        """
        检查状态的前置条件

        Args:
            target_state: 目标状态
            agent_state: Agent 状态

        Returns:
            错误信息列表
        """
        errors: List[str] = []
        state_def = self.engine.get_state_definition(target_state)

        if not state_def or not state_def.preconditions:
            return errors

        checklist = agent_state.get("checklist", {})
        mandatory = agent_state.get("mandatory_actions_done", {})

        for precondition in state_def.preconditions:
            # 解析前置条件字符串，格式如 "checklist.fluid_type" 或 "mandatory.risk_assessed"
            if "." in precondition:
                category, field = precondition.split(".", 1)

                if category == "checklist":
                    if field == "p1_complete":
                        p1_fields = self._get_p1_fields(agent_state)
                        for f in p1_fields:
                            if not checklist.get(f, False):
                                errors.append(f"进入{target_state}需要先收集{f}")
                    elif not checklist.get(field, False):
                        errors.append(f"进入{target_state}需要先收集{field}")

                elif category == "mandatory":
                    if not mandatory.get(field, False):
                        errors.append(f"进入{target_state}需要先完成{field}")

        return errors

    def check_mandatory_actions(
        self,
        agent_state: Dict[str, Any]
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        检查强制动作是否完成

        Args:
            agent_state: Agent 状态

        Returns:
            (错误列表, 待执行动作列表)
        """
        errors = []
        pending_actions = []

        for action in self.engine.mandatory_actions:
            # 检查是否触发此强制动作
            if action.is_triggered(agent_state):
                # 检查是否已完成
                if not action.is_completed(agent_state):
                    errors.append(action.error_message or f"需要执行强制动作: {action.name}")
                    pending_actions.append({
                        "action": action.action,
                        "params": action.params,
                        "name": action.name,
                    })

        return errors, pending_actions

    def check_can_close(self, agent_state: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        检查是否可以关闭事件

        Args:
            agent_state: Agent 状态

        Returns:
            (是否可以关闭, 阻塞原因列表)
        """
        blockers = []

        # 检查 P1 Checklist
        checklist = agent_state.get("checklist", {})
        p1_fields = self._get_p1_fields(agent_state)
        for field in p1_fields:
            if not checklist.get(field, False):
                blockers.append(f"未完成P1信息收集: {field}")

        # 检查风险评估
        mandatory = agent_state.get("mandatory_actions_done", {})
        if not mandatory.get("risk_assessed", False):
            blockers.append("未完成风险评估")

        # 检查强制动作
        mandatory_errors, _ = self.check_mandatory_actions(agent_state)
        blockers.extend(mandatory_errors)

        return len(blockers) == 0, blockers

    def get_next_required_actions(
        self,
        agent_state: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        获取下一步需要执行的动作

        根据当前状态和验证结果，推荐下一步动作

        Args:
            agent_state: Agent 状态

        Returns:
            推荐动作列表
        """
        actions: List[Dict[str, Any]] = []
        checklist = agent_state.get("checklist", {})
        mandatory = agent_state.get("mandatory_actions_done", {})
        risk = agent_state.get("risk_assessment", {})

        current_state = self.engine.current_state

        # INIT 状态：需要收集信息
        if current_state == FSMStateEnum.INIT.value:
            # 检查缺少的 P1 字段
            p1_fields, p1_labels = self._get_p1_fields_with_labels(agent_state)
            for field in p1_fields:
                name = p1_labels.get(field, field)
                if not checklist.get(field, False):
                    actions.append({
                        "action": "ask_for_detail",
                        "params": {"field": field},
                        "reason": f"需要收集{name}信息",
                        "priority": "high" if field in ["fluid_type", "position"] else "medium"
                    })

        # P1_RISK_ASSESS 状态：执行风险评估
        elif current_state == FSMStateEnum.P1_RISK_ASSESS.value:
            if not mandatory.get("risk_assessed", False):
                actions.append({
                    "action": "assess_risk",
                    "params": {},
                    "reason": "需要执行风险评估",
                    "priority": "high"
                })

        # P2_IMMEDIATE_CONTROL 状态：高危情况通知消防
        elif current_state == FSMStateEnum.P2_IMMEDIATE_CONTROL.value:
            if risk_level_rank(risk.get("level")) >= 3 and not mandatory.get("fire_dept_notified", False):
                actions.append({
                    "action": "notify_department",
                    "params": {"department": "消防", "priority": "immediate"},
                    "reason": "高危情况必须立即通知消防",
                    "priority": "critical"
                })

        # P4_AREA_ISOLATION 状态：计算影响区域
        elif current_state == FSMStateEnum.P4_AREA_ISOLATION.value:
            spatial = agent_state.get("spatial_analysis", {})
            if not spatial.get("isolated_nodes"):
                actions.append({
                    "action": "calculate_impact_zone",
                    "params": {},
                    "reason": "需要计算影响区域",
                    "priority": "high"
                })

            # 如果影响跑道，需要通知塔台
            if spatial.get("affected_runways") and not mandatory.get("atc_notified", False):
                actions.append({
                    "action": "notify_department",
                    "params": {"department": "塔台", "priority": "high"},
                    "reason": "影响跑道运行需要通知塔台",
                    "priority": "high"
                })

        # P8_CLOSE 状态：生成报告
        elif current_state == FSMStateEnum.P8_CLOSE.value:
            if not agent_state.get("final_report"):
                actions.append({
                    "action": "generate_report",
                    "params": {},
                    "reason": "需要生成事件报告",
                    "priority": "medium"
                })

        # 检查强制动作
        _, pending = self.check_mandatory_actions(agent_state)
        for p in pending:
            # 避免重复添加
            if not any(a["action"] == p["action"] and a["params"] == p["params"] for a in actions):
                actions.append({
                    "action": p["action"],
                    "params": p["params"],
                    "reason": f"强制动作: {p['name']}",
                    "priority": "critical"
                })

        # 按优先级排序
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        actions.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 4))

        return actions

    def _get_p1_fields(self, agent_state: Dict[str, Any]) -> List[str]:
        """从场景配置获取 P1 字段列表"""
        scenario_type = agent_state.get("scenario_type", "oil_spill")
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

    def _get_p1_fields_with_labels(self, agent_state: Dict[str, Any]) -> Tuple[List[str], Dict[str, str]]:
        """获取 P1 字段列表及其显示名称"""
        scenario_type = agent_state.get("scenario_type", "oil_spill")
        try:
            from constraints.loader import get_loader
            loader = get_loader()
            constraints = loader.load(scenario_type)
            p1_fields = [f.key for f in constraints.p1_fields]
            labels = {f.key: f.label for f in constraints.p1_fields}
            return p1_fields, labels
        except Exception as exc:
            logger.warning(
                "Failed to load P1 field labels for scenario %s: %s",
                scenario_type,
                exc,
                exc_info=True,
            )
            return ["fluid_type", "continuous", "engine_status", "position"], {}

    def generate_validation_report(
        self,
        agent_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成完整的验证报告

        Args:
            agent_state: Agent 状态

        Returns:
            验证报告
        """
        result = self.validate(agent_state)
        progress = self.engine.get_progress()
        can_close, blockers = self.check_can_close(agent_state)
        next_actions = self.get_next_required_actions(agent_state)

        return {
            "timestamp": datetime.now().isoformat(),
            "validation": {
                "is_valid": result.is_valid,
                "errors": result.errors,
                "warnings": result.warnings,
            },
            "state": {
                "current": result.current_state,
                "inferred": result.inferred_state,
                "progress": progress,
            },
            "closure": {
                "can_close": can_close,
                "blockers": blockers,
            },
            "recommendations": {
                "next_actions": next_actions,
                "pending_mandatory": result.pending_actions,
            },
            "history": self.engine.get_history(),
        }


def create_validator(
    scenario_type: str = "oil_spill",
    config_path: Optional[str] = None
) -> FSMValidator:
    """
    创建验证器实例

    Args:
        scenario_type: 场景类型
        config_path: 配置文件路径

    Returns:
        FSMValidator 实例
    """
    engine = FSMEngine(scenario_type=scenario_type, config_path=config_path)
    return FSMValidator(engine)
