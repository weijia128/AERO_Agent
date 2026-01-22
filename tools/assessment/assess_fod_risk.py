"""
FOD 风险评估工具（基于 fod_rule.json）
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from tools.base import BaseTool


FOD_RULE_PATH = Path(__file__).resolve().parents[2] / "fod_rule.json"


def _load_rules() -> Dict[str, Any]:
    if not FOD_RULE_PATH.exists():
        return {}
    with FOD_RULE_PATH.open("r", encoding="utf-8") as f:
        return cast(Dict[str, Any], json.load(f))


_FOD_RULES = _load_rules()


def _get_path_value(data: Dict[str, Any], path: str) -> Any:
    if not path:
        return None
    if path in data:
        return data.get(path)
    current: Any = data
    for key in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _exists(data: Dict[str, Any], path: str) -> bool:
    value = _get_path_value(data, path)
    return value not in [None, "", [], {}]


def _eval_operand(data: Dict[str, Any], operand: Any) -> Any:
    if isinstance(operand, (int, float, bool)):
        return operand
    if isinstance(operand, str):
        if operand.startswith("abs(") and operand.endswith(")"):
            inner = operand[4:-1]
            value = _get_path_value(data, inner)
            try:
                return abs(float(value))
            except (TypeError, ValueError):
                return None
        return _get_path_value(data, operand) if "." in operand else operand
    return operand


def _evaluate_clause(data: Dict[str, Any], clause: Dict[str, Any]) -> bool:
    if "eq" in clause:
        key, value = clause["eq"]
        return bool(_get_path_value(data, key) == value)
    if "exists" in clause:
        return _exists(data, clause["exists"])
    if "lte" in clause:
        left, right = clause["lte"]
        left_val = _eval_operand(data, left)
        right_val = _eval_operand(data, right)
        if left_val is None or right_val is None:
            return False
        return float(left_val) <= float(right_val)
    if "missing_or_empty" in clause:
        field = clause["missing_or_empty"]
        value = _get_path_value(data, field)
        return value is None or value == "" or value == [] or value == {}
    if "not_missing_or_empty" in clause:
        field = clause["not_missing_or_empty"]
        value = _get_path_value(data, field)
        return value is not None and value != "" and value != [] and value != {}
    return False


def _evaluate_condition(data: Dict[str, Any], condition: Dict[str, Any]) -> bool:
    if "all" in condition:
        clauses = cast(List[Dict[str, Any]], condition["all"])
        return all(_evaluate_clause(data, c) for c in clauses)
    if "any" in condition:
        clauses = cast(List[Dict[str, Any]], condition["any"])
        return any(_evaluate_clause(data, c) for c in clauses)
    return False


def _score_from_map(value: Optional[str], score_map: Dict[str, int]) -> int:
    if not score_map:
        return 0
    key = value or "UNKNOWN"
    return int(score_map.get(key, score_map.get("UNKNOWN", 0)))


def _map_risk_level(score: float, thresholds: List[Dict[str, Any]]) -> str:
    for item in thresholds:
        if score >= float(item.get("gte", 0)):
            return str(item.get("level", "R1"))
    return "R1"


class AssessFodRiskTool(BaseTool):
    """FOD 风险评估工具（按 fod_rule.json 计算）"""

    name = "assess_fod_risk"
    description = """基于 FOD 规则评估风险等级。

输入参数（可选）:
- location_area: 位置类别（RUNWAY/TAXIWAY/APRON/...）
- position: 具体位置
- fod_type: FOD 种类（METAL/PLASTIC_RUBBER/STONE_GRAVEL/LIQUID/UNKNOWN）
- presence: 是否仍在道面（ON_SURFACE/REMOVED/MOVING_BLOWING/UNKNOWN）
- report_time: 汇报时间
- fod_size: 尺寸（SMALL/MEDIUM/LARGE/UNKNOWN）

返回信息:
- 风险等级 (R1-R4)
- 风险分数
- 评估解释与处置建议"""

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        if not _FOD_RULES:
            return {
                "observation": "未找到 fod_rule.json，无法评估 FOD 风险",
                "success": False
            }

        incident = dict(state.get("incident", {}))
        incident.update(inputs)

        data: Dict[str, Any] = {
            "event_type": "FOD",
            "location_area": incident.get("location_area"),
            "position": incident.get("position"),
            "fod_type": incident.get("fod_type"),
            "presence": incident.get("presence"),
            "report_time": incident.get("report_time"),
            "fod_size": incident.get("fod_size"),
            "impact_note": incident.get("impact_note"),
            "location": {
                "area_type": incident.get("location_area"),
                "identifier": incident.get("position"),
                "segment": incident.get("location_segment"),
                "centerline_offset_m": incident.get("centerline_offset_m"),
            },
        }

        required_fields: List[str] = []
        for rule in _FOD_RULES.get("rules", []):
            if rule.get("id") == "fod.validate.must_fields":
                required_fields = rule.get("then", {}).get("required_fields", [])
                break

        missing = [field for field in required_fields if not _exists(data, field)]
        if missing:
            return {
                "observation": f"FOD 风险评估缺少关键字段: {missing}",
                "success": False,
            }

        scoring = _FOD_RULES.get("config", {}).get("scoring", {})
        weights = scoring.get("weights", {})
        location_map = scoring.get("location_score_map", {})
        type_map = scoring.get("type_score_map", {})
        size_map = scoring.get("size_score_map", {})

        location_base = _score_from_map(data.get("location_area"), location_map)
        type_base = _score_from_map(data.get("fod_type"), type_map)
        size_base = _score_from_map(data.get("fod_size"), size_map)

        modifier_sum = 0
        for modifier in scoring.get("location_modifiers", []):
            when = modifier.get("when", {})
            if when and _evaluate_condition(data, when):
                modifier_sum += int(modifier.get("add", 0))

        location_score = min(120, max(0, location_base + modifier_sum))
        risk_score = (
            location_score * float(weights.get("location", 0.5))
            + type_base * float(weights.get("type", 0.3))
            + size_base * float(weights.get("size", 0.2))
        )

        explanations = [
            f"location={data.get('location_area')}({location_score})",
            f"type={data.get('fod_type')}({type_base})",
            f"size={data.get('fod_size')}({size_base})",
        ]

        if data.get("presence") == "REMOVED":
            risk_score *= 0.6
            explanations.append("presence=REMOVED, score*0.6")
        elif data.get("presence") == "MOVING_BLOWING":
            risk_score += 10
            explanations.append("presence=MOVING_BLOWING, +10")

        risk_score = round(max(0.0, risk_score), 2)

        level = _map_risk_level(risk_score, scoring.get("risk_level_thresholds", []))

        recommendations = []
        for rule in _FOD_RULES.get("rules", []):
            if rule.get("id") == "fod.action.recommend":
                by_level = rule.get("then", {}).get("by_level", {})
                recommendations = by_level.get(level, {}).get("recommendations", [])
                break

        observation = f"FOD 风险评估完成: 等级={level}, 分数={risk_score}"

        return {
            "observation": observation,
            "risk_assessment": {
                "level": level,
                "score": risk_score,
                "inputs": {
                    "location_area": data.get("location_area"),
                    "position": data.get("position"),
                    "fod_type": data.get("fod_type"),
                    "presence": data.get("presence"),
                    "fod_size": data.get("fod_size"),
                },
                "explanations": explanations,
                "recommendations": recommendations,
            },
            "mandatory_actions_done": {
                "risk_assessed": True,
            },
        }
