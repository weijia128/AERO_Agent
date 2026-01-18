"""
集成测试：气象增强流程
"""
import pytest
from tools.assessment.assess_weather_impact import AssessWeatherImpactTool
from tools.assessment.estimate_cleanup_time import EstimateCleanupTimeTool


class TestWeatherEnhancedFlow:
    """测试完整的气象增强流程"""

    def test_complete_flow_with_weather(self):
        """测试完整流程（包含气象数据）"""
        # 模拟状态
        state = {
            "incident": {
                "fluid_type": "FUEL",
                "leak_size": "MEDIUM",
                "position": "501"
            },
            "weather": {
                "wind_direction": 270,
                "wind_speed": 5.2,
                "temperature": 3,
                "visibility": 10000
            }
        }

        # Step 1: 评估气象影响
        weather_impact_tool = AssessWeatherImpactTool()
        result1 = weather_impact_tool.execute(state, {})

        assert "weather_impact" in result1
        assert "observation" in result1

        weather_impact = result1["weather_impact"]
        assert "wind_impact" in weather_impact
        assert "temperature_impact" in weather_impact
        assert "visibility_impact" in weather_impact
        assert "cleanup_time_adjustment" in weather_impact

        # 验证风向影响
        assert weather_impact["wind_impact"]["spread_rate"] == "快速"
        assert weather_impact["wind_impact"]["radius_adjustment"] == 1
        assert weather_impact["wind_impact"]["spread_direction"] == "东方向"

        # 验证温度影响
        assert weather_impact["temperature_impact"]["viscosity"] == "中"
        assert weather_impact["temperature_impact"]["time_factor"] == 1.0

        # Step 2: 更新状态
        state["weather_impact"] = weather_impact

        # Step 3: 预估清理时间
        cleanup_time_tool = EstimateCleanupTimeTool()
        result2 = cleanup_time_tool.execute(state, {})

        assert "cleanup_time_estimate" in result2
        assert "observation" in result2

        estimate = result2["cleanup_time_estimate"]
        assert estimate["base_time_minutes"] == 30  # FUEL + MEDIUM + stand
        assert estimate["adjusted_time_minutes"] > 0
        assert estimate["weather_factor"] == weather_impact["cleanup_time_adjustment"]["total_factor"]

    def test_complete_flow_without_weather(self):
        """测试缺少气象数据的情况"""
        state = {
            "incident": {
                "fluid_type": "HYDRAULIC",
                "leak_size": "SMALL",
                "position": "taxiway_A3"
            }
        }

        # Step 1: 评估气象影响（缺少气象数据,工具会尝试查询或使用默认值）
        weather_impact_tool = AssessWeatherImpactTool()
        result1 = weather_impact_tool.execute(state, {})

        # 工具应该返回某种结果（可能是查询结果或默认值）
        assert "weather_impact" in result1 or "缺少气象数据" in result1["observation"]

        # Step 2: 预估清理时间（使用默认气象系数）
        cleanup_time_tool = EstimateCleanupTimeTool()
        result2 = cleanup_time_tool.execute(state, {})

        estimate = result2["cleanup_time_estimate"]
        assert estimate["base_time_minutes"] == 20  # HYDRAULIC + SMALL + taxiway
        # 如果没有气象影响数据,使用默认系数1.0
        assert estimate["weather_factor"] >= 1.0
        assert estimate["adjusted_time_minutes"] >= 20

    def test_flow_with_extreme_weather(self):
        """测试极端天气条件"""
        state = {
            "incident": {
                "fluid_type": "OIL",
                "leak_size": "LARGE",
                "position": "runway_05L"
            },
            "weather": {
                "wind_direction": 0,
                "wind_speed": 8.0,     # 强风
                "temperature": -20,     # 极低温
                "visibility": 2000      # 低能见度
            }
        }

        # Step 1: 评估气象影响
        weather_impact_tool = AssessWeatherImpactTool()
        result1 = weather_impact_tool.execute(state, {})

        weather_impact = result1["weather_impact"]

        # 验证极端条件识别
        assert weather_impact["wind_impact"]["spread_rate"] == "快速"
        assert weather_impact["temperature_impact"]["viscosity"] == "极高"
        assert weather_impact["visibility_impact"]["safety_level"] == "困难"

        # 验证调整系数显著增加
        total_factor = weather_impact["cleanup_time_adjustment"]["total_factor"]
        assert total_factor > 1.5  # 1.2 (风) × 1.5 (温度) × 1.15 (能见度) ≈ 2.07

        # Step 2: 预估清理时间
        state["weather_impact"] = weather_impact
        cleanup_time_tool = EstimateCleanupTimeTool()
        result2 = cleanup_time_tool.execute(state, {})

        estimate = result2["cleanup_time_estimate"]
        assert estimate["base_time_minutes"] == 60  # OIL + LARGE + runway
        # 调整后时间应该显著增加
        assert estimate["adjusted_time_minutes"] > 90

    def test_flow_with_favorable_weather(self):
        """测试有利气象条件"""
        state = {
            "incident": {
                "fluid_type": "FUEL",
                "leak_size": "SMALL",
                "position": "501"
            },
            "weather": {
                "wind_direction": 90,
                "wind_speed": 1.5,      # 微风
                "temperature": 25,       # 高温
                "visibility": 15000      # 极好能见度
            }
        }

        # Step 1: 评估气象影响
        weather_impact_tool = AssessWeatherImpactTool()
        result1 = weather_impact_tool.execute(state, {})

        weather_impact = result1["weather_impact"]

        # 验证有利条件
        assert weather_impact["wind_impact"]["spread_rate"] == "缓慢"
        assert weather_impact["temperature_impact"]["cleanup_difficulty"] == "简单"
        assert weather_impact["visibility_impact"]["safety_level"] == "良好"

        # 验证调整系数减小
        total_factor = weather_impact["cleanup_time_adjustment"]["total_factor"]
        assert total_factor < 1.0  # 温度因子 0.8

        # Step 2: 预估清理时间
        state["weather_impact"] = weather_impact
        cleanup_time_tool = EstimateCleanupTimeTool()
        result2 = cleanup_time_tool.execute(state, {})

        estimate = result2["cleanup_time_estimate"]
        assert estimate["base_time_minutes"] == 20  # FUEL + SMALL + stand
        # 调整后时间应该减少
        assert estimate["adjusted_time_minutes"] < 20

    def test_tool_registry_integration(self):
        """测试工具注册集成"""
        from tools.registry import ToolRegistry

        # 验证工具已注册
        weather_tool = ToolRegistry.get("assess_weather_impact")
        cleanup_tool = ToolRegistry.get("estimate_cleanup_time")

        assert weather_tool is not None
        assert cleanup_tool is not None
        assert weather_tool.name == "assess_weather_impact"
        assert cleanup_tool.name == "estimate_cleanup_time"

        # 验证工具描述可获取
        weather_desc = weather_tool.get_description()
        cleanup_desc = cleanup_tool.get_description()

        assert "气象条件" in weather_desc
        assert "清理时间" in cleanup_desc
