"""
语义理解层 - 使用 Function Calling 生成结构化信息
"""
from typing import Dict, Any, List, Tuple

from config.llm_config import get_llm_client


DEFAULT_CONFIDENCE_THRESHOLDS = {
    "flight_no": 0.75,
    "position": 0.8,
    "fluid_type": 0.8,
    "engine_status": 0.8,
    "continuous": 0.7,
    "leak_size": 0.6,
    "reported_by": 0.6,
}

UNDERSTAND_INCIDENT_SCHEMA = {
    "name": "understand_incident_report",
    "description": "理解用户对机场机坪应急事件的描述，提取结构化信息并给出置信度",
    "parameters": {
        "type": "object",
        "properties": {
            "conversation_summary": {
                "type": "string",
                "description": "用一句话总结本轮用户输入",
            },
            "extracted_facts": {
                "type": "object",
                "description": "提取的结构化事实",
                "properties": {
                    "flight_no": {
                        "type": "string",
                        "description": "航班号，如 CA1234 或 MU5678",
                    },
                    "flight_no_display": {
                        "type": "string",
                        "description": "航班号原始显示，如 川航3349",
                    },
                    "position": {
                        "type": "string",
                        "description": "事发位置，如 501、A3、跑道01L、滑行道19",
                    },
                    "fluid_type": {
                        "type": "string",
                        "enum": ["FUEL", "HYDRAULIC", "OIL", "UNKNOWN"],
                        "description": "油液类型",
                    },
                    "engine_status": {
                        "type": "string",
                        "enum": ["RUNNING", "STOPPED", "UNKNOWN"],
                        "description": "发动机状态",
                    },
                    "continuous": {
                        "type": "boolean",
                        "description": "是否持续泄漏",
                    },
                    "leak_size": {
                        "type": "string",
                        "enum": ["LARGE", "MEDIUM", "SMALL", "UNKNOWN"],
                        "description": "泄漏面积",
                    },
                    "reported_by": {
                        "type": "string",
                        "description": "报告人姓名或工号",
                    },
                },
            },
            "confidence_scores": {
                "type": "object",
                "description": "字段置信度（0-1）",
                "properties": {
                    "flight_no": {"type": "number"},
                    "flight_no_display": {"type": "number"},
                    "position": {"type": "number"},
                    "fluid_type": {"type": "number"},
                    "engine_status": {"type": "number"},
                    "continuous": {"type": "number"},
                    "leak_size": {"type": "number"},
                    "reported_by": {"type": "number"},
                },
            },
            "semantic_issues": {
                "type": "array",
                "items": {"type": "string"},
                "description": "检测到的语义矛盾或不合理之处",
            },
        },
        "required": ["conversation_summary", "extracted_facts", "confidence_scores"],
    },
}

SEMANTIC_UNDERSTANDING_SYSTEM_PROMPT = """你是机场应急响应系统的语义理解模块。

任务：理解用户的自然语言输入，提取结构化事实，并给出置信度。

要求：
1. 只提取明确或高度确信的信息，不要猜测。
2. 若用户表达不清楚或未知，请使用 UNKNOWN（例如油液类型不明）。
3. 用户可能一次性提供多条信息，请全部提取。
4. 给每个字段打置信度（0-1）。
5. 如发现矛盾或不合理之处，写入 semantic_issues。
"""


def understand_conversation(
    current_message: str,
    conversation_history: List[Dict[str, Any]],
    known_facts: Dict[str, Any],
    fsm_state: str,
) -> Dict[str, Any]:
    """使用 LLM Function Calling 理解对话内容并提取结构化信息"""
    llm = get_llm_client()

    context = _build_context_prompt(conversation_history, known_facts, fsm_state)
    messages = [
        {"role": "system", "content": SEMANTIC_UNDERSTANDING_SYSTEM_PROMPT},
        {"role": "system", "content": context},
        {"role": "user", "content": current_message},
    ]

    try:
        response = llm.invoke(
            messages,
            functions=[UNDERSTAND_INCIDENT_SCHEMA],
            function_call={"name": "understand_incident_report"},
        )
        understanding = _parse_function_call_response(response)
        return _post_process_understanding(understanding)
    except Exception as exc:
        return {
            "conversation_summary": "语义理解失败",
            "extracted_facts": {},
            "confidence_scores": {},
            "semantic_issues": [f"语义理解失败: {exc}"],
        }


def split_by_confidence(
    extracted_facts: Dict[str, Any],
    confidence_scores: Dict[str, float],
    thresholds: Dict[str, float] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """根据置信度阈值划分高置信度与低置信度字段"""
    thresholds = thresholds or DEFAULT_CONFIDENCE_THRESHOLDS
    accepted: Dict[str, Any] = {}
    low_confidence: List[Dict[str, Any]] = []

    for field, value in extracted_facts.items():
        if value is None:
            continue
        confidence = confidence_scores.get(field, 1.0)
        threshold = thresholds.get(field, thresholds.get("default", 0.7))
        if confidence >= threshold:
            accepted[field] = value
        else:
            low_confidence.append({
                "field": field,
                "value": value,
                "confidence": confidence,
            })

    return accepted, low_confidence


def _build_context_prompt(
    history: List[Dict[str, Any]],
    known: Dict[str, Any],
    fsm_state: str,
) -> str:
    """构建上下文提示"""
    parts = [f"## 当前 FSM 状态\n{fsm_state}"]

    if known:
        known_lines = [f"- {k}: {v}" for k, v in known.items() if v not in [None, ""]]
        if known_lines:
            parts.append("## 已知信息")
            parts.extend(known_lines)

    if history:
        parts.append("## 对话历史（最近3轮）")
        for msg in history[-6:]:
            role = "用户" if msg.get("role") == "user" else "系统"
            parts.append(f"{role}: {msg.get('content', '')}")

    return "\n".join(parts)


def _parse_function_call_response(response: Any) -> Dict[str, Any]:
    """解析 Function Calling 响应"""
    import json

    function_call = {}
    if hasattr(response, "additional_kwargs"):
        function_call = response.additional_kwargs.get("function_call", {})
        if not function_call and response.additional_kwargs.get("tool_calls"):
            tool_calls = response.additional_kwargs.get("tool_calls", [])
            if tool_calls:
                function_call = tool_calls[0].get("function", {})
    elif hasattr(response, "function_call"):
        function_call = response.function_call

    arguments = function_call.get("arguments", "{}")
    try:
        return json.loads(arguments)
    except json.JSONDecodeError:
        return {
            "conversation_summary": "JSON 解析失败",
            "extracted_facts": {},
            "confidence_scores": {},
            "semantic_issues": ["Function Calling 返回无法解析"],
        }


def _post_process_understanding(understanding: Dict[str, Any]) -> Dict[str, Any]:
    """后处理：补全字段并归一化枚举值"""
    understanding.setdefault("conversation_summary", "")
    understanding.setdefault("extracted_facts", {})
    understanding.setdefault("confidence_scores", {})
    understanding.setdefault("semantic_issues", [])

    extracted = understanding.get("extracted_facts", {})
    normalized = _normalize_extracted_facts(extracted)
    understanding["extracted_facts"] = normalized

    return understanding


def _normalize_extracted_facts(extracted: Dict[str, Any]) -> Dict[str, Any]:
    """归一化枚举字段"""
    normalized = dict(extracted)

    def _normalize_enum(value: Any, mapping: Dict[str, str], allowed: List[str]) -> Any:
        if value is None:
            return None
        value_str = str(value).strip().upper()
        if value_str in allowed:
            return value_str
        return mapping.get(value_str, value)

    normalized["fluid_type"] = _normalize_enum(
        normalized.get("fluid_type"),
        {"燃油": "FUEL", "航油": "FUEL", "液压油": "HYDRAULIC", "滑油": "OIL"},
        ["FUEL", "HYDRAULIC", "OIL", "UNKNOWN"],
    )
    normalized["engine_status"] = _normalize_enum(
        normalized.get("engine_status"),
        {"运转": "RUNNING", "运行": "RUNNING", "关闭": "STOPPED", "关车": "STOPPED"},
        ["RUNNING", "STOPPED", "UNKNOWN"],
    )
    normalized["leak_size"] = _normalize_enum(
        normalized.get("leak_size"),
        {"大": "LARGE", "中": "MEDIUM", "小": "SMALL"},
        ["LARGE", "MEDIUM", "SMALL", "UNKNOWN"],
    )

    return normalized
