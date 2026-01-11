"""
输出生成节点

职责：
1. 汇总所有分析结果
2. 调用 LLM 基于 SKILL 规范生成检查单报告
3. 格式化最终输出
"""
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List

from agent.state import AgentState, FSMState, RiskLevel
from config.llm_config import get_llm_client

# =============================================================================
# 常量定义
# =============================================================================

# 油液类型映射（报告用，详细）
FLUID_TYPE_MAP = {
    "FUEL": "航空燃油(Jet Fuel)",
    "HYDRAULIC": "液压油",
    "OIL": "发动机滑油",
}

# 油液类型映射（摘要用，简洁）
FLUID_TYPE_MAP_SIMPLE = {
    "FUEL": "燃油",
    "HYDRAULIC": "液压油",
    "OIL": "滑油",
}

# 泄漏面积映射（报告用）
LEAK_SIZE_MAP = {
    "LARGE": ">5㎡",
    "MEDIUM": "1-5㎡",
    "SMALL": "<1㎡",
    "UNKNOWN": "待评估",
}

# 泄漏面积映射（摘要用）
LEAK_SIZE_MAP_SIMPLE = {
    "LARGE": "大面积",
    "MEDIUM": "中等面积",
    "SMALL": "小面积",
}

# 动作名称映射
ACTION_NAME_MAP = {
    "ask_for_detail": "信息确认",
    "assess_risk": "风险评估",
    "calculate_impact_zone": "影响范围分析",
    "notify_department": "通知相关部门",
    "search_regulations": "规程检索",
}

# 部门通知状态映射配置
# 格式: 部门名称 -> (mandatory_key, notified_map_keys)
DEPT_NOTIFICATION_CONFIG = {
    "机务": ("maintenance_notified", ["机务"]),
    "清污/场务": ("cleaning_notified", ["清洗", "清污"]),
    "消防": ("fire_dept_notified", ["消防"]),
    "机场运行指挥": ("operations_notified", ["运控", "运行指挥"]),
    "安全监察": ("safety_notified", ["安全监察"]),
}

# =============================================================================
# 辅助函数
# =============================================================================


def _build_affected_areas_text(spatial: Dict[str, Any], separator: str = "、") -> str:
    """
    从空间分析结果构建受影响区域文本

    Args:
        spatial: 空间分析字典
        separator: 分隔符，默认为顿号

    Returns:
        格式化的受影响区域文本
    """
    affected_areas = []
    if spatial.get("isolated_nodes"):
        affected_areas.extend(spatial["isolated_nodes"])
    if spatial.get("affected_taxiways"):
        affected_areas.extend([f"滑行道{t}" for t in spatial["affected_taxiways"]])
    if spatial.get("affected_runways"):
        affected_areas.extend([f"跑道{r}" for r in spatial["affected_runways"]])
    return separator.join(affected_areas) if affected_areas else ""


def _build_event_context(
    incident: Dict[str, Any],
    risk: Dict[str, Any],
) -> Dict[str, Any]:
    """
    构建事件上下文信息（统一字段映射）

    Args:
        incident: 事件信息字典
        risk: 风险评估字典

    Returns:
        包含格式化字段的上下文字典
    """
    return {
        "oil_type": FLUID_TYPE_MAP.get(
            incident.get("fluid_type"), incident.get("fluid_type", "不明油液")
        ),
        "leak_area": LEAK_SIZE_MAP.get(incident.get("leak_size"), "待评估"),
        "engine_status": "运行中" if incident.get("engine_status") == "RUNNING" else "已关闭",
        "is_continuous": incident.get("continuous", False),
        "is_continuous_text": "是" if incident.get("continuous") else "否",
        "risk_level": risk.get("level", "未评估"),
        "risk_score": risk.get("score", 0),
        "risk_factors": risk.get("factors", []),
        "position": incident.get("position", "未知位置"),
        "flight_no": incident.get("flight_no", "未知航班"),
    }


def _extract_notified_departments(notifications: List[Dict[str, Any]]) -> str:
    """
    从通知列表提取已通知部门文本

    Args:
        notifications: 通知记录列表

    Returns:
        顿号分隔的部门名称，如无则返回默认文本
    """
    notified_units = [n.get("department") for n in notifications if n.get("department")]
    return "、".join(notified_units) if notified_units else "暂无记录"


def _parse_llm_json_response(content: str) -> Dict[str, str] | None:
    """
    解析 LLM 返回的 JSON 响应

    Args:
        content: LLM 响应内容

    Returns:
        解析后的字典，如果解析失败或缺少必要字段则返回 None
    """
    json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    json_str = json_match.group(1) if json_match else content

    result = json.loads(json_str)

    required_keys = ["event_description", "effect_evaluation", "improvement_suggestions"]
    if all(key in result for key in required_keys):
        return result
    return None


def _build_notifications_table(coordination_units: List[Dict[str, Any]]) -> str:
    """
    构建协同单位通知记录表格行

    Args:
        coordination_units: 协调单位列表

    Returns:
        Markdown 表格行字符串
    """
    rows = []
    for unit in coordination_units:
        name = unit.get("name", "")
        notified_status = "☑ 是  ☐ 否" if unit.get("notified") else "☐ 是  ☐ 否"
        notify_time = unit.get("notify_time", "——") or "——"
        if notify_time and len(notify_time) > 19:
            notify_time = notify_time[11:19]
        rows.append(f"| {name} | {notified_status} | {notify_time} | |")
    return "\n".join(rows) + "\n" if rows else ""


# =============================================================================
# LLM 事件总结生成
# =============================================================================


def _build_deterministic_summary(
    incident: Dict[str, Any],
    risk: Dict[str, Any],
    spatial: Dict[str, Any],
    notifications: List[Dict[str, Any]],
    recommendations: List[str],
) -> Dict[str, str]:
    """
    构建确定性事件总结（作为 LLM 的回退方案）

    Returns:
        包含 event_description, effect_evaluation, improvement_suggestions 的字典
    """
    ctx = _build_event_context(incident, risk)

    continuous_text = "泄漏持续" if ctx["is_continuous"] else "泄漏已停止"
    engine_risk_text = (
        "发动机处于运转状态，存在火灾风险"
        if ctx["engine_status"] == "运行中"
        else "发动机已关闭"
    )

    event_description = (
        f"{ctx['position']}发生约{ctx['leak_area']}的{ctx['oil_type']}泄漏，"
        f"{continuous_text}，{engine_risk_text}。"
        f"经风险评估，危险等级为{ctx['risk_level']}。"
    )

    notified_text = _extract_notified_departments(notifications)
    effect_evaluation = f"已完成事件确认与风险评估，已通知：{notified_text}。后续处置待开展。"

    if not recommendations:
        recommendations = [
            "加强机坪巡查频次与质量，提升特情早期发现能力。",
            "优化应急响应流程，缩短从发现到现场处置的响应时间。",
            "定期组织相关单位进行联合演练，提升协同处置效率。",
        ]
    improvement_suggestions = "\n".join(
        [f"{i + 1}. {r}" for i, r in enumerate(recommendations[:3])]
    )

    return {
        "event_description": event_description,
        "effect_evaluation": effect_evaluation,
        "improvement_suggestions": improvement_suggestions,
    }


def _generate_event_summary_with_llm(
    incident: Dict[str, Any],
    risk: Dict[str, Any],
    spatial: Dict[str, Any],
    notifications: List[Dict[str, Any]],
    recommendations: List[str],
    knowledge: Dict[str, Any] = None,
) -> Dict[str, str]:
    """
    使用 LLM 生成事件总结（包含润色和智能建议）

    Returns:
        包含 event_description, effect_evaluation, improvement_suggestions 的字典
    """
    ctx = _build_event_context(incident, risk)
    affected_text = _build_affected_areas_text(spatial) or "无"
    notified_text = _extract_notified_departments(notifications)

    knowledge_ref = ""
    if knowledge and knowledge.get("regulations"):
        regs = knowledge["regulations"]
        if regs:
            reg = regs[0]
            knowledge_ref = (
                f"参考规程：{reg.get('title', '')}，清理方式：{reg.get('cleanup_method', '')}"
            )

    risk_factors_text = (
        ", ".join(ctx["risk_factors"]) if ctx["risk_factors"] else "无特殊因素"
    )

    prompt = f"""你是机场机坪应急响应专家，请根据以下事件信息生成专业的事件总结。

## 事件信息
- 航班号：{ctx['flight_no']}
- 发现位置：{ctx['position']}
- 油液类型：{ctx['oil_type']}
- 泄漏面积：{ctx['leak_area']}
- 是否持续滴漏：{ctx['is_continuous_text']}
- 发动机状态：{ctx['engine_status']}
- 风险等级：{ctx['risk_level']}（风险分数：{ctx['risk_score']}）
- 风险因素：{risk_factors_text}
- 受影响区域：{affected_text}
- 已通知单位：{notified_text}
{knowledge_ref}

## 输出要求
请生成以下三部分内容，使用专业、简洁的民航术语：

### 事件经过简述
用1-2句话概括事件发生经过，包含关键信息（位置、油液类型、泄漏情况、风险等级），语言流畅自然。

### 处置效果评估
根据已完成的处置动作（风险评估、通知等），评估当前处置进展和效果，1-2句话。

### 后续改进建议
根据本次事件的具体情况，提出3条针对性的改进建议（不要太笼统，要结合具体事件特点）。

请严格按照以下 JSON 格式输出：
```json
{{
  "event_description": "事件经过简述内容",
  "effect_evaluation": "处置效果评估内容",
  "improvement_suggestions": "1. 建议一\\n2. 建议二\\n3. 建议三"
}}
```"""

    try:
        llm = get_llm_client()
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        result = _parse_llm_json_response(content)
        if result:
            return result

    except Exception as e:
        logging.warning(f"LLM 事件总结生成失败，使用确定性模板: {e}")

    return _build_deterministic_summary(incident, risk, spatial, notifications, recommendations)


def generate_event_summary(state: AgentState) -> str:
    """生成事件摘要"""
    incident = state.get("incident", {})
    
    parts = []
    
    # 时间和位置
    parts.append(f"事件时间: {incident.get('report_time', '未知')}")
    if incident.get("position"):
        parts.append(f"事件位置: {incident['position']}")
    
    # 航班信息
    if incident.get("flight_no"):
        parts.append(f"航班号: {incident['flight_no']}")

    # 事件描述
    desc_parts = []
    if incident.get("fluid_type"):
        desc_parts.append(f"{FLUID_TYPE_MAP_SIMPLE.get(incident['fluid_type'], incident['fluid_type'])}泄漏")
    if incident.get("leak_size"):
        desc_parts.append(LEAK_SIZE_MAP_SIMPLE.get(incident['leak_size'], incident['leak_size']))
    if incident.get("continuous"):
        desc_parts.append("持续滴漏中")
    if incident.get("engine_status") == "RUNNING":
        desc_parts.append("发动机运转中")
    
    if desc_parts:
        parts.append(f"事件描述: {', '.join(desc_parts)}")
    
    return "\n".join(parts)


def generate_handling_process(state: AgentState) -> List[str]:
    """生成处置过程"""
    actions = state.get("actions_taken", [])
    process = []
    
    for action in actions:
        action_name = action.get("action", "")
        result = action.get("result", "")
        timestamp = action.get("timestamp", "")
        
        action_desc = ACTION_NAME_MAP.get(action_name, action_name)
        if result:
            process.append(f"[{timestamp}] {action_desc}: {result}")
        else:
            process.append(f"[{timestamp}] {action_desc}")
    
    return process


def generate_checklist_items(state: AgentState) -> List[Dict[str, Any]]:
    """生成检查单项目"""
    incident = state.get("incident", {})
    risk = state.get("risk_assessment", {})
    mandatory = state.get("mandatory_actions_done", {})
    
    items = []
    
    # 信息收集检查项
    items.append({
        "category": "信息收集",
        "items": [
            {"item": "油液类型确认", "status": "✓" if incident.get("fluid_type") else "✗"},
            {"item": "泄漏面积确认", "status": "✓" if incident.get("leak_size") else "✗"},
            {"item": "持续状态确认", "status": "✓" if incident.get("continuous") is not None else "✗"},
            {"item": "发动机状态确认", "status": "✓" if incident.get("engine_status") else "✗"},
            {"item": "位置确认", "status": "✓" if incident.get("position") else "✗"},
        ]
    })
    
    # 风险评估检查项
    items.append({
        "category": "风险评估",
        "items": [
            {"item": "风险等级评定", "status": "✓" if risk.get("level") else "✗"},
            {"item": "风险因素识别", "status": "✓" if risk.get("factors") else "✗"},
        ]
    })
    
    # 通知协调检查项
    items.append({
        "category": "通知协调",
        "items": [
            {"item": "消防部门通知", "status": "✓" if mandatory.get("fire_dept_notified") else "✗"},
            {"item": "塔台通知", "status": "✓" if mandatory.get("atc_notified") else "○"},  # ○ 表示可选
        ]
    })
    
    return items


def generate_operational_impact(state: AgentState) -> Dict[str, Any]:
    """生成运行影响评估"""
    spatial = state.get("spatial_analysis", {})
    flight_impact = state.get("flight_impact_prediction", {})

    # 使用辅助函数构建受影响区域列表
    affected_areas_text = _build_affected_areas_text(spatial, separator=", ")
    affected_areas = affected_areas_text.split(", ") if affected_areas_text else []

    impact = {
        "affected_areas": affected_areas,
        "affected_flights": [],
        "estimated_delay": "",
        "recommendations": [],
    }

    # 受影响航班（优先使用航班影响预测结果）
    if flight_impact and flight_impact.get("affected_flights"):
        # 使用预测结果
        affected_flights = flight_impact["affected_flights"]
        for flight_info in affected_flights:
            callsign = flight_info.get("callsign", "UNKNOWN")
            delay = flight_info.get("estimated_delay_minutes", 0)
            reason = flight_info.get("delay_reason", "")
            impact["affected_flights"].append(
                f"{callsign}: 预计延误 {delay} 分钟 ({reason})"
            )
    else:
        # 回退到 spatial_analysis 中的简单结果
        affected_flights = spatial.get("affected_flights", {})
        for flight, delay in affected_flights.items():
            impact["affected_flights"].append(f"{flight}: 预计延误{delay}")

    # 估算延误
    if flight_impact and flight_impact.get("statistics"):
        stats = flight_impact["statistics"]
        total = stats.get("total_affected_flights", 0)
        avg_delay = stats.get("average_delay_minutes", 0)
        if total > 0:
            impact["estimated_delay"] = f"预计影响 {total} 架次，平均延误 {avg_delay:.0f} 分钟"

    # 建议
    if spatial.get("affected_runways"):
        impact["recommendations"].append("建议启用备用跑道")
    if len(impact["affected_areas"]) > 3:
        impact["recommendations"].append("建议发布机场通告(NOTAM)")

    return impact


def generate_recommendations(state: AgentState) -> List[str]:
    """生成建议措施"""
    risk = state.get("risk_assessment", {})
    spatial = state.get("spatial_analysis", {})
    incident = state.get("incident", {})
    flight_impact = state.get("flight_impact_prediction", {})

    recommendations = []

    # 根据风险等级生成建议
    risk_level = risk.get("level", "")
    if risk_level == RiskLevel.HIGH.value:
        recommendations.append("立即执行应急响应程序")
        recommendations.append("保持与消防部门的持续联络")
        if incident.get("engine_status") == "RUNNING":
            recommendations.append("要求机组关闭发动机")
    elif risk_level == RiskLevel.MEDIUM.value:
        recommendations.append("持续监控泄漏情况")
        recommendations.append("准备应急物资")

    # 根据空间分析生成建议
    if spatial.get("affected_runways"):
        recommendations.append("协调进离港航班使用备用跑道")
    if spatial.get("isolated_nodes"):
        recommendations.append(f"隔离区域: {', '.join(spatial['isolated_nodes'])}")

    # 根据航班影响预测生成建议
    if flight_impact and flight_impact.get("statistics"):
        stats = flight_impact["statistics"]
        total = stats.get("total_affected_flights", 0)
        avg_delay = stats.get("average_delay_minutes", 0)

        if total > 0:
            recommendations.append(f"预计影响航班: {total} 架次")
            recommendations.append(f"预计平均延误: {avg_delay:.0f} 分钟")

            # 根据延误严重程度给出建议
            if avg_delay >= 60:
                recommendations.append("延误严重，建议发布机场通告(NOTAM)")
                recommendations.append("建议启动航班大面积延误应急预案")
            elif avg_delay >= 30:
                recommendations.append("延误较重，建议向旅客及时发布延误信息")

            # 根据严重程度分布给出建议
            severity = stats.get("severity_distribution", {})
            if severity.get("high", 0) > 0:
                recommendations.append(f"高严重航班 {severity['high']} 架次，建议重点关注")
            if severity.get("medium", 0) > 5:
                recommendations.append("中等影响航班较多，建议优化调度")

    # 通用建议
    recommendations.append("事件结束后进行复盘总结")
    recommendations.append("更新应急处置经验库")

    return recommendations


def generate_coordination_units(state: AgentState) -> List[Dict[str, Any]]:
    """生成需协调单位列表（详细记录格式）"""
    risk = state.get("risk_assessment", {})
    spatial = state.get("spatial_analysis", {})
    notifications = state.get("notifications_sent", [])
    mandatory = state.get("mandatory_actions_done", {})

    units = []

    # 已通知的单位映射
    notified_map = {}
    for n in notifications:
        dept = n.get("department")
        notified_map[dept] = {
            "notified": True,
            "time": n.get("timestamp", ""),
            "priority": n.get("priority", "normal"),
            "message": n.get("message", ""),
        }

    # 定义所有可能需要协调的单位（与SKILL模板完全一致）
    all_units = [
        {
            "name": "机务",
            "required": risk.get("level") in [RiskLevel.MEDIUM.value, "MEDIUM_HIGH", RiskLevel.HIGH.value],
            "contact": "内线8200",
            "role": "航空器故障排查与维修",
        },
        {
            "name": "清污/场务",
            "required": True,  # 始终需要清污
            "contact": "内线8400",
            "role": "油污清理与环境恢复",
        },
        {
            "name": "消防",
            "required": risk.get("level") == RiskLevel.HIGH.value or risk.get("level") == "MEDIUM_HIGH",
            "contact": "119/内线8119",
            "role": "应急救援及火灾风险防控",
        },
        {
            "name": "机场运行指挥",
            "required": True,
            "contact": "内线8000",
            "role": "整体运行协调与信息发布",
        },
        {
            "name": "安全监察",
            "required": False,
            "contact": "内线8500",
            "role": "安全监督与事件调查",
        },
    ]

    for unit in all_units:
        dept = unit["name"]

        # 使用配置映射获取通知状态
        is_notified = False
        notify_time = ""
        priority = "normal"

        if dept in DEPT_NOTIFICATION_CONFIG:
            mandatory_key, map_keys = DEPT_NOTIFICATION_CONFIG[dept]
            is_notified = mandatory.get(mandatory_key, False)
            # 尝试从多个可能的键获取时间和优先级
            for key in map_keys:
                if key in notified_map:
                    notify_time = notified_map[key].get("time", "") or notify_time
                    priority = notified_map[key].get("priority", "normal") or priority
                    if notify_time:
                        break

        # 如果有通知记录但状态未同步，尝试从通知列表获取
        if not is_notified:
            for n in notifications:
                n_dept = n.get("department", "")
                if dept in n_dept or n_dept in dept:
                    is_notified = True
                    notify_time = n.get("timestamp", "")
                    priority = n.get("priority", "normal")
                    break

        units.append({
            "name": dept,
            "required": unit["required"],
            "contact": unit["contact"],
            "role": unit["role"],
            "notified": is_notified,
            "notify_time": notify_time,
            "priority": priority or "normal",
        })

    return units


def generate_notifications_summary(state: AgentState) -> Dict[str, Any]:
    """生成通知记录汇总"""
    notifications = state.get("notifications_sent", [])
    risk = state.get("risk_assessment", {})

    summary = {
        "total_notifications": len(notifications),
        "notifications": [],
        "risk_based_required": [],
    }

    # 统计通知
    for n in notifications:
        summary["notifications"].append({
            "department": n.get("department"),
            "time": n.get("timestamp"),
            "priority": n.get("priority"),
            "status": n.get("status"),
        })

    # 根据风险等级确定应该通知的单位
    risk_level = risk.get("level", "")
    if risk_level == RiskLevel.HIGH.value:
        summary["risk_based_required"] = ["消防", "塔台", "机务", "运控"]
    elif risk_level == "MEDIUM_HIGH":
        summary["risk_based_required"] = ["消防", "机务", "运控"]
    elif risk_level == RiskLevel.MEDIUM.value:
        summary["risk_based_required"] = ["机务", "运控"]
    elif risk_level == RiskLevel.LOW.value:
        summary["risk_based_required"] = ["清洗", "运控"]

    return summary


def output_generator_node(state: AgentState) -> Dict[str, Any]:
    """
    输出生成节点

    调用 LLM 基于 SKILL 规范和知识库生成结构化的机坪特情处置检查单报告
    """
    # 构建事件数据
    incident = state.get("incident", {})
    risk = state.get("risk_assessment", {})
    spatial = state.get("spatial_analysis", {})
    actions = state.get("actions_taken", [])

    # 获取检索到的知识库内容
    knowledge = state.get("retrieved_knowledge", {})

    # 生成协调单位详细记录
    coordination_units = generate_coordination_units(state)
    notifications_summary = generate_notifications_summary(state)

    # 使用确定性模板生成报告，保证结构完整
    final_answer = _render_checklist_report(state, coordination_units, notifications_summary)

    # 构建结构化报告（供 API 返回）
    recent_actions = [a.get("action", "") for a in actions[-5:]]
    execution_summary = {
        "session_id": state.get("session_id", ""),
        "fsm_state": state.get("fsm_state", ""),
        "actions_total": len(actions),
        "recent_actions": recent_actions,
    }
    final_report = {
        "title": "机坪特情处置检查单",
        "event_summary": generate_event_summary(state),
        "risk_level": risk.get("level", "未评估"),
        "risk_score": risk.get("score", 0),
        "handling_process": generate_handling_process(state),
        "checklist_items": generate_checklist_items(state),
        "coordination_units": coordination_units,
        "notifications_summary": notifications_summary,
        "recommendations": generate_recommendations(state),
        "operational_impact": generate_operational_impact(state),
        "execution_summary": execution_summary,
        "generated_at": datetime.now().isoformat(),
        "fsm_final_state": state.get("fsm_state", ""),
        "llm_generated": False,
    }

    return {
        "final_report": final_report,
        "final_answer": final_answer,
        "is_complete": True,
        "fsm_state": FSMState.COMPLETED.value,
    }


def _render_checklist_report(state: AgentState, coordination_units: List[Dict[str, Any]], notifications_summary: Dict[str, Any]) -> str:
    """生成完整的检查单 Markdown（确定性模板）"""
    incident = state.get("incident", {})
    risk = state.get("risk_assessment", {})
    spatial = state.get("spatial_analysis", {})
    knowledge = state.get("retrieved_knowledge", {})
    flight_impact = state.get("flight_impact_prediction", {})
    position_impact = state.get("position_impact_analysis", {})
    actions = state.get("actions_taken", [])
    session_id = state.get("session_id", "") or "——"
    fsm_state = state.get("fsm_state", "") or "——"
    recent_actions = [a.get("action", "") for a in actions[-5:] if a.get("action")]
    recent_actions_text = "、".join(recent_actions) if recent_actions else "——"

    # 事件编号与时间
    event_id = f"TQCZ-{datetime.now().strftime('%Y%m%d')}-{datetime.now().strftime('%H%M')}"
    report_time = incident.get("report_time") or datetime.now().isoformat()
    report_time_str = report_time[:19].replace("T", " ")

    # 航班号
    flight_no_display = incident.get("flight_no_display") or incident.get("flight_no") or ""
    aircraft_display = flight_no_display or "——"

    # 使用公共上下文构建函数
    ctx = _build_event_context(incident, risk)
    oil_type = ctx["oil_type"]
    leak_area = ctx["leak_area"]
    # 报告中发动机状态显示为"关闭"而非"已关闭"
    engine_status = "运行中" if incident.get("engine_status") == "RUNNING" else "关闭"
    is_continuous = ctx["is_continuous_text"]
    risk_level = ctx["risk_level"]
    risk_score = ctx["risk_score"]

    # 协同单位通知记录表
    notifications_table = _build_notifications_table(coordination_units)

    # 影响区域
    affected_area_text = _build_affected_areas_text(spatial, separator=", ") or "——"

    # 运行影响
    flight_delay_text = "——"
    if flight_impact and flight_impact.get("statistics"):
        stats = flight_impact["statistics"]
        total = stats.get("total_affected_flights", 0)
        avg_delay = stats.get("average_delay_minutes", 0)
        if total > 0:
            flight_delay_text = f"预计影响 {total} 架次，平均延误 {avg_delay:.0f} 分钟"

    runway_adjust_text = "——"
    if spatial.get("affected_taxiways") or spatial.get("affected_runways"):
        runway_adjust_text = "建议调整滑行路线/跑道运行"

    # 处置建议（用于 LLM 参考）
    recommendations = generate_recommendations(state)

    # 使用 LLM 生成事件总结（包含润色和智能建议）
    notifications = state.get("notifications_sent", [])
    event_summary = _generate_event_summary_with_llm(
        incident=incident,
        risk=risk,
        spatial=spatial,
        notifications=notifications,
        recommendations=recommendations,
        knowledge=knowledge,
    )

    # 提取 LLM 生成的内容
    event_description = event_summary.get("event_description", "")
    effect_text = event_summary.get("effect_evaluation", "")
    improvement_suggestions = event_summary.get("improvement_suggestions", "")

    # 清理方式（取知识库第一个）
    cleanup_method = "——"
    regs = knowledge.get("regulations", []) if knowledge else []
    if regs and regs[0].get("cleanup_method"):
        cleanup_method = regs[0].get("cleanup_method")

    return f"""# 机坪特情处置检查单

**适用范围**：机坪航空器漏油、油污、渗漏等特情事件的识别、处置与闭环记录

## 1. 事件基本信息
| 项目 | 记录 |
|-----|------|
| 事件编号 | {event_id} |
| 航班号/航空器注册号 | {aircraft_display} |
| 事件触发时间 | {report_time_str} |
| 上报方式 | {incident.get('discovery_method', '巡查') or '巡查'} |
| 报告人 | {incident.get('reported_by', '——') or '——'} |
| 发现位置 | {incident.get('position', '——')} |
| 风险等级 | {risk_level} (风险分数: {risk_score}) |

### 1.1 执行轨迹摘要
| 项目 | 记录 |
|-----|------|
| 会话ID | {session_id} |
| FSM 状态 | {fsm_state} |
| 工具执行次数 | {len(actions)} |
| 最近动作 | {recent_actions_text} |

## 2. 特情初始确认
### 2.1 漏油基本情况
| 关键项 | 选择/填写 |
|-------|---------|
| 油液类型 | {oil_type} |
| 是否持续滴漏 | {is_continuous} |
| 发动机/APU状态 | {engine_status} |
| 泄漏面积评估 | {leak_area} |
| 漏油形态 | 滴漏 |
| 现场气象条件 | —— |

## 3. 初期风险控制措施
检查项（勾选已执行项）：

- {"☑" if engine_status == "关闭" else "☐"} 已要求机组关车或保持关车
- ☐ 已禁止航空器滑行
- ☐ 已设置安全警戒区域
- ☐ 已排除现场点火源
- ☐ 已向周边航空器发布注意通告

## 4. 协同单位通知记录

| 单位 | 是否通知 | 通知时间 | 备注 |
|-----|---------|---------|------|
{notifications_table}## 5. 区域隔离与现场检查
### 5.1 隔离与运行限制
| 项目 | 是/否 | 备注 |
|-----|------|-----|
| 隔离区域已明确划定 | ☐ 是  ☐ 否 | |
| 滑行道关闭执行 | ☐ 是  ☐ 否 | |
| 停机位暂停使用 | ☐ 是  ☐ 否 | |
| 跑道运行受影响 | ☐ 是  ☐ 否 | |

### 5.2 现场检查要点

- ☐ 地面油污范围已确认
- ☐ 周边设施未受污染
- ☐ 无二次泄漏风险
- ☐ 无新增安全隐患

## 6. 清污处置执行情况
| 项目 | 记录 |
|-----|------|
| 清污车辆到场时间 | —— |
| 作业开始时间 | —— |
| 作业结束时间 | —— |
| 清理方式 | {cleanup_method} |
| 是否符合环保要求 | —— |

## 7. 处置结果确认
| 检查项 | 结果 | 备注 |
|-------|------|-----|
| 泄漏已停止 | ☐ 是  ☐ 否 | |
| 地面无残留油污 | ☐ 是  ☐ 否 | |
| 表面摩擦系数符合要求 | ☐ 是  ☐ 否 | |
| 现场检查合格 | ☐ 是  ☐ 否 | |

## 8. 区域恢复与运行返还
检查项（勾选已完成项）：

- ☐ 已解除现场警戒
- ☐ 已恢复滑行道使用
- ☐ 已恢复停机位使用
- ☐ 已通知管制/运控运行恢复

## 9. 运行影响评估
| 影响项 | 说明 |
|-------|-----|
| 航班延误情况 | {flight_delay_text} |
| 航班调整/取消 | —— |
| 机坪运行影响 | {affected_area_text} |
| 跑道/滑行路线调整 | {runway_adjust_text} |

## 10. 事件总结与改进建议
**事件经过简述：**
{event_description}

**处置效果评估：**
{effect_text}

**后续改进建议：**
{improvement_suggestions}

## 11. 签字与存档
| 角色 | 姓名 | 签字 | 时间 |
|-----|------|-----|------|
| 现场负责人 | | | |
| 机务代表 | | | |
| 清洗/场务代表 | | | |
| 消防代表 | | | |
| 机场运行指挥 | | | |

---
**说明**：本检查单应随事件处置过程同步填写，事件关闭后统一归档，用于运行复盘与安全审计。

报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
