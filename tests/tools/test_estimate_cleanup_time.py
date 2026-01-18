"""
清理时间预估工具测试
"""
import pytest
from tools.assessment.estimate_cleanup_time import EstimateCleanupTimeTool


class TestEstimateCleanupTimeTool:
    """清理时间预估工具测试类"""

    def setup_method(self):
        """测试前准备"""
        self.tool = EstimateCleanupTimeTool()

    def test_base_time_fuel_small_stand(self):
        """测试燃油小面积机位基准时间"""
        state = {
            "incident": {
                "fluid_type": "FUEL",
                "leak_size": "SMALL",
                "position": "501"
            }
        }
        result = self.tool.execute(state, {})

        estimate = result["cleanup_time_estimate"]
        assert estimate["base_time_minutes"] == 20
        assert estimate["position_type"] == "stand"

    def test_base_time_fuel_large_runway(self):
        """测试燃油大面积跑道基准时间"""
        state = {
            "incident": {
                "fluid_type": "FUEL",
                "leak_size": "LARGE",
                "position": "runway_05L"
            }
        }
        result = self.tool.execute(state, {})

        estimate = result["cleanup_time_estimate"]
        assert estimate["base_time_minutes"] == 90
        assert estimate["position_type"] == "runway"

    def test_weather_adjustment(self):
        """测试气象调整"""
        state = {
            "incident": {
                "fluid_type": "FUEL",
                "leak_size": "MEDIUM",
                "position": "501"
            },
            "weather_impact": {
                "cleanup_time_adjustment": {
                    "total_factor": 1.3
                }
            }
        }
        result = self.tool.execute(state, {})

        estimate = result["cleanup_time_estimate"]
        assert estimate["base_time_minutes"] == 30
        assert estimate["adjusted_time_minutes"] == 39  # 30 × 1.3

    def test_position_type_detection_taxiway(self):
        """测试滑行道识别"""
        state = {
            "incident": {
                "fluid_type": "HYDRAULIC",
                "leak_size": "SMALL",
                "position": "taxiway_A3"
            }
        }
        result = self.tool.execute(state, {})

        estimate = result["cleanup_time_estimate"]
        assert estimate["position_type"] == "taxiway"
        assert estimate["base_time_minutes"] == 20

    def test_default_values(self):
        """测试默认值"""
        state = {"incident": {}}
        result = self.tool.execute(state, {})

        estimate = result["cleanup_time_estimate"]
        assert estimate["fluid_type"] == "FUEL"
        assert estimate["leak_size"] == "MEDIUM"
        assert estimate["position_type"] == "stand"

    def test_hydraulic_medium_taxiway(self):
        """测试液压油中等面积滑行道"""
        state = {
            "incident": {
                "fluid_type": "HYDRAULIC",
                "leak_size": "MEDIUM",
                "position": "A3"
            }
        }
        result = self.tool.execute(state, {})

        estimate = result["cleanup_time_estimate"]
        assert estimate["base_time_minutes"] == 35
        assert estimate["position_type"] == "taxiway"

    def test_oil_large_stand(self):
        """测试滑油大面积机位"""
        state = {
            "incident": {
                "fluid_type": "OIL",
                "leak_size": "LARGE",
                "position": "502"
            }
        }
        result = self.tool.execute(state, {})

        estimate = result["cleanup_time_estimate"]
        assert estimate["base_time_minutes"] == 30
        assert estimate["position_type"] == "stand"

    def test_weather_factor_favorable(self):
        """测试有利气象条件"""
        state = {
            "incident": {
                "fluid_type": "FUEL",
                "leak_size": "SMALL",
                "position": "501"
            },
            "weather_impact": {
                "cleanup_time_adjustment": {
                    "total_factor": 0.8
                }
            }
        }
        result = self.tool.execute(state, {})

        estimate = result["cleanup_time_estimate"]
        assert estimate["adjusted_time_minutes"] == 16  # 20 × 0.8

    def test_position_type_runway_detection(self):
        """测试跑道识别"""
        # 测试 "05L" 格式
        state = {
            "incident": {
                "fluid_type": "FUEL",
                "leak_size": "MEDIUM",
                "position": "05L"
            }
        }
        result = self.tool.execute(state, {})
        assert result["cleanup_time_estimate"]["position_type"] == "runway"

        # 测试 "runway_06R" 格式
        state["incident"]["position"] = "runway_06R"
        result = self.tool.execute(state, {})
        assert result["cleanup_time_estimate"]["position_type"] == "runway"

    def test_observation_format_with_adjustment(self):
        """测试带气象调整的输出格式"""
        state = {
            "incident": {
                "fluid_type": "FUEL",
                "leak_size": "MEDIUM",
                "position": "501"
            },
            "weather_impact": {
                "cleanup_time_adjustment": {
                    "total_factor": 1.2
                }
            }
        }
        result = self.tool.execute(state, {})

        observation = result["observation"]
        assert "清理时间预估完成" in observation
        assert "气象调整系数" in observation
        assert "气象条件不利" in observation
