"""
对话策略层 - 根据语义验证结果生成追问
"""
from typing import Dict, Any, List

from config.llm_config import get_llm_client
from config.airline_codes import format_callsign_display
from scenarios.base import ScenarioRegistry
from tools.information.smart_ask import build_combined_question, group_missing_fields


def generate_next_question(state: Dict[str, Any], semantic_validation: Dict[str, Any]) -> str:
    """生成下一条追问"""
    incident = state.get("incident", {})
    scenario_type = state.get("scenario_type", "oil_spill")
    scenario = ScenarioRegistry.get(scenario_type)

    missing_fields = semantic_validation.get("missing_fields", []) or []
    low_confidence = semantic_validation.get("low_confidence_fields", []) or []
    semantic_issues = semantic_validation.get("semantic_issues", []) or []

    flight_no = incident.get("flight_no_display") or incident.get("flight_no") or ""
    callsign = format_callsign_display(flight_no) if flight_no else ""

    field_names = scenario.field_names if scenario else {}
    ask_prompts = scenario.prompt_config.get("ask_prompts", {}) if scenario else {}

    def format_field(field: str) -> str:
        return field_names.get(field, field)

    def format_low_conf() -> List[str]:
        formatted = []
        for item in low_confidence:
            field = item.get("field", "")
            value = item.get("value", "")
            confidence = item.get("confidence", 0)
            formatted.append(f"{format_field(field)}={value} (置信度{confidence:.2f})")
        return formatted

    constraint_lines = []
    if semantic_issues:
        constraint_lines.append("需要优先澄清的问题:")
        constraint_lines.extend([f"- {issue}" for issue in semantic_issues])
    if missing_fields:
        constraint_lines.append("缺失字段:")
        constraint_lines.extend([f"- {format_field(field)}" for field in missing_fields])
    if low_confidence:
        constraint_lines.append("低置信度字段:")
        constraint_lines.extend([f"- {item}" for item in format_low_conf()])

    history = state.get("messages", [])
    history_text = "\n".join(
        f"{'用户' if m.get('role') == 'user' else '管制'}: {m.get('content', '')}"
        for m in history[-4:]
    )

    prompt = f"""你是机场机坪应急响应的对话策略模块。

任务：根据约束信息生成一条专业且自然的追问，最多询问2个信息点。
优先级：先澄清语义矛盾，再补全缺失字段，再确认低置信度字段。
要求：只输出问题文本，不要解释。
称呼：若有航班号必须在问题开头称呼（如“{callsign}，...”）。

约束信息:
{chr(10).join(constraint_lines)}

对话历史（最近2轮）:
{history_text}
"""

    try:
        llm = get_llm_client()
        response = llm.invoke(prompt)
        question = response.content.strip() if hasattr(response, "content") else str(response).strip()
        if question:
            return question
    except Exception:
        pass

    # 低置信度优先确认（没有矛盾也没有缺失时）
    if not semantic_issues and not missing_fields and low_confidence:
        item = low_confidence[0]
        field = item.get("field", "")
        value = item.get("value", "")
        field_name = format_field(field)
        confirm_text = f"请确认{field_name}是否为“{value}”？"
        if callsign and not confirm_text.startswith(callsign):
            confirm_text = f"{callsign}，{confirm_text}"
        return confirm_text

    if semantic_issues:
        issue_text = semantic_issues[0]
        question = f"请确认：{issue_text}"
    else:
        fields_for_question = missing_fields or [item.get("field") for item in low_confidence if item.get("field")]
        if fields_for_question:
            groups = group_missing_fields(fields_for_question)
            question = build_combined_question(groups[0] if groups else fields_for_question, flight_no)
        else:
            question = "请补充当前事件的关键信息。"

    if callsign and not question.startswith(callsign):
        question = f"{callsign}，{question}"

    if ask_prompts and missing_fields:
        prompt_key = missing_fields[0]
        question = ask_prompts.get(prompt_key, question)
        if callsign and not question.startswith(callsign):
            question = f"{callsign}，{question}"

    return question
