"""
气象影响评估工具测试
"""
import pytest
from tools.assessment.assess_weather_impact import AssessWeatherImpactTool


class TestAssessWeatherImpactTool:
    """气象影响评估工具测试类"""

    def setup_method(self):
        """测试前准备"""
        self.tool = AssessWeatherImpactTool()

    def test_wind_impact_slow(self):
        """测试微风情况"""
        state = {
            "incident": {"fluid_type": "FUEL"},
            "weather": {"wind_direction": 270, "wind_speed": 1.5}
        }
        result = self.tool.execute(state, {})

        wind_impact = result["weather_impact"]["wind_impact"]
        assert wind_impact["spread_rate"] == "缓慢"
        assert wind_impact["radius_adjustment"] == 0

    def test_wind_impact_fast(self):
        """测试大风情况"""
        state = {
            "incident": {"fluid_type": "FUEL"},
            "weather": {"wind_direction": 270, "wind_speed": 6.0}
        }
        result = self.tool.execute(state, {})

        wind_impact = result["weather_impact"]["wind_impact"]
        assert wind_impact["spread_rate"] == "快速"
        assert wind_impact["radius_adjustment"] == 1

    def test_temperature_impact_fuel_hot(self):
        """测试高温对燃油的影响"""
        state = {
            "incident": {"fluid_type": "FUEL"},
            "weather": {"temperature": 20}
        }
        result = self.tool.execute(state, {})

        temp_impact = result["weather_impact"]["temperature_impact"]
        assert temp_impact["volatility"] == "高"
        assert temp_impact["time_factor"] == 0.8

    def test_temperature_impact_fuel_cold(self):
        """测试低温对燃油的影响"""
        state = {
            "incident": {"fluid_type": "FUEL"},
            "weather": {"temperature": -5}
        }
        result = self.tool.execute(state, {})

        temp_impact = result["weather_impact"]["temperature_impact"]
        assert temp_impact["viscosity"] == "高"
        assert temp_impact["time_factor"] == 1.3

    def test_visibility_impact_good(self):
        """测试良好能见度"""
        state = {
            "incident": {"fluid_type": "FUEL"},
            "weather": {"visibility": 15000}
        }
        result = self.tool.execute(state, {})

        vis_impact = result["weather_impact"]["visibility_impact"]
        assert vis_impact["safety_level"] == "良好"
        assert vis_impact["time_factor"] == 1.0

    def test_visibility_impact_poor(self):
        """测试低能见度"""
        state = {
            "incident": {"fluid_type": "FUEL"},
            "weather": {"visibility": 3000}
        }
        result = self.tool.execute(state, {})

        vis_impact = result["weather_impact"]["visibility_impact"]
        assert vis_impact["safety_level"] == "困难"
        assert vis_impact["require_extra_caution"] is True
        assert vis_impact["time_factor"] == 1.15

    def test_comprehensive_impact(self):
        """测试综合气象影响"""
        state = {
            "incident": {"fluid_type": "FUEL"},
            "weather": {
                "wind_direction": 270,
                "wind_speed": 5.5,
                "temperature": -2,
                "visibility": 8000
            }
        }
        result = self.tool.execute(state, {})

        cleanup_adj = result["weather_impact"]["cleanup_time_adjustment"]
        # 快速扩散(1.2) × 低温(1.3) × 中等能见度(1.05) ≈ 1.64
        assert cleanup_adj["total_factor"] > 1.5

    def test_wind_direction_conversion(self):
        """测试风向转换"""
        # 西风(270度) → 向东扩散
        state = {
            "incident": {"fluid_type": "FUEL"},
            "weather": {"wind_direction": 270, "wind_speed": 3}
        }
        result = self.tool.execute(state, {})
        assert result["weather_impact"]["wind_impact"]["spread_direction"] == "东方向"

        # 北风(0度) → 向南扩散
        state["weather"]["wind_direction"] = 0
        result = self.tool.execute(state, {})
        assert result["weather_impact"]["wind_impact"]["spread_direction"] == "南方向"

    def test_missing_weather_data(self):
        """测试缺失气象数据"""
        state = {"incident": {"fluid_type": "FUEL"}}
        result = self.tool.execute(state, {})
        assert "缺少气象数据" in result["observation"]

    def test_hydraulic_fluid_temperature(self):
        """测试液压油温度影响"""
        state = {
            "incident": {"fluid_type": "HYDRAULIC"},
            "weather": {"temperature": -8}
        }
        result = self.tool.execute(state, {})

        temp_impact = result["weather_impact"]["temperature_impact"]
        assert temp_impact["viscosity"] == "高"
        assert temp_impact["time_factor"] == 1.1

    def test_oil_fluid_temperature(self):
        """测试滑油温度影响"""
        state = {
            "incident": {"fluid_type": "OIL"},
            "weather": {"temperature": -10}
        }
        result = self.tool.execute(state, {})

        temp_impact = result["weather_impact"]["temperature_impact"]
        assert temp_impact["viscosity"] == "极高"
        assert temp_impact["time_factor"] == 1.5
