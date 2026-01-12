"""
鸟击风险评估工具 (BSRC 规则引擎)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tools.base import BaseTool


BSRC_PATH = Path(__file__).resolve().parents[2] / "BSRC.json"


def _load_bsrc() -> Dict[str, Any]:
    if not BSRC_PATH.exists():
        return {}
    with BSRC_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


_BSRC = _load_bsrc()


RISK_ORDER = {"R1": 1, "R2": 2, "R3": 3, "R4": 4}


def _pick_higher_risk(a: str, b: str) -> str:
    return a if RISK_ORDER.get(a, 0) >= RISK_ORDER.get(b, 0) else b


def _normalize_phase(incident: Dict[str, Any]) -> str:
    raw = str(incident.get("phase") or "").upper()
    if raw in {
        "PUSHBACK", "TAXI", "TAKEOFF_ROLL", "INITIAL_CLIMB", "CRUISE",
        "DESCENT", "APPROACH", "LANDING_ROLL", "ON_STAND", "UNKNOWN",
    }:
        return raw

    position = str(incident.get("position") or "")
    flight_type = str(incident.get("flight_type") or "").upper()

    if "机位" in position:
        return "ON_STAND"
    if "滑行道" in position:
        return "TAXI"
    if "跑道" in position:
        if flight_type == "A":
            return "LANDING_ROLL"
        if flight_type == "D":
            return "TAKEOFF_ROLL"
        return "TAKEOFF_ROLL"

    cn_phase_map = {
        "推出": "PUSHBACK",
        "滑行": "TAXI",
        "起飞": "TAKEOFF_ROLL",
        "爬升": "INITIAL_CLIMB",
        "巡航": "CRUISE",
        "下降": "DESCENT",
        "进近": "APPROACH",
        "落地": "LANDING_ROLL",
        "停机位": "ON_STAND",
    }
    for key, value in cn_phase_map.items():
        if key in raw:
            return value

    return "UNKNOWN"


def _normalize_impact_area(incident: Dict[str, Any]) -> str:
    part = str(incident.get("affected_part") or "")
    if any(key in part for key in ["发动机", "左发", "右发", "双发"]):
        return "ENGINE"
    if "风挡" in part or "挡风玻璃" in part:
        return "WINDSHIELD"
    if "雷达罩" in part:
        return "RADOME"
    if "机翼" in part or "翼尖" in part or "翼根" in part:
        return "WING_LEADING_EDGE"
    if "机身" in part or "机腹" in part:
        return "FUSELAGE"
    if "起落架" in part or "落架" in part:
        return "LANDING_GEAR"
    return "UNKNOWN"


def _normalize_evidence(incident: Dict[str, Any]) -> str:
    raw = str(incident.get("evidence") or "").upper()
    if raw in {
        "CONFIRMED_STRIKE_WITH_REMAINS",
        "SYSTEM_WARNING",
        "ABNORMAL_NOISE_VIBRATION",
        "SUSPECTED_ONLY",
        "NO_ABNORMALITY",
    }:
        return raw

    current_status = str(incident.get("current_status") or "")
    event_type = str(incident.get("event_type") or "")

    if "火警" in current_status or "异常" in current_status:
        return "SYSTEM_WARNING"
    if "确认" in event_type:
        return "CONFIRMED_STRIKE_WITH_REMAINS"
    if "疑似" in event_type:
        return "SUSPECTED_ONLY"
    return "NO_ABNORMALITY"


def _normalize_bird_info(incident: Dict[str, Any]) -> str:
    raw = str(incident.get("bird_info") or "").upper()
    if raw in {"LARGE_BIRD", "FLOCK", "MEDIUM_SMALL_SINGLE", "UNKNOWN"}:
        return raw

    if "群" in raw or "群" in str(incident.get("bird_info") or ""):
        return "FLOCK"
    if "大" in raw or "大型" in str(incident.get("bird_info") or ""):
        return "LARGE_BIRD"
    if "小" in raw or "中" in raw:
        return "MEDIUM_SMALL_SINGLE"
    return "UNKNOWN"


def _normalize_ops_impact(incident: Dict[str, Any]) -> str:
    raw = str(incident.get("ops_impact") or "").upper()
    if raw in {
        "RTO_OR_RTB",
        "BLOCKING_RUNWAY_OR_TAXIWAY",
        "REQUEST_MAINT_CHECK",
        "NO_OPS_IMPACT",
        "UNKNOWN",
    }:
        return raw

    current_status = str(incident.get("current_status") or "")
    crew_request = str(incident.get("crew_request") or "")
    position = str(incident.get("position") or "")

    if "返航" in current_status or "备降" in current_status or "返航" in crew_request or "备降" in crew_request:
        return "RTO_OR_RTB"
    if "跑道" in position or "滑行道" in position:
        return "BLOCKING_RUNWAY_OR_TAXIWAY"
    if "检查" in current_status or "检查" in crew_request or "待检查" in current_status:
        return "REQUEST_MAINT_CHECK"
    if "正常" in current_status:
        return "NO_OPS_IMPACT"
    return "UNKNOWN"


def _evaluate_clause(data: Dict[str, Any], clause: Dict[str, Any]) -> bool:
    if "eq" in clause:
        key, value = clause["eq"]
        return data.get(key) == value
    if "in" in clause:
        key, values = clause["in"]
        return data.get(key) in values
    return False


def _evaluate_condition(data: Dict[str, Any], condition: Dict[str, Any]) -> bool:
    if "all" in condition:
        return all(_evaluate_clause(data, c) for c in condition["all"])
    if "any" in condition:
        return any(_evaluate_clause(data, c) for c in condition["any"])
    return False


def _weighted_score(
    data: Dict[str, Any],
    weights: Dict[str, float],
    lookup_tables: Dict[str, Dict[str, int]],
    max_score: int,
) -> float:
    max_by_dim: Dict[str, int] = {}
    for key, table in lookup_tables.items():
        max_by_dim[key] = max(table.values()) if table else 0

    def score_for(table_key: str, value_key: str) -> float:
        points = lookup_tables.get(table_key, {}).get(data.get(value_key, "UNKNOWN"), 0)
        return weights.get(value_key, 1.0) * points

    raw = (
        score_for("phase_points", "phase")
        + score_for("impact_area_points", "impact_area")
        + score_for("evidence_points", "evidence")
        + score_for("bird_info_points", "bird_info")
        + score_for("ops_impact_points", "ops_impact")
    )

    max_raw = (
        weights.get("phase", 1.0) * max_by_dim.get("phase_points", 0)
        + weights.get("impact_area", 1.0) * max_by_dim.get("impact_area_points", 0)
        + weights.get("evidence", 1.0) * max_by_dim.get("evidence_points", 0)
        + weights.get("bird_info", 1.0) * max_by_dim.get("bird_info_points", 0)
        + weights.get("ops_impact", 1.0) * max_by_dim.get("ops_impact_points", 0)
    )
    if max_raw <= 0:
        return 0.0
    return round(raw / max_raw * max_score, 2)


def _map_risk_level(score: float, mapping: List[Dict[str, Any]]) -> str:
    for item in mapping:
        if item["min"] <= score <= item["max"]:
            return item["risk_level"]
    return "R2"


class AssessBirdStrikeRiskTool(BaseTool):
    """鸟击风险评估工具（BSRC 规则引擎）"""

    name = "assess_bird_strike_risk"
    description = """基于 BSRC 规则评估鸟击风险等级。

输入参数（可选）:
- phase: 飞行阶段（TAKEOFF_ROLL/APPROACH/...）
- impact_area: 撞击部位（ENGINE/WINDSHIELD/...）
- evidence: 迹象强度（CONFIRMED_STRIKE_WITH_REMAINS/...）
- bird_info: 鸟类信息（LARGE_BIRD/FLOCK/...）
- ops_impact: 运行影响（RTO_OR_RTB/...）

返回信息:
- 风险等级 (R1-R4)
- 风险分数
- 规则解释与管控建议"""

    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        if not _BSRC:
            return {"observation": "未找到 BSRC.json，无法评估鸟击风险"}

        incident = dict(state.get("incident", {}))
        incident.update(inputs)

        data = {
            "phase": _normalize_phase(incident),
            "impact_area": _normalize_impact_area(incident),
            "evidence": _normalize_evidence(incident),
            "bird_info": _normalize_bird_info(incident),
            "ops_impact": _normalize_ops_impact(incident),
        }

        scoring = _BSRC.get("scoring_model", {})
        lookup_tables = _BSRC.get("lookup_tables", {})
        weights = {d["name"]: d.get("weight", 1.0) for d in scoring.get("dimensions", [])}
        max_score = scoring.get("max_score", 100)

        score = _weighted_score(data, weights, lookup_tables, max_score)

        explanations: List[str] = []
        risk_floor = "NONE"
        risk_boost = 0

        for rule in _BSRC.get("rules", []):
            when = rule.get("when", {})
            if _evaluate_condition(data, when):
                then = rule.get("then", {})
                if then.get("risk_floor"):
                    risk_floor = _pick_higher_risk(risk_floor, then["risk_floor"])
                if then.get("risk_boost"):
                    risk_boost += int(then["risk_boost"])
                explain = then.get("explain")
                if explain:
                    explanations.append(explain)

        score = min(max_score, max(0.0, score + risk_boost))

        mapping = _BSRC.get("risk_mapping", {}).get("by_score", [])
        level = _map_risk_level(score, mapping)
        if _BSRC.get("risk_mapping", {}).get("apply_floor_override", False) and risk_floor != "NONE":
            level = _pick_higher_risk(level, risk_floor)

        guardrails = _BSRC.get("guardrails", {}).get("by_risk_level", {}).get(level, {})

        observation = (
            f"鸟击风险评估完成: 等级={level}, 分数={score}, "
            f"阶段={data['phase']}, 部位={data['impact_area']}, 迹象={data['evidence']}"
        )

        return {
            "observation": observation,
            "risk_assessment": {
                "level": level,
                "score": score,
                "inputs": data,
                "risk_floor_applied": risk_floor if risk_floor != "NONE" else "NONE",
                "explanations": explanations,
                "guardrails": guardrails,
            },
            "mandatory_actions_done": {
                "risk_assessed": True,
            },
        }
