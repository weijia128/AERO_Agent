"""
Prompt 构建入口
"""
from typing import Any

from agent.state import AgentState
from scenarios.base import ScenarioRegistry
from config.airline_codes import format_callsign_display


def _format_callsign_for_prompt(flight_no: str) -> str:
    """格式化呼号用于 Prompt"""
    return format_callsign_display(flight_no) or flight_no


def build_prompt(
    state: AgentState,
    context: str,
    messages: list,
    reasoning_history: list,
    tools_description: str,
    checklist: dict,
    fsm_errors: list,
) -> str:
    """使用场景专属配置构建 ReAct Prompt"""

    scenario_type = state.get("scenario_type", "oil_spill")
    scenario = ScenarioRegistry.get(scenario_type)

    # 获取场景的 System Prompt
    if scenario and scenario.system_prompt:
        parts = [scenario.system_prompt]
    else:
        # 回退到默认 prompt
        from agent.prompts.react_template import SYSTEM_PROMPT
        parts = [SYSTEM_PROMPT]

    # 工具说明
    parts.append(f"\n## 可用工具\n{tools_description}")

    # 当前状态
    parts.append(f"\n## 当前状态\n{context}")

    # 【新增】空间分析结果
    spatial = state.get("spatial_analysis", {})
    if spatial:
        parts.append(f"\n## 影响范围分析结果")
        if spatial.get("anchor_node"):
            parts.append(f"起始位置: {spatial['anchor_node']} ({spatial.get('anchor_node_type', '')})")
        if spatial.get("isolated_nodes"):
            parts.append(f"隔离区域: {len(spatial['isolated_nodes'])} 个节点")
        if spatial.get("affected_stands"):
            parts.append(f"受影响机位: {', '.join(spatial['affected_stands'])}")
        if spatial.get("affected_taxiways"):
            parts.append(f"受影响滑行道: {', '.join(spatial['affected_taxiways'])}")
        if spatial.get("affected_runways"):
            parts.append(f"受影响跑道: {', '.join(spatial['affected_runways'])}")

    # 【新增】航班影响预测结果
    flight_impact = state.get("flight_impact_prediction", {})
    if flight_impact:
        parts.append(f"\n## 航班影响预测结果")
        stats = flight_impact.get("statistics", {})
        if stats:
            total = stats.get("total_affected_flights", 0)
            avg_delay = stats.get("average_delay_minutes", 0)
            parts.append(f"预计受影响航班: {total} 架次")
            parts.append(f"预计平均延误: {avg_delay:.1f} 分钟")

            severity = stats.get("severity_distribution", {})
            if severity:
                parts.append(
                    f"影响分布: 严重 {severity.get('high', 0)}, "
                    f"中等 {severity.get('medium', 0)}, "
                    f"轻微 {severity.get('low', 0)}"
                )

    # 【新增】位置特定影响分析结果
    position_impact = state.get("position_impact_analysis", {})
    if position_impact:
        parts.append(f"\n## 位置特定影响分析结果")
        direct = position_impact.get("direct_impact", {})
        if direct:
            facility_name = direct.get("affected_facility", "")
            parts.append(f"事发设施: {facility_name}")
            if direct.get("closure_time_minutes"):
                parts.append(f"预计封闭时间: {direct['closure_time_minutes']} 分钟")
            if direct.get("severity_score"):
                parts.append(f"严重程度: {direct['severity_score']:.1f}/5.0")

        adjacent = position_impact.get("adjacent_impact", {})
        if adjacent and adjacent.get("total_adjacent", 0) > 0:
            parts.append(f"相邻设施影响: {adjacent['total_adjacent']} 个")
            count_by_type = adjacent.get("count_by_type", {})
            if count_by_type.get("机位", 0) > 0:
                parts.append(f"  - 受影响机位: {count_by_type['机位']} 个")
            if count_by_type.get("滑行道", 0) > 0:
                parts.append(f"  - 受影响滑行道: {count_by_type['滑行道']} 条")
            if count_by_type.get("跑道", 0) > 0:
                parts.append(f"  - 受影响跑道: {count_by_type['跑道']} 条")

        efficiency = position_impact.get("efficiency_impact", {})
        if efficiency:
            parts.append(f"运行效率影响: {efficiency.get('description', '')}")
            if efficiency.get("delay_per_flight"):
                parts.append(f"预计延误: {efficiency['delay_per_flight']} 分钟/架次")
            if efficiency.get("capacity_reduction_percent"):
                parts.append(f"容量降低: {efficiency['capacity_reduction_percent']}%")

    # 航班号信息（如果已知）
    incident = state.get("incident", {})
    flight_no = incident.get("flight_no")
    if flight_no:
        callsign = _format_callsign_for_prompt(flight_no)
        parts.append(f"\n## 重要：当前已知机号\n**机号**: {callsign}")
        parts.append(f"**所有后续问题前必须加上机号称呼**: 例如 \"{callsign}，[问题内容]\"")
        parts.append(f"**禁止使用'机长'称呼**，必须使用机号 {callsign}")

    # Checklist - 按场景定义的顺序，区分 P1 必填 / P2 可选
    if scenario:
        p1_order = []
        for field in scenario.p1_fields:
            key = field.get("key")
            if key:
                p1_order.append(str(key))
        p2_order = []
        for field in scenario.p2_fields:
            key = field.get("key")
            if key:
                p2_order.append(str(key))
        missing_p1 = [f for f in p1_order if not checklist.get(f, False)]
        missing_p2 = [f for f in p2_order if not checklist.get(f, False)]
        collected_fields = [f for f, v in checklist.items() if v]
        field_names = scenario.field_names
    else:
        missing_p1 = [f for f, v in checklist.items() if not v]
        missing_p2 = []
        collected_fields = [f for f, v in checklist.items() if v]
        field_names = {}

    checklist_text = "\n## Checklist 状态"
    if collected_fields:
        names = [field_names.get(f, f) for f in collected_fields]
        checklist_text += f"\n已收集（不要再问）: {', '.join(names)}"
    if missing_p1:
        names = [field_names.get(f, f) for f in missing_p1]
        checklist_text += f"\n必填(P1)待收集（按顺序询问）:"
        for i, name in enumerate(names, 1):
            checklist_text += f"\n  {i}. {name}"
    else:
        checklist_text += "\nP1 信息已完成，可进入风险评估/处置。"

    if missing_p2:
        names = [field_names.get(f, f) for f in missing_p2]
        checklist_text += f"\n可选(P2)待收集（如需要再询问）: {', '.join(names)}"

    parts.append(checklist_text)

    # FSM 错误
    if fsm_errors:
        parts.append(f"\n## 需要处理的问题\n" + "\n".join(f"- {e}" for e in fsm_errors))

    # 对话历史
    if messages:
        msg_lines = []
        for msg in messages[-3:]:
            role = "用户" if msg.get("role") == "user" else "Agent"
            msg_lines.append(f"{role}: {msg.get('content', '')[:200]}")
        parts.append(f"\n## 对话历史\n" + "\n".join(msg_lines))

        # 检查上一轮是否已经询问过问题（Agent 发送了消息）
        last_msg = messages[-1]
        if last_msg.get("role") == "assistant":
            parts.append("\n## 重要：已发送询问")
            parts.append("上一轮已经向用户发送了问题，当前应**等待用户回答**，不要继续调用工具！")
            parts.append("请直接输出 'Final Answer: 等待用户回答...' 表示暂停")

    # 推理历史
    if reasoning_history:
        history_lines = []
        for step in reasoning_history[-3:]:
            history_lines.append(f"Step {step.get('step')}: {step.get('thought', '')[:100]}")
            if step.get("observation"):
                history_lines.append(f"  Observation: {step['observation'][:100]}")
        parts.append(f"\n## 推理历史\n" + "\n".join(history_lines))

    parts.append("\n## 请决定下一步行动")

    return "\n".join(parts)


def build_scenario_prompt(*args: Any, **kwargs: Any) -> str:
    """兼容旧调用名"""
    return build_prompt(*args, **kwargs)
