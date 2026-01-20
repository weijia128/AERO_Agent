"""
测试综合分析工具（使用真实数据）

测试场景：
- 时间：2026-01-06 10:00
- 位置：501 机位
- 事故：大面积燃油泄漏
- 数据来源：真实历史数据（航班计划、气象、拓扑）
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from tools.assessment.analyze_spill_comprehensive import AnalyzeSpillComprehensiveTool


def test_comprehensive_analysis():
    """测试综合分析工具"""

    print("\n" + "=" * 80)
    print("测试场景：2026-01-06 10:00 在 501 机位发生大面积燃油泄漏")
    print("数据来源：2026-01-06 8-12点 真实历史数据")
    print("=" * 80 + "\n")

    # 初始化工具
    tool = AnalyzeSpillComprehensiveTool()

    # 模拟 agent state（从用户交互中获取的信息）
    state = {
        "incident": {
            "position": "501",
            "fluid_type": "FUEL",
            "leak_size": "LARGE",
            "incident_time": "2026-01-06 10:00:00",
            "start_time": "2026-01-06 10:00:00",
        },
        "risk_assessment": {
            "risk_level": "HIGH"
        }
    }

    print("📋 从 Agent 交互中获取的信息:")
    print(f"  位置: {state['incident']['position']}")
    print(f"  时间: {state['incident']['incident_time']}")
    print(f"  油液类型: {state['incident']['fluid_type']}")
    print(f"  泄漏面积: {state['incident']['leak_size']}")
    print(f"  风险等级: {state['risk_assessment']['risk_level']}")

    print("\n开始执行综合分析...\n")

    # 执行综合分析
    result = tool.execute(state, {})

    # 输出结果
    print(result.get("observation", ""))

    # 验证结果结构
    comprehensive_analysis = result.get("comprehensive_analysis", {})

    print("\n" + "=" * 80)
    print("验证数据完整性")
    print("=" * 80)

    # 验证清理分析
    cleanup = comprehensive_analysis.get("cleanup_analysis", {})
    print(f"\n✓ 清理时间分析:")
    print(f"  - 基准时间: {cleanup.get('base_time_minutes', 0)} 分钟")
    print(f"  - 调整后时间: {cleanup.get('weather_adjusted_minutes', 0)} 分钟")

    # 验证空间影响
    spatial = comprehensive_analysis.get("spatial_impact", {})
    print(f"\n✓ 空间影响分析:")
    print(f"  - 受影响机位: {len(spatial.get('affected_stands', []))} 个")
    print(f"  - 受影响滑行道: {len(spatial.get('affected_taxiways', []))} 条")
    print(f"  - 受影响跑道: {len(spatial.get('affected_runways', []))} 条")

    # 验证航班影响
    flight = comprehensive_analysis.get("flight_impact", {})
    stats = flight.get("statistics", {})
    print(f"\n✓ 航班影响分析:")
    print(f"  - 受影响航班: {stats.get('total_affected_flights', 0)} 架次")
    print(f"  - 累计延误: {stats.get('total_delay_minutes', 0)} 分钟")
    print(f"  - 平均延误: {stats.get('average_delay_minutes', 0):.1f} 分钟")

    # 验证风险场景
    scenarios = comprehensive_analysis.get("risk_scenarios", [])
    print(f"\n✓ 风险场景分析: {len(scenarios)} 个场景")
    for i, scenario in enumerate(scenarios, 1):
        print(f"  {i}. [{scenario['category']}] {scenario['scenario']}")

    # 验证解决建议
    recommendations = comprehensive_analysis.get("recommendations", [])
    print(f"\n✓ 解决建议: {len(recommendations)} 条建议")
    for i, rec in enumerate(recommendations, 1):
        print(f"  {i}. [{rec['priority']}] {rec['action']}")

    print("\n" + "=" * 80)
    print("测试完成!")
    print("=" * 80)

    assert isinstance(comprehensive_analysis, dict)
    assert "cleanup_analysis" in comprehensive_analysis


def test_different_scenarios():
    """测试不同场景"""

    print("\n" + "=" * 80)
    print("测试不同场景")
    print("=" * 80)

    tool = AnalyzeSpillComprehensiveTool()

    # 场景1：中等面积液压油泄漏
    print("\n场景 1: 中等面积液压油泄漏")
    print("-" * 80)

    state1 = {
        "incident": {
            "position": "558",
            "fluid_type": "HYDRAULIC",
            "leak_size": "MEDIUM",
            "incident_time": "2026-01-06 09:00:00",
        },
        "risk_assessment": {
            "risk_level": "MEDIUM"
        }
    }

    result1 = tool.execute(state1, {})
    analysis1 = result1.get("comprehensive_analysis", {})
    stats1 = analysis1.get("flight_impact", {}).get("statistics", {})

    print(f"  清理时间: {analysis1.get('cleanup_analysis', {}).get('weather_adjusted_minutes', 0)} 分钟")
    print(f"  受影响航班: {stats1.get('total_affected_flights', 0)} 架次")

    # 场景2：小面积滑油泄漏
    print("\n场景 2: 小面积滑油泄漏")
    print("-" * 80)

    state2 = {
        "incident": {
            "position": "524",
            "fluid_type": "OIL",
            "leak_size": "SMALL",
            "incident_time": "2026-01-06 11:00:00",
        },
        "risk_assessment": {
            "risk_level": "LOW"
        }
    }

    result2 = tool.execute(state2, {})
    analysis2 = result2.get("comprehensive_analysis", {})
    stats2 = analysis2.get("flight_impact", {}).get("statistics", {})

    print(f"  清理时间: {analysis2.get('cleanup_analysis', {}).get('weather_adjusted_minutes', 0)} 分钟")
    print(f"  受影响航班: {stats2.get('total_affected_flights', 0)} 架次")

    print("\n" + "=" * 80)
    print("多场景测试完成!")
    print("=" * 80)


if __name__ == "__main__":
    # 测试1：主场景
    print("\n" + "#" * 80)
    print("# 测试 1: 主场景（大面积燃油泄漏）")
    print("#" * 80)
    test_comprehensive_analysis()

    # 测试2：不同场景对比
    print("\n" + "#" * 80)
    print("# 测试 2: 不同场景对比")
    print("#" * 80)
    test_different_scenarios()

    print("\n" + "#" * 80)
    print("# 所有测试完成!")
    print("#" * 80)
