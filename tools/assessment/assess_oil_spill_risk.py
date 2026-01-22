"""
风险评估工具 (规则引擎)

对应文档方案的 P1_RISK_ASSESS
确定性计算，不使用 LLM
"""
from typing import Dict, Any, List, Tuple, Optional
from tools.base import BaseTool
from scenarios.base import ScenarioRegistry
from agent.state import RiskLevel, normalize_risk_level


# 风险评估规则矩阵
RISK_RULES = [
    # (条件, 风险等级, 分数, 说明)
    {
        "conditions": {"fluid_type": "FUEL", "continuous": True, "engine_status": "RUNNING"},
        "level": "R4",
        "score": 95,
        "description": "航空燃油+持续泄漏+发动机运转=极高火灾风险(易燃易爆)",
    },
    {
        "conditions": {"fluid_type": "FUEL", "engine_status": "RUNNING"},
        "level": "R4",
        "score": 90,
        "description": "航空燃油+发动机运转=高火灾风险(禁止任何火花)",
    },
    {
        "conditions": {"fluid_type": "FUEL", "continuous": True},
        "level": "R4",
        "score": 85,
        "description": "航空燃油+持续泄漏=高风险",
    },
    {
        "conditions": {"fluid_type": "FUEL", "leak_size": "LARGE"},
        "level": "R4",
        "score": 80,
        "description": "大面积航空燃油泄漏=高风险(泡沫覆盖)",
    },
    {
        "conditions": {"fluid_type": "FUEL"},
        "level": "R3",
        "score": 60,
        "description": "航空燃油泄漏=中等风险(专业吸油材料处置)",
    },
    {
        "conditions": {"fluid_type": "HYDRAULIC", "continuous": True, "engine_status": "RUNNING"},
        "level": "R3",
        "score": 70,
        "description": "液压油+发动机运转+持续泄漏=中高风险(高压喷射危险)",
    },
    {
        "conditions": {"fluid_type": "HYDRAULIC", "continuous": True},
        "level": "R3",
        "score": 55,
        "description": "液压油持续泄漏=中等风险(先泄压，后吸附)",
    },
    {
        "conditions": {"fluid_type": "HYDRAULIC", "leak_size": "LARGE"},
        "level": "R3",
        "score": 65,
        "description": "大面积液压油泄漏=中高风险(专业回收容器)",
    },
    {
        "conditions": {"fluid_type": "HYDRAULIC"},
        "level": "R2",
        "score": 30,
        "description": "液压油泄漏=低风险",
    },
    {
        "conditions": {"fluid_type": "OIL", "continuous": True, "engine_status": "RUNNING"},
        "level": "R3",
        "score": 55,
        "description": "发动机滑油+持续泄漏+发动机运转=中风险(烟雾有毒)",
    },
    {
        "conditions": {"fluid_type": "OIL", "continuous": True},
        "level": "R2",
        "score": 50,
        "description": "发动机滑油持续泄漏=中风险(可燃)",
    },
    {
        "conditions": {"fluid_type": "OIL", "leak_size": "LARGE"},
        "level": "R2",
        "score": 45,
        "description": "大面积滑油泄漏=中风险(吸附材料，防滑处理)",
    },
    {
        "conditions": {"fluid_type": "OIL"},
        "level": "R1",
        "score": 25,
        "description": "滑油泄漏=低风险",
    },
]

RISK_SCORE_MAPPING = [
    (75, RiskLevel.R4.value),
    (55, RiskLevel.R3.value),
    (30, RiskLevel.R2.value),
    (0, RiskLevel.R1.value),
]


def score_to_risk_level(score: Optional[int]) -> str:
    """将分数映射到 R1-R4。"""
    if score is None:
        return RiskLevel.UNKNOWN.value
    for min_score, level in RISK_SCORE_MAPPING:
        if score >= min_score:
            return level
    return RiskLevel.UNKNOWN.value


def resolve_risk_level(rule_level: Optional[str], score: Optional[int]) -> str:
    """优先使用明确的 R1-R4，否则按分数映射。"""
    if rule_level in {RiskLevel.R1.value, RiskLevel.R2.value, RiskLevel.R3.value, RiskLevel.R4.value}:
        return rule_level
    if score is not None:
        return score_to_risk_level(score)
    return normalize_risk_level(rule_level or RiskLevel.UNKNOWN.value)




def match_rule(incident: Dict[str, Any], rule: Dict) -> Tuple[bool, List[str]]:
    """匹配规则"""
    conditions = rule["conditions"]
    matched_factors = []
    
    for key, expected_value in conditions.items():
        actual_value = incident.get(key)
        if actual_value is None:
            return False, []
        if isinstance(expected_value, list):
            if actual_value not in expected_value:
                return False, []
        elif actual_value != expected_value:
            return False, []
        matched_factors.append(f"{key}={actual_value}")
    
    return True, matched_factors


class AssessRiskTool(BaseTool):
    """风险评估工具（规则引擎）"""
    
    name = "assess_risk"
    description = """基于规则引擎评估漏油事件的风险等级。

输入参数（可选，默认从状态获取）:
- fluid_type: 油液类型
- continuous: 是否持续
- engine_status: 发动机状态
- leak_size: 泄漏面积

返回信息:
- 风险等级 (R1-R4)
- 风险分数
- 风险因素
- 立即行动建议"""
    
    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        # 合并输入和状态中的事件信息
        incident = state.get("incident", {}).copy()
        incident.update(inputs)
        scenario_type = state.get("scenario_type", "oil_spill")
        scenario = ScenarioRegistry.get(scenario_type)
        rules = scenario.risk_rules if scenario and scenario.risk_rules else RISK_RULES
        
        # 遍历规则，找到匹配的最高风险规则
        matched_rule = None
        matched_factors = []
        
        for rule in rules:
            is_match, factors = match_rule(incident, rule)
            if is_match:
                matched_rule = rule
                matched_factors = factors
                break  # 规则按优先级排序，找到第一个即可
        
        # 如果没有匹配规则，返回默认低风险
        if not matched_rule:
            matched_rule = {
                "level": "R1",
                "score": 10,
                "description": "未匹配到高风险规则",
            }
        
        score = matched_rule.get("score")
        level = resolve_risk_level(matched_rule.get("level"), score)
        
        # 获取立即行动
        immediate_actions_map = scenario.immediate_actions if scenario else {}
        immediate_actions = immediate_actions_map.get(level, [])
        
        # 构建结果
        observation = (
            f"风险评估完成: 等级={level}, 分数={score}, "
            f"因素={matched_factors}, "
            f"原因: {matched_rule.get('description', '未知')}"
        )
        
        return {
            "observation": observation,
            "risk_assessment": {
                "level": level,
                "score": score,
                "factors": matched_factors,
                "rationale": matched_rule.get("description", "未知"),
                "immediate_actions": immediate_actions,
            },
            "mandatory_actions_done": {
                "risk_assessed": True,
            },
        }
