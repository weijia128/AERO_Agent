"""
测试使用真实数据的航班影响预测功能

测试场景：2026-01-06 10:00 在 501 机位发生大面积燃油泄漏
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from tools.spatial.predict_flight_impact import PredictFlightImpactTool
from tools.spatial.calculate_impact_zone import CalculateImpactZoneTool
from tools.assessment.estimate_cleanup_time import EstimateCleanupTimeTool
from tools.assessment.assess_weather_impact import AssessWeatherImpactTool


def test_flight_impact_prediction():
    """测试航班影响预测（使用 2026-01-06 真实数据）"""

    print("=" * 80)
    print("测试场景：2026-01-06 10:00 在 501 机位发生大面积燃油泄漏")
    print("=" * 80)

    # 初始化工具
    cleanup_tool = EstimateCleanupTimeTool()
    weather_tool = AssessWeatherImpactTool()
    impact_zone_tool = CalculateImpactZoneTool()
    flight_impact_tool = PredictFlightImpactTool()

    # 模拟 agent state
    state = {
        "incident": {
            "incident_time": "2026-01-06 10:00:00",
            "start_time": "2026-01-06 10:00:00",
            "position": "501",
            "fluid_type": "FUEL",
            "leak_size": "LARGE",
        },
        "risk_assessment": {
            "risk_level": "HIGH"
        }
    }

    print("\n步骤 1: 评估气象影响")
    print("-" * 80)
    weather_result = weather_tool.execute(state, {
        "position": "501",
        "incident_time": "2026-01-06 10:00:00",
        "fluid_type": "FUEL"
    })
    print(weather_result.get("observation", ""))

    # 更新 state
    state["weather_impact"] = weather_result.get("weather_impact", {})

    print("\n步骤 2: 估算清理时间")
    print("-" * 80)
    cleanup_result = cleanup_tool.execute(state, {
        "fluid_type": "FUEL",
        "leak_size": "LARGE",
        "position": "501"
    })
    print(cleanup_result.get("observation", ""))
    cleanup_minutes = cleanup_result.get("cleanup_time_minutes", 90)

    print("\n步骤 3: 计算空间影响范围")
    print("-" * 80)
    impact_zone_result = impact_zone_tool.execute(state, {
        "anchor_position": "501",
        "fluid_type": "FUEL",
        "risk_level": "HIGH"
    })
    print(impact_zone_result.get("observation", ""))

    # 更新 state
    state["spatial_analysis"] = impact_zone_result.get("spatial_analysis", {})

    print("\n步骤 4: 预测航班影响")
    print("-" * 80)
    # 计算时间窗口（以小时为单位）
    time_window_hours = max(2, cleanup_minutes / 60)

    flight_result = flight_impact_tool.execute(state, {
        "time_window": time_window_hours
    })

    print(flight_result.get("observation", ""))

    # 详细统计
    flight_impact = flight_result.get("flight_impact", {})
    if flight_impact:
        stats = flight_impact.get("statistics", {})
        print("\n" + "=" * 80)
        print("总结报告")
        print("=" * 80)
        print(f"事故时间: 2026-01-06 10:00:00")
        print(f"事故位置: 501 机位")
        print(f"泄漏类型: 大面积燃油泄漏")
        print(f"预估清理时间: {cleanup_minutes} 分钟")
        print(f"分析时间窗口: {time_window_hours:.1f} 小时")
        print(f"\n受影响航班统计:")
        print(f"  - 总数: {stats.get('total_affected_flights', 0)} 架次")
        print(f"  - 总延误: {stats.get('total_delay_minutes', 0)} 分钟")
        print(f"  - 平均延误: {stats.get('average_delay_minutes', 0):.1f} 分钟/架次")

        sev = stats.get('severity_distribution', {})
        print(f"\n延误严重性分布:")
        print(f"  - 严重 (≥60分钟): {sev.get('high', 0)} 架次")
        print(f"  - 中等 (20-59分钟): {sev.get('medium', 0)} 架次")
        print(f"  - 轻微 (<20分钟): {sev.get('low', 0)} 架次")

        affected_flights = flight_impact.get("affected_flights", [])
        if affected_flights:
            print(f"\n受影响最严重的航班（前 5）:")
            for i, flight in enumerate(affected_flights[:5], 1):
                print(f"  {i}. {flight['callsign']}: "
                      f"延误 {flight['estimated_delay_minutes']} 分钟 "
                      f"({flight['delay_reason']}, "
                      f"机位={flight['stand']}, 跑道={flight['runway']})")

    print("\n" + "=" * 80)
    print("测试完成!")
    print("=" * 80)


if __name__ == "__main__":
    test_flight_impact_prediction()
