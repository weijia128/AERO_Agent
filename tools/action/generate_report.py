"""
报告生成工具
"""
from typing import Dict, Any
from tools.base import BaseTool
from constraints.loader import get_loader
from scenarios.base import ScenarioRegistry


class GenerateReportTool(BaseTool):
    """生成处置报告"""
    
    name = "generate_report"
    description = """生成事件处置报告。
    
通常在信息收集完成、风险评估完成后调用。

输入参数（可选）:
- include_recommendations: 是否包含建议
- format: 报告格式（checklist/narrative）

返回信息:
- 结构化报告内容"""
    
    def execute(self, state: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        include_recommendations = inputs.get("include_recommendations", True)
        report_format = inputs.get("format", "checklist")
        
        # 检查前置条件
        mandatory = state.get("mandatory_actions_done", {})
        scenario_type = state.get("scenario_type", "oil_spill")
        scenario = ScenarioRegistry.get(scenario_type)
        risk_required = scenario.risk_required if scenario else True
        if risk_required and not mandatory.get("risk_assessed"):
            return {
                "observation": "生成报告前必须完成风险评估",
            }
        
        checklist = state.get("checklist", {})
        p1_fields = get_loader().get_all_p1_keys(scenario_type)
        if not p1_fields:
            p1_fields = ["fluid_type", "continuous", "engine_status", "position"]
        p1_missing = [f for f in p1_fields if not checklist.get(f)]
        
        if p1_missing:
            return {
                "observation": f"生成报告前需要完成 P1 信息收集: {p1_missing}",
            }
        
        # 生成确认询问消息
        incident = state.get("incident", {})
        observation = "报告准备完成，等待用户确认是否需要补充信息。"

        return {
            "observation": observation,
            # 不直接设置 is_complete，而是设置 report_generated 标志
            "report_generated": True,
            "awaiting_supplemental_info": False,
            "messages": [],
        }
