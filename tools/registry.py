"""
工具注册中心
"""
from typing import Dict, Optional, List
from tools.base import BaseTool


class ToolRegistry:
    """工具注册中心"""
    
    _tools: Dict[str, BaseTool] = {}
    _scenario_tools: Dict[str, List[str]] = {}
    
    @classmethod
    def register(cls, tool: BaseTool, scenarios: List[str] = None):
        """注册工具"""
        cls._tools[tool.name] = tool
        
        # 注册到场景
        if scenarios:
            for scenario in scenarios:
                if scenario not in cls._scenario_tools:
                    cls._scenario_tools[scenario] = []
                cls._scenario_tools[scenario].append(tool.name)
    
    @classmethod
    def get(cls, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return cls._tools.get(name)
    
    @classmethod
    def get_all(cls) -> Dict[str, BaseTool]:
        """获取所有工具"""
        return cls._tools.copy()
    
    @classmethod
    def get_by_scenario(cls, scenario: str) -> List[BaseTool]:
        """获取场景相关工具"""
        tool_names = cls._scenario_tools.get(scenario, [])
        # 加上通用工具
        all_tool_names = set(tool_names) | set(cls._scenario_tools.get("common", []))
        return [cls._tools[name] for name in all_tool_names if name in cls._tools]
    
    @classmethod
    def get_descriptions(cls, scenario: str = None) -> str:
        """获取工具描述"""
        if scenario:
            tools = cls.get_by_scenario(scenario)
        else:
            tools = list(cls._tools.values())
        
        descriptions = []
        for tool in tools:
            descriptions.append(tool.get_description())
        
        return "\n\n".join(descriptions)


def get_tool(name: str) -> Optional[BaseTool]:
    """获取工具的便捷函数"""
    return ToolRegistry.get(name)


def get_tools_description(scenario: str = None) -> str:
    """获取工具描述的便捷函数"""
    return ToolRegistry.get_descriptions(scenario)


# ============================================================
# 注册所有工具
# ============================================================

def register_all_tools():
    """注册所有工具"""
    from tools.information.ask_for_detail import AskForDetailTool
    from tools.information.smart_ask import SmartAskTool
    from tools.information.get_aircraft_info import GetAircraftInfoTool
    from tools.information.get_weather import GetWeatherTool
    from tools.information.flight_plan_lookup import FlightPlanLookupTool
    from tools.spatial.get_stand_location import GetStandLocationTool
    from tools.spatial.calculate_impact_zone import CalculateImpactZoneTool
    from tools.spatial.predict_flight_impact import PredictFlightImpactTool
    from tools.spatial.analyze_position_impact import AnalyzePositionImpactTool
    from tools.knowledge.search_regulations import SearchRegulationsTool
    from tools.assessment.assess_risk import AssessRiskTool
    from tools.assessment.assess_bird_strike_risk import AssessBirdStrikeRiskTool
    from tools.action.notify_department import NotifyDepartmentTool
    from tools.action.generate_report import GenerateReportTool

    # 通用工具
    ToolRegistry.register(AskForDetailTool(), ["common"])
    ToolRegistry.register(SmartAskTool(), ["common"])
    ToolRegistry.register(GetAircraftInfoTool(), ["common"])
    ToolRegistry.register(GetWeatherTool(), ["common"])
    ToolRegistry.register(FlightPlanLookupTool(), ["common"])
    ToolRegistry.register(NotifyDepartmentTool(), ["common"])
    ToolRegistry.register(GenerateReportTool(), ["common"])

    # 漏油场景工具
    ToolRegistry.register(GetStandLocationTool(), ["oil_spill", "common"])
    ToolRegistry.register(CalculateImpactZoneTool(), ["oil_spill"])
    ToolRegistry.register(PredictFlightImpactTool(), ["oil_spill"])
    ToolRegistry.register(AnalyzePositionImpactTool(), ["oil_spill"])
    ToolRegistry.register(SearchRegulationsTool(), ["oil_spill", "common"])
    ToolRegistry.register(AssessRiskTool(), ["oil_spill"])
    ToolRegistry.register(AssessBirdStrikeRiskTool(), ["bird_strike"])


# 自动注册
try:
    register_all_tools()
except ImportError:
    # 模块可能还未完全加载
    pass
