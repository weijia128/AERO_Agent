"""
气象影响评估演示脚本
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.assessment.assess_weather_impact import AssessWeatherImpactTool
from tools.assessment.estimate_cleanup_time import EstimateCleanupTimeTool


def demo_scenario_1():
    """场景1: 高温大风天气"""
    print("=" * 60)
    print("场景1: 高温大风天气（燃油泄漏）")
    print("=" * 60)

    state = {
        "incident": {
            "fluid_type": "FUEL",
            "leak_size": "MEDIUM",
            "position": "501"
        },
        "weather": {
            "wind_direction": 270,  # 西风
            "wind_speed": 6.5,      # 大风
            "temperature": 25,       # 高温
            "visibility": 12000
        }
    }

    # 评估气象影响
    weather_tool = AssessWeatherImpactTool()
    weather_result = weather_tool.execute(state, {})
    print("\n" + weather_result["observation"])
    print()

    # 预估清理时间
    state["weather_impact"] = weather_result["weather_impact"]
    time_tool = EstimateCleanupTimeTool()
    time_result = time_tool.execute(state, {})
    print("\n" + time_result["observation"])
    print()


def demo_scenario_2():
    """场景2: 低温低能见度天气"""
    print("=" * 60)
    print("场景2: 低温低能见度天气（液压油泄漏）")
    print("=" * 60)

    state = {
        "incident": {
            "fluid_type": "HYDRAULIC",
            "leak_size": "SMALL",
            "position": "taxiway_A3"
        },
        "weather": {
            "wind_direction": 180,  # 南风
            "wind_speed": 3.0,      # 轻风
            "temperature": -8,       # 低温
            "visibility": 4000      # 低能见度
        }
    }

    # 评估气象影响
    weather_tool = AssessWeatherImpactTool()
    weather_result = weather_tool.execute(state, {})
    print("\n" + weather_result["observation"])
    print()

    # 预估清理时间
    state["weather_impact"] = weather_result["weather_impact"]
    time_tool = EstimateCleanupTimeTool()
    time_result = time_tool.execute(state, {})
    print("\n" + time_result["observation"])
    print()


def demo_scenario_3():
    """场景3: 极端低温条件（滑油泄漏）"""
    print("=" * 60)
    print("场景3: 极端低温条件（滑油泄漏在跑道）")
    print("=" * 60)

    state = {
        "incident": {
            "fluid_type": "OIL",
            "leak_size": "LARGE",
            "position": "runway_05L"
        },
        "weather": {
            "wind_direction": 0,    # 北风
            "wind_speed": 2.0,      # 微风
            "temperature": -15,      # 极低温
            "visibility": 10000
        }
    }

    # 评估气象影响
    weather_tool = AssessWeatherImpactTool()
    weather_result = weather_tool.execute(state, {})
    print("\n" + weather_result["observation"])
    print()

    # 预估清理时间
    state["weather_impact"] = weather_result["weather_impact"]
    time_tool = EstimateCleanupTimeTool()
    time_result = time_tool.execute(state, {})
    print("\n" + time_result["observation"])
    print()


if __name__ == "__main__":
    demo_scenario_1()
    print("\n")
    demo_scenario_2()
    print("\n")
    demo_scenario_3()
