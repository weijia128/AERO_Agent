from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from agent.llm_guard import invoke_llm
from agent.nodes.output_generator import generate_recommendations
from scenarios.base import ScenarioRegistry

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "external_recommendation_prompt.txt"

FLUID_LABELS = {
    "FUEL": "燃油",
    "HYDRAULIC": "液压油",
    "OIL": "滑油",
    "UNKNOWN": "不明油液",
}

ENGINE_LABELS = {
    "RUNNING": "运转中",
    "STOPPED": "已关闭",
    "APU": "仅APU运行",
}

LEAK_SIZE_LABELS = {
    "SMALL": "小面积",
    "MEDIUM": "中等面积",
    "LARGE": "大面积",
}


def build_external_recommendation(state: Dict[str, Any]) -> str:
    scenario_type = state.get("scenario_type", "") or "oil_spill"
    incident = state.get("incident", {}) or {}
    risk = state.get("risk_assessment", {}) or {}
    checklist = state.get("checklist", {}) or {}

    missing_fields = _get_missing_fields(checklist, scenario_type)
    incident_details = _format_incident_details(incident)
    checklist_summary = _format_checklist_summary(checklist)
    immediate_actions = _get_immediate_actions(scenario_type, risk.get("level"))

    prompt = _render_prompt(
        scenario_type=scenario_type,
        risk_level=risk.get("level", "未评估"),
        risk_score=risk.get("score", "—"),
        incident_details=incident_details,
        checklist_summary=checklist_summary,
        missing_fields="、".join(missing_fields) if missing_fields else "无",
        immediate_actions="；".join(immediate_actions) if immediate_actions else "无",
    )

    if prompt:
        try:
            response = invoke_llm(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            content = _clean_llm_output(content)
            if content:
                return content
        except Exception:
            pass

    return _build_fallback_recommendation(state, missing_fields, immediate_actions)


def _render_prompt(**kwargs: Any) -> str:
    try:
        template = PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    return template.format(**kwargs)


def _get_missing_fields(checklist: Dict[str, Any], scenario_type: str) -> List[str]:
    scenario = ScenarioRegistry.get(scenario_type)
    if scenario:
        missing = []
        for field in scenario.p1_fields:
            key = field.get("key")
            if not key:
                continue
            if not checklist.get(key, False):
                missing.append(field.get("label") or key)
        return missing
    return [key for key, done in checklist.items() if not done]


def _format_incident_details(incident: Dict[str, Any]) -> str:
    mapping = {
        "flight_no": "航班号",
        "position_display": "位置",
        "position": "位置",
        "fluid_type": "油液类型",
        "engine_status": "发动机状态",
        "continuous": "持续泄漏",
        "leak_size": "泄漏面积",
        "reported_by": "报告人",
    }

    lines: List[str] = []
    for key, label in mapping.items():
        value = incident.get(key)
        if value in (None, ""):
            continue
        if key == "fluid_type":
            value = FLUID_LABELS.get(str(value), value)
        elif key == "engine_status":
            value = ENGINE_LABELS.get(str(value), value)
        elif key == "leak_size":
            value = LEAK_SIZE_LABELS.get(str(value), value)
        elif key == "continuous":
            value = "是" if bool(value) else "否"
        lines.append(f"- {label}: {value}")

    return "\n".join(lines) if lines else "- 无"


def _format_checklist_summary(checklist: Dict[str, Any]) -> str:
    if not checklist:
        return "无"
    done = [key for key, value in checklist.items() if value]
    pending = [key for key, value in checklist.items() if not value]
    return f"已收集: {', '.join(done) if done else '无'}；待补充: {', '.join(pending) if pending else '无'}"


def _get_immediate_actions(scenario_type: str, risk_level: Any) -> List[str]:
    scenario = ScenarioRegistry.get(scenario_type)
    if not scenario:
        return []
    immediate_actions = scenario.config.get("immediate_actions", {})
    if not risk_level:
        return []
    return list(immediate_actions.get(str(risk_level), []) or [])


def _build_fallback_recommendation(
    state: Dict[str, Any],
    missing_fields: List[str],
    immediate_actions: List[str],
) -> str:
    recommendations: List[str] = []

    if missing_fields:
        recommendations.append(f"先补充关键信息：{', '.join(missing_fields)}")

    recommendations.extend(immediate_actions)

    if not immediate_actions:
        recommendations.extend(generate_recommendations(state))

    if not recommendations:
        recommendations.append("请按机场应急预案处置，并保持与相关单位联络。")

    return _format_numbered_list(recommendations)


def _format_numbered_list(items: List[str]) -> str:
    cleaned = [item.strip() for item in items if item and item.strip()]
    return "\n".join(f"{idx + 1}. {item}" for idx, item in enumerate(cleaned))


def _clean_llm_output(text: str) -> str:
    content = text.strip()
    if not content:
        return ""
    if content.startswith("```"):
        content = content.strip("`")
    return content.strip()
