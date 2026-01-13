"""
FSM 验证节点

融合方案核心：
- FSM 不驱动流程，而是验证
- 检查 Agent 是否完成必要步骤
- 检查状态转换是否合规
- 发现问题时通知 Agent 补救

本模块现已重构，核心逻辑委托给 fsm 模块处理。
保留原有接口以确保向后兼容。
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

from agent.state import AgentState, FSMState, RiskLevel, risk_level_rank
from fsm import FSMEngine, FSMValidator, FSMStateEnum
from fsm.states import FSMTransitionRecord
from scenarios.base import ScenarioRegistry


def _build_validator_from_state(
    state: Optional[AgentState],
    scenario_type: str
) -> FSMValidator:
    """根据当前状态构建 FSM 验证器实例"""
    scenario = ScenarioRegistry.get(scenario_type)
    config_path = None
    if scenario and scenario.fsm_states_path and scenario.fsm_states_path.exists():
        config_path = str(scenario.fsm_states_path)
    engine = FSMEngine(scenario_type=scenario_type, config_path=config_path)
    if state:
        current = state.get("fsm_state")
        if current:
            engine.current_state = current
        history = state.get("fsm_history", [])
        if history:
            engine.history = [
                FSMTransitionRecord(
                    from_state=item.get("from_state", ""),
                    to_state=item.get("to_state", ""),
                    trigger=item.get("trigger", ""),
                    timestamp=item.get("timestamp", datetime.now().isoformat()),
                    context=item.get("context", {}),
                )
                for item in history
            ]
    return FSMValidator(engine)


def get_fsm_validator(
    session_id: str,
    scenario_type: str = "oil_spill",
    state: Optional[AgentState] = None
) -> FSMValidator:
    """
    获取 FSM 验证器实例

    Args:
        session_id: 会话 ID
        scenario_type: 场景类型
        state: 当前 Agent 状态

    Returns:
        FSMValidator 实例
    """
    _ = session_id  # 保留接口兼容
    return _build_validator_from_state(state, scenario_type)


def clear_fsm_validator(session_id: str):
    """清除 FSM 验证器实例（保留接口）"""
    _ = session_id


# ============================================================
# 向后兼容的导出（保留原有接口）
# ============================================================

# FSM 状态转换规则（委托给 fsm 模块）
FSM_TRANSITIONS = {
    FSMState.INIT: [FSMState.P1_RISK_ASSESS],
    FSMState.P1_RISK_ASSESS: [FSMState.P2_IMMEDIATE_CONTROL, FSMState.P4_AREA_ISOLATION],
    FSMState.P2_IMMEDIATE_CONTROL: [FSMState.P3_RESOURCE_DISPATCH],
    FSMState.P3_RESOURCE_DISPATCH: [FSMState.P4_AREA_ISOLATION],
    FSMState.P4_AREA_ISOLATION: [FSMState.P5_CLEANUP],
    FSMState.P5_CLEANUP: [FSMState.P6_VERIFICATION],
    FSMState.P6_VERIFICATION: [FSMState.P7_RECOVERY, FSMState.P5_CLEANUP],
    FSMState.P7_RECOVERY: [FSMState.P8_CLOSE],
    FSMState.P8_CLOSE: [FSMState.COMPLETED],
}

# 每个 FSM 状态的前置条件
FSM_PRECONDITIONS = {
    FSMState.P1_RISK_ASSESS: {
        "checklist": ["fluid_type", "position"],
    },
    FSMState.P2_IMMEDIATE_CONTROL: {
        "requires": ["risk_assessed"],
    },
    FSMState.P3_RESOURCE_DISPATCH: {
        "risk_level": [RiskLevel.R2, RiskLevel.R3, RiskLevel.R4],
    },
    FSMState.P4_AREA_ISOLATION: {
        "requires": ["risk_assessed"],
    },
    FSMState.P8_CLOSE: {
        "requires": ["risk_assessed"],
        "checklist_complete": True,
    },
}

# 强制动作规则
MANDATORY_ACTIONS = {
    # 高风险：必须通知消防
    "high_risk_fire_notification": {
        "condition": lambda s: risk_level_rank(s.get("risk_assessment", {}).get("level")) >= 3,
        "action": "notify_department",
        "params": {"department": "消防"},
        "check_field": "fire_dept_notified",
        "error_message": "高危情况必须通知消防",
    },
    # R2 及以上：通知机务
    "medium_risk_maintenance": {
        "condition": lambda s: risk_level_rank(s.get("risk_assessment", {}).get("level")) >= 2,
        "action": "notify_department",
        "params": {"department": "机务"},
        "check_field": "maintenance_notified",
        "error_message": "中等及以上风险必须通知机务",
    },
    # 低风险：通知清洗部门
    "low_risk_cleaning": {
        "condition": lambda s: risk_level_rank(s.get("risk_assessment", {}).get("level")) == 1,
        "action": "notify_department",
        "params": {"department": "清洗"},
        "check_field": "cleaning_notified",
        "error_message": "低风险必须通知清洗部门",
    },
    # 影响跑道：必须通知塔台
    "runway_impact_atc_notification": {
        "condition": lambda s: bool(s.get("spatial_analysis", {}).get("affected_runways")),
        "action": "notify_department",
        "params": {"department": "塔台"},
        "check_field": "atc_notified",
        "error_message": "影响跑道运行必须通知塔台",
    },
}


def determine_fsm_state(state: AgentState) -> FSMState:
    """
    根据 Agent 状态确定当前应该处于的 FSM 状态

    这是融合方案的关键：
    - 不是 FSM 驱动 Agent
    - 而是根据 Agent 已完成的工作，推断 FSM 状态

    注意：此函数现已委托给 fsm.FSMEngine.infer_state()
    """
    session_id = state.get("session_id", "default")
    scenario_type = state.get("scenario_type", "oil_spill")
    validator = get_fsm_validator(session_id, scenario_type, state)

    # 使用新的 FSM 引擎推断状态
    inferred = validator.engine.infer_state(state)

    # 转换为原有的 FSMState 枚举
    return FSMState(inferred)


def check_fsm_preconditions(target_state: FSMState, state: AgentState) -> List[str]:
    """检查 FSM 状态的前置条件"""
    session_id = state.get("session_id", "default")
    scenario_type = state.get("scenario_type", "oil_spill")
    validator = get_fsm_validator(session_id, scenario_type, state)

    return validator.check_preconditions(target_state.value, state)


def check_mandatory_actions(state: AgentState) -> List[str]:
    """检查强制动作是否完成"""
    session_id = state.get("session_id", "default")
    scenario_type = state.get("scenario_type", "oil_spill")
    validator = get_fsm_validator(session_id, scenario_type, state)

    errors, _ = validator.check_mandatory_actions(state)
    return errors


def validate_state_transition(from_state: FSMState, to_state: FSMState) -> bool:
    """验证 FSM 状态转换是否合法"""
    if from_state == to_state:
        return True

    allowed_transitions = FSM_TRANSITIONS.get(from_state, [])
    return to_state in allowed_transitions


def fsm_validator_node(state: AgentState) -> Dict[str, Any]:
    """
    FSM 验证节点

    融合设计：
    1. 根据 Agent 状态推断当前 FSM 状态
    2. 验证状态转换是否合法
    3. 检查前置条件
    4. 检查强制动作
    5. 发现问题时生成错误列表，让 Agent 补救
    """
    session_id = state.get("session_id", "default")
    scenario_type = state.get("scenario_type", "oil_spill")
    validator = get_fsm_validator(session_id, scenario_type, state)

    # 执行验证
    result = validator.validate(state)

    # 获取历史记录
    fsm_history = state.get("fsm_history", [])

    # 如果状态发生变化，记录到历史
    current_fsm = state.get("fsm_state", FSMStateEnum.INIT.value)
    if current_fsm != result.inferred_state:
        fsm_history.append({
            "from_state": current_fsm,
            "to_state": result.inferred_state,
            "trigger": "agent_action",
            "timestamp": datetime.now().isoformat(),
        })

    # 合并错误和警告
    errors = result.errors.copy()
    if result.warnings:
        # 警告不阻塞流程，但记录下来
        pass

    # 确定下一步
    if errors:
        # 有错误，返回推理节点处理
        next_node = "reasoning"
    elif result.inferred_state in [FSMStateEnum.P8_CLOSE.value, FSMStateEnum.COMPLETED.value]:
        # 达到完成条件
        next_node = "output_generator"
    else:
        # 继续推理
        next_node = "reasoning"

    return {
        "fsm_state": result.inferred_state,
        "fsm_history": fsm_history,
        "fsm_validation_errors": errors,
        "next_node": next_node,
    }


# ============================================================
# 扩展接口（新增功能）
# ============================================================

def get_next_required_actions(state: AgentState) -> List[Dict[str, Any]]:
    """
    获取下一步需要执行的动作

    Args:
        state: Agent 状态

    Returns:
        推荐动作列表
    """
    session_id = state.get("session_id", "default")
    scenario_type = state.get("scenario_type", "oil_spill")
    validator = get_fsm_validator(session_id, scenario_type, state)

    return validator.get_next_required_actions(state)


def get_validation_report(state: AgentState) -> Dict[str, Any]:
    """
    获取完整的验证报告

    Args:
        state: Agent 状态

    Returns:
        验证报告
    """
    session_id = state.get("session_id", "default")
    scenario_type = state.get("scenario_type", "oil_spill")
    validator = get_fsm_validator(session_id, scenario_type, state)

    return validator.generate_validation_report(state)


def get_fsm_progress(state: AgentState) -> Dict[str, Any]:
    """
    获取 FSM 处理进度

    Args:
        state: Agent 状态

    Returns:
        进度信息
    """
    session_id = state.get("session_id", "default")
    scenario_type = state.get("scenario_type", "oil_spill")
    validator = get_fsm_validator(session_id, scenario_type, state)

    # 先同步状态
    validator.engine.sync_with_agent_state(state)

    return validator.engine.get_progress()


def can_close_event(state: AgentState) -> tuple:
    """
    检查是否可以关闭事件

    Args:
        state: Agent 状态

    Returns:
        (是否可以关闭, 阻塞原因列表)
    """
    session_id = state.get("session_id", "default")
    scenario_type = state.get("scenario_type", "oil_spill")
    validator = get_fsm_validator(session_id, scenario_type, state)

    return validator.check_can_close(state)
