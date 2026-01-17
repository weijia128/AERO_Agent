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
from agent.state import AgentState, FSMState, risk_level_rank
from config.llm_config import get_llm_client
from agent.nodes.template_renderer import render_report
from scenarios.base import ScenarioRegistry

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
    "机务": ("maintenance_notified", ["机务", "塔台"]),  # 塔台通知时也更新机务状态
    "清污/场务": ("cleaning_notified", ["清洗", "清污"]),
    "消防": ("fire_dept_notified", ["消防"]),
    "机场运行指挥": ("operations_notified", ["运控", "运行指挥", "塔台"]),
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


def _build_summary_context(
    incident: Dict[str, Any],
    risk: Dict[str, Any],
    spatial: Dict[str, Any],
    notifications: List[Dict[str, Any]],
    knowledge: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """构建摘要模板上下文。"""
    ctx = _build_event_context(incident, risk)
    affected_text = _build_affected_areas_text(spatial) or "无"
    notified_text = _extract_notified_departments(notifications) or "暂无记录"

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

    return {
        "flight_no": ctx["flight_no"],
        "position": ctx["position"],
        "event_type": incident.get("event_type", "确认/疑似"),
        "affected_part": incident.get("affected_part", "待确认"),
        "current_status": incident.get("current_status", "待检查"),
        "risk_level": ctx["risk_level"],
        "risk_score": ctx["risk_score"],
        "notified_units": notified_text,
        "knowledge_ref": knowledge_ref,
        "oil_type": ctx["oil_type"],
        "leak_area": ctx["leak_area"],
        "is_continuous": ctx["is_continuous_text"],
        "engine_status": ctx["engine_status"],
        "risk_factors": risk_factors_text,
        "affected_areas": affected_text,
        "continuous_text": "泄漏持续" if ctx["is_continuous"] else "泄漏已停止",
        "engine_risk": (
            "发动机处于运转状态，存在火灾风险"
            if ctx["engine_status"] == "运行中"
            else "发动机已关闭"
        ),
    }


def _format_template(template: str, context: Dict[str, Any]) -> str:
    """安全格式化模板，保留未提供字段占位。"""
    result = template
    for key, value in context.items():
        result = result.replace(f"{{{key}}}", str(value))
    return result


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


# =============================================================================
# LLM 事件总结生成
# =============================================================================


def _build_deterministic_summary(
    incident: Dict[str, Any],
    risk: Dict[str, Any],
    spatial: Dict[str, Any],
    notifications: List[Dict[str, Any]],
    recommendations: List[str],
    scenario_type: str = "oil_spill",
    knowledge: Dict[str, Any] | None = None,
) -> Dict[str, str]:
    """
    构建确定性事件总结（作为 LLM 的回退方案）

    Returns:
        包含 event_description, effect_evaluation, improvement_suggestions 的字典
    """
    ctx = _build_event_context(incident, risk)
    scenario = ScenarioRegistry.get(scenario_type)
    summary_prompts = scenario.summary_prompts if scenario else {}
    fallback = summary_prompts.get("fallback") if summary_prompts else None
    if fallback:
        summary_context = _build_summary_context(
            incident=incident,
            risk=risk,
            spatial=spatial,
            notifications=notifications,
            knowledge=knowledge,
        )
        return {
            "event_description": _format_template(
                fallback.get("event_description", ""), summary_context
            ),
            "effect_evaluation": _format_template(
                fallback.get("effect_evaluation", ""), summary_context
            ),
            "improvement_suggestions": _format_template(
                fallback.get("improvement_suggestions", ""), summary_context
            ),
        }

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

    if scenario_type == "bird_strike":
        event_description = (
            f"{incident.get('position', '未知位置')}发生鸟击（{incident.get('event_type', '确认/疑似')}），"
            f"影响部位：{incident.get('affected_part', '待确认')}，当前状态：{incident.get('current_status', '待检查')}。"
        )
        effect_evaluation = f"已完成事件确认，已通知：{_extract_notified_departments(notifications)}。"
        improvement_suggestions = "\n".join(
            [
                "1. 安排停场检查确认受损部位与程度。",
                "2. 评估是否需要返航/改降或更换航路。",
                "3. 记录鸟击信息并通报运行/机务/消防。",
            ]
        )
        return {
            "event_description": event_description,
            "effect_evaluation": effect_evaluation,
            "improvement_suggestions": improvement_suggestions,
        }

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
    scenario_type: str,
    knowledge: Dict[str, Any] = None,
) -> Dict[str, str]:
    """
    使用 LLM 生成事件总结（包含润色和智能建议）

    Returns:
        包含 event_description, effect_evaluation, improvement_suggestions 的字典
    """
    ctx = _build_event_context(incident, risk)
    summary_context = _build_summary_context(
        incident=incident,
        risk=risk,
        spatial=spatial,
        notifications=notifications,
        knowledge=knowledge,
    )
    scenario = ScenarioRegistry.get(scenario_type)
    summary_prompts = scenario.summary_prompts if scenario else {}
    prompt_template = summary_prompts.get("template") if summary_prompts else None

    if prompt_template:
        prompt = _format_template(prompt_template, summary_context)
    elif scenario_type == "bird_strike":
        prompt = f"""你是机场鸟击应急响应专家，请生成简洁、可落地的事件总结。请使用提供的信息，不要编造未提供的单位/时间/数字。

事件信息（供参考）：
- 航班号：{ctx['flight_no']}
- 发生位置：{ctx['position']}
- 事件类型：{incident.get('event_type', '确认/疑似')}
- 影响部位：{incident.get('affected_part', '待确认')}
- 当前状态：{incident.get('current_status', '待检查')}
- 风险等级：{ctx['risk_level']}（风险分数：{ctx['risk_score']}）
- 已通知单位：{summary_context.get('notified_units', '')}
{summary_context.get('knowledge_ref', '')}

输出要求（严格遵守，不要添加字段）：
1) 事件经过简述：1-2 句话，包含位置/事件类型/影响部位/风险等级，避免华丽辞藻。
2) 处置效果评估：1-2 句话，基于已执行的动作（通知/检查安排等），勿夸大。
3) 后续改进建议：正好 3 条，针对性且与本次鸟击相关（如检查、通报、运行调整）。

请严格输出以下 JSON：
```json
{{
  "event_description": "事件经过简述内容，限 120 字内",
  "effect_evaluation": "处置效果评估内容，限 120 字内",
  "improvement_suggestions": "1. 建议一\\n2. 建议二\\n3. 建议三"
}}
```"""
    else:
        prompt = f"""你是机场机坪应急响应专家，请生成简洁、可落地的事件总结。请使用提供的信息，不要编造任何未提供的单位、时间或数字。

事件信息（供参考）：
- 航班号：{ctx['flight_no']}
- 发现位置：{ctx['position']}
- 油液类型：{ctx['oil_type']}
- 泄漏面积：{ctx['leak_area']}
- 是否持续滴漏：{ctx['is_continuous_text']}
- 发动机状态：{ctx['engine_status']}
- 风险等级：{ctx['risk_level']}（风险分数：{ctx['risk_score']}）
- 风险因素：{summary_context.get('risk_factors', '')}
- 受影响区域：{summary_context.get('affected_areas', '')}
- 已通知单位：{summary_context.get('notified_units', '')}
{summary_context.get('knowledge_ref', '')}

输出要求（严格遵守，不要添加字段）：
1) 事件经过简述：1-2 句话，包含位置/油液/泄漏情况/风险等级，避免华丽辞藻。
2) 处置效果评估：1-2 句话，基于已执行的动作（风险评估、通知等），勿夸大。
3) 后续改进建议：正好 3 条，针对性且与该事件相关，不要泛泛而谈。

请严格输出以下 JSON：
```json
{{
  "event_description": "事件经过简述内容，限 120 字内",
  "effect_evaluation": "处置效果评估内容，限 120 字内",
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

    return _build_deterministic_summary(
        incident,
        risk,
        spatial,
        notifications,
        recommendations,
        scenario_type=scenario_type,
        knowledge=knowledge,
    )


def generate_event_summary(state: AgentState) -> str:
    """生成事件摘要"""
    incident = state.get("incident", {})
    
    parts = []
    
    # 时间和位置
    parts.append(f"事件时间: {incident.get('report_time', '未知')}")
    if incident.get("position_display") or incident.get("position"):
        parts.append(f"事件位置: {incident.get('position_display') or incident.get('position')}")
    
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
    if risk_level_rank(risk_level) >= 3:
        recommendations.append("立即执行应急响应程序")
        recommendations.append("保持与消防部门的持续联络")
        if incident.get("engine_status") == "RUNNING":
            recommendations.append("要求机组关闭发动机")
    elif risk_level_rank(risk_level) == 2:
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
            "required": risk_level_rank(risk.get("level")) >= 2,
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
            "required": risk_level_rank(risk.get("level")) >= 3,
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

            # 如果 mandatory 标记为已通知，但没找到时间，尝试从 notifications 列表中匹配
            if is_notified and not notify_time:
                for n in notifications:
                    n_dept = n.get("department", "")
                    # 检查部门名称是否在映射列表中
                    if n_dept in map_keys:
                        notify_time = n.get("timestamp", "")
                        priority = n.get("priority", "normal")
                        break

        # 如果 mandatory 未标记，但通知列表中有记录，也尝试匹配
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
    if risk_level_rank(risk_level) >= 3:
        summary["risk_based_required"] = ["消防", "塔台", "机务", "运控"]
    elif risk_level_rank(risk_level) == 2:
        summary["risk_based_required"] = ["机务", "运控"]
    elif risk_level_rank(risk_level) == 1:
        summary["risk_based_required"] = ["清洗", "运控"]

    return summary


def _build_event_id() -> str:
    """生成事件编号。"""
    now = datetime.now()
    return f"TQCZ-{now.strftime('%Y%m%d')}-{now.strftime('%H%M')}"


def _format_report_time(report_time: str | None) -> str:
    """格式化报告时间。"""
    value = report_time or datetime.now().isoformat()
    return value[:19].replace("T", " ")


def _normalize_coordination_units(units: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """标准化协调单位字段，便于模板渲染。"""
    normalized = []
    for unit in units:
        notify_time_raw = unit.get("notify_time", "")
        # 处理空时间
        if not notify_time_raw:
            notify_time = "——"
        # 处理 ISO 8601 格式时间 (2026-01-13T11:06:40.123456)
        elif "T" in notify_time_raw:
            # 提取时间部分 HH:MM:SS
            notify_time = notify_time_raw.split("T")[1][:8]
        else:
            notify_time = notify_time_raw

        normalized.append(
            {
                "name": unit.get("name", ""),
                "role": unit.get("role", ""),
                "notified": unit.get("notified", False),
                "notify_time": notify_time,
            }
        )
    return normalized


def _build_render_context(
    state: AgentState,
    coordination_units: List[Dict[str, Any]],
    event_summary: Dict[str, str],
) -> Dict[str, Any]:
    """构建模板渲染上下文，统一格式化字段。"""
    incident = state.get("incident", {})
    risk = state.get("risk_assessment", {})
    spatial = state.get("spatial_analysis", {})
    flight_impact = state.get("flight_impact_prediction", {})
    knowledge = state.get("retrieved_knowledge", {})
    actions = state.get("actions_taken", [])

    ctx = _build_event_context(incident, risk)
    engine_status = "运行中" if incident.get("engine_status") == "RUNNING" else "关闭"

    # 事件基本信息
    report_time_str = _format_report_time(incident.get("report_time"))
    flight_no_display = incident.get("flight_no_display") or incident.get("flight_no") or "——"
    discovery_method = incident.get("discovery_method", "巡查") or "巡查"
    reported_by = incident.get("reported_by", "——") or "——"
    position = incident.get("position", "——") or "——"
    fod_type_map = {
        "METAL": "金属类",
        "PLASTIC_RUBBER": "塑料/橡胶",
        "STONE_GRAVEL": "石块/砂石",
        "LIQUID": "油液/液体异物",
        "UNKNOWN": "不明",
    }
    presence_map = {
        "ON_SURFACE": "仍在道面",
        "REMOVED": "已移除",
        "MOVING_BLOWING": "被风吹动",
        "UNKNOWN": "不明",
    }
    area_map = {
        "RUNWAY": "跑道",
        "TAXIWAY": "滑行道",
        "APRON": "机坪",
        "UNKNOWN": "不明",
    }
    size_map = {
        "SMALL": "小（<5cm）",
        "MEDIUM": "中（5-15cm）",
        "LARGE": "大（>15cm）",
        "UNKNOWN": "不明",
    }
    phase_map = {
        "PUSHBACK": "推出",
        "TAXI": "滑行",
        "TAKEOFF_ROLL": "起飞滑跑",
        "INITIAL_CLIMB": "起飞后爬升",
        "CRUISE": "巡航",
        "DESCENT": "下降",
        "APPROACH": "进近",
        "LANDING_ROLL": "落地滑跑",
        "ON_STAND": "停机位",
        "UNKNOWN": "不明",
    }
    evidence_map = {
        "CONFIRMED_STRIKE_WITH_REMAINS": "确认撞击有残留",
        "SYSTEM_WARNING": "系统告警",
        "ABNORMAL_NOISE_VIBRATION": "异响/振动",
        "SUSPECTED_ONLY": "仅怀疑",
        "NO_ABNORMALITY": "无异常",
        "UNKNOWN": "不明",
    }
    bird_info_map = {
        "LARGE_BIRD": "大型鸟类",
        "FLOCK": "鸟群",
        "MEDIUM_SMALL_SINGLE": "中小型单只",
        "UNKNOWN": "不明",
    }
    bird_ops_impact_map = {
        "RTO_OR_RTB": "中断起飞/返航",
        "BLOCKING_RUNWAY_OR_TAXIWAY": "占用跑道/滑行道",
        "REQUEST_MAINT_CHECK": "请求机务检查",
        "NO_OPS_IMPACT": "不影响运行",
        "UNKNOWN": "不明",
    }

    # 运行影响
    affected_area_text = _build_affected_areas_text(spatial, separator=", ") or "——"
    flight_delay_text = "——"
    if flight_impact and flight_impact.get("statistics"):
        stats = flight_impact["statistics"]
        total = stats.get("total_affected_flights", 0)
        avg_delay = stats.get("average_delay_minutes", 0)
        if total > 0:
            flight_delay_text = f"预计影响 {total} 架次，平均延误 {avg_delay:.0f} 分钟"
    runway_adjust_text = (
        "建议调整滑行路线/跑道运行"
        if spatial.get("affected_taxiways") or spatial.get("affected_runways")
        else "——"
    )

    # 知识库
    cleanup_method = "——"
    regs = knowledge.get("regulations", []) if knowledge else []
    if regs and regs[0].get("cleanup_method"):
        cleanup_method = regs[0].get("cleanup_method")

    recent_actions = [a.get("action", "") for a in actions[-5:] if a.get("action")]
    recent_actions_text = "、".join(recent_actions) if recent_actions else "——"

    return {
        "scope": "机坪特情处置检查单",
        "event_id": _build_event_id(),
        "aircraft_display": flight_no_display,
        "report_time": report_time_str,
        "discovery_method": discovery_method,
        "reported_by": reported_by,
        "position": position,
        "risk_level": ctx["risk_level"],
        "risk_score": ctx["risk_score"],
        "session_id": state.get("session_id", "") or "——",
        "fsm_state": state.get("fsm_state", "") or "——",
        "actions_total": len(actions),
        "recent_actions_text": recent_actions_text,
        "oil_type": ctx["oil_type"],
        "is_continuous": ctx["is_continuous_text"],
        "engine_status": engine_status,
        "leak_area": ctx["leak_area"],
        "coordination_units": _normalize_coordination_units(coordination_units),
        "cleanup_method": cleanup_method,
        "flight_delay_text": flight_delay_text,
        "affected_area_text": affected_area_text,
        "runway_adjust_text": runway_adjust_text,
        "event_description": event_summary.get("event_description", "——"),
        "effect_text": event_summary.get("effect_evaluation", "——"),
        "improvement_suggestions": event_summary.get("improvement_suggestions", "——"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "location_area": area_map.get(incident.get("location_area"), "——"),
        "fod_type": fod_type_map.get(incident.get("fod_type"), incident.get("fod_type", "——") or "——"),
        "presence": presence_map.get(incident.get("presence"), "——"),
        "fod_size": size_map.get(incident.get("fod_size"), incident.get("fod_size", "——") or "——"),
        "ops_impact": incident.get("ops_impact", "——") or "——",
        "related_event": incident.get("related_event", "——") or "——",
        "bird_phase": phase_map.get(incident.get("phase"), incident.get("phase", "——") or "——"),
        "bird_evidence": evidence_map.get(incident.get("evidence"), incident.get("evidence", "——") or "——"),
        "bird_info": bird_info_map.get(incident.get("bird_info"), incident.get("bird_info", "——") or "——"),
        "bird_ops_impact": bird_ops_impact_map.get(
            incident.get("ops_impact"),
            incident.get("ops_impact", "——") or "——",
        ),
        # 鸟击等场景特有字段，默认占位
        "event_type": incident.get("event_type", "鸟击（确认/疑似）") or "鸟击（确认/疑似）",
        "tail_no": incident.get("tail_no", "——") or "——",
        "affected_part": incident.get("affected_part", "——") or "——",
        "current_status": incident.get("current_status", "——") or "——",
        "crew_request": incident.get("crew_request", "——") or "——",
        "suspend_resources": "是" if incident.get("suspend_resources") else "否",
        "followup_required": "是" if incident.get("followup_required") else "否",
    }


def output_generator_node(state: AgentState) -> Dict[str, Any]:
    """
    输出生成节点

    调用 LLM 基于 SKILL 规范和知识库生成结构化的机坪特情处置检查单报告
    """
    scenario_type = state.get("scenario_type", "oil_spill")
    incident = state.get("incident", {})
    risk = state.get("risk_assessment", {})
    spatial = state.get("spatial_analysis", {})
    actions = state.get("actions_taken", [])
    knowledge = state.get("retrieved_knowledge", {})

    # 基础数据准备
    coordination_units = generate_coordination_units(state)
    notifications_summary = generate_notifications_summary(state)
    recommendations = generate_recommendations(state)

    # LLM 生成摘要槽位（失败自动回退）
    notifications = state.get("notifications_sent", [])
    event_summary = _generate_event_summary_with_llm(
        incident=incident,
        risk=risk,
        spatial=spatial,
        notifications=notifications,
        recommendations=recommendations,
        scenario_type=scenario_type,
        knowledge=knowledge,
    )

    # 使用模板渲染最终 Markdown
    render_context = _build_render_context(
        state=state,
        coordination_units=coordination_units,
        event_summary=event_summary,
    )
    scenario = ScenarioRegistry.get(scenario_type)
    final_answer = render_report(
        scenario_type,
        render_context,
        template_path=scenario.template_path if scenario else None,
    )

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
        "recommendations": recommendations,
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
    """兼容保留：复用 Jinja 模板渲染路径。"""
    incident = state.get("incident", {})
    risk = state.get("risk_assessment", {})
    spatial = state.get("spatial_analysis", {})
    knowledge = state.get("retrieved_knowledge", {})
    notifications = state.get("notifications_sent", [])
    recommendations = generate_recommendations(state)
    scenario_type = state.get("scenario_type", "oil_spill")

    event_summary = _generate_event_summary_with_llm(
        incident=incident,
        risk=risk,
        spatial=spatial,
        notifications=notifications,
        recommendations=recommendations,
        scenario_type=scenario_type,
        knowledge=knowledge,
    )
    render_context = _build_render_context(
        state=state,
        coordination_units=coordination_units,
        event_summary=event_summary,
    )
    scenario = ScenarioRegistry.get(scenario_type)
    return render_report(
        scenario_type,
        render_context,
        template_path=scenario.template_path if scenario else None,
    )
