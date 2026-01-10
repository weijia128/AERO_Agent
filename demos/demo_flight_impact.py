"""
演示：获取位置信息后，结合拓扑图和航班数据分析漏油影响

展示如何在Agent中集成拓扑图分析和航班影响预测
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.spatial.topology_loader import get_topology_loader
from tools.spatial.calculate_impact_zone import CalculateImpactZoneTool
from tools.spatial.predict_flight_impact import PredictFlightImpactTool


def demo_position_based_impact_analysis():
    """演示基于位置的漏油影响分析"""
    print("=" * 70)
    print("演示：基于位置的漏油影响分析")
    print("=" * 70)

    # 模拟用户输入的位置信息
    test_positions = [
        {
            "position": "corrected_stand_0",
            "fluid_type": "FUEL",
            "description": "501机位，燃油泄漏"
        },
        {
            "position": "corrected_stand_5",
            "fluid_type": "FUEL",
            "description": "502机位，燃油泄漏"
        },
        {
            "position": "corrected_stand_10",
            "fluid_type": "HYDRAULIC",
            "description": "503机位，液压油泄漏"
        }
    ]

    for i, scenario in enumerate(test_positions, 1):
        print(f"\n{'='*70}")
        print(f"场景 {i}: {scenario['description']}")
        print(f"{'='*70}")

        # 创建模拟状态
        state = {
            "incident": {
                "position": scenario["position"],
                "fluid_type": scenario["fluid_type"]
            },
            "risk_assessment": {
                "level": "HIGH"
            }
        }

        # Step 1: 计算影响范围
        print(f"\n[步骤 1] 计算影响范围...")
        impact_tool = CalculateImpactZoneTool()
        impact_result = impact_tool.execute(state, {})

        observation = impact_result.get("observation", "")
        print(f"观察结果: {observation}")

        spatial = impact_result.get("spatial_analysis", {})
        if spatial:
            print(f"\n影响范围详情:")
            print(f"  起始节点: {spatial.get('anchor_node')}")
            print(f"  隔离节点数: {len(spatial.get('isolated_nodes', []))}")
            print(f"  受影响机位: {len(spatial.get('affected_stands', []))}")
            print(f"  受影响滑行道: {len(spatial.get('affected_taxiways', []))}")
            print(f"  受影响跑道: {len(spatial.get('affected_runways', []))}")

            # Step 2: 预测航班影响
            print(f"\n[步骤 2] 预测航班影响...")

            # 更新状态
            state["spatial_analysis"] = spatial

            predict_tool = PredictFlightImpactTool()
            predict_result = predict_tool.execute(state, {"time_window": 2})

            prediction_obs = predict_result.get("observation", "")
            print(f"预测结果: {prediction_obs}")

            # 显示详细统计
            flight_impact = predict_result.get("flight_impact", {})
            if flight_impact:
                stats = flight_impact.get("statistics", {})
                if stats:
                    total = stats.get("total_affected_flights", 0)
                    avg_delay = stats.get('average_delay_minutes', 0)
                    print(f"\n影响统计:")
                    print(f"  受影响航班: {total} 架次")
                    print(f"  平均延误: {avg_delay:.1f} 分钟")

                    severity = stats.get('severity_distribution', {})
                    if severity:
                        print(f"  严重延误: {severity.get('high', 0)} 架次")
                        print(f"  中等延误: {severity.get('medium', 0)} 架次")
                        print(f"  轻微延误: {severity.get('low', 0)} 架次")

            # Step 3: 生成处置建议
            print(f"\n[步骤 3] 处置建议:")

            recommendations = []

            # 基于风险等级
            if scenario["fluid_type"] == "FUEL":
                recommendations.append("立即通知消防部门")
                recommendations.append("建立300米安全隔离区")

            # 基于影响范围
            if spatial.get("affected_runways"):
                recommendations.append("跑道受影响，建议启用备用跑道")
                recommendations.append("协调进离港航班调整")

            # 基于航班影响
            if flight_impact and flight_impact.get("statistics"):
                stats = flight_impact["statistics"]
                avg_delay = stats.get("average_delay_minutes", 0)
                if avg_delay >= 60:
                    recommendations.append("延误严重，建议发布机场通告")
                elif avg_delay >= 30:
                    recommendations.append("延误较重，建议向旅客发布延误信息")

            # 基于位置
            if "stand" in scenario["position"].lower():
                recommendations.append("机位封锁，需安排备用机位")

            for rec in recommendations:
                print(f"  - {rec}")

        print()


def demo_react_integration():
    """演示如何在ReAct推理中集成影响分析"""
    print("\n" + "=" * 70)
    print("演示：ReAct推理中的影响分析显示")
    print("=" * 70)

    # 模拟Agent状态
    state = {
        "incident": {
            "position": "corrected_stand_0",
            "fluid_type": "FUEL"
        },
        "spatial_analysis": {
            "anchor_node": "corrected_stand_0",
            "anchor_node_type": "stand",
            "isolated_nodes": ["stand_0", "stand_1", "stand_2", "taxiway_5"],
            "affected_stands": ["stand_0", "stand_1", "stand_2"],
            "affected_taxiways": ["taxiway_5"],
            "affected_runways": [],
            "impact_radius": 2
        },
        "flight_impact_prediction": {
            "statistics": {
                "total_affected_flights": 15,
                "average_delay_minutes": 35.5,
                "severity_distribution": {
                    "high": 3,
                    "medium": 8,
                    "low": 4
                }
            }
        }
    }

    print("\n在ReAct推理Prompt中显示的影响分析结果:")
    print("-" * 70)

    # 模拟build_scenario_prompt中的输出
    spatial = state.get("spatial_analysis", {})
    if spatial:
        print("\n## 影响范围分析结果")
        if spatial.get("anchor_node"):
            print(f"起始位置: {spatial['anchor_node']} ({spatial.get('anchor_node_type', '')})")
        if spatial.get("isolated_nodes"):
            print(f"隔离区域: {len(spatial['isolated_nodes'])} 个节点")
        if spatial.get("affected_stands"):
            print(f"受影响机位: {', '.join(spatial['affected_stands'])}")
        if spatial.get("affected_taxiways"):
            print(f"受影响滑行道: {', '.join(spatial['affected_taxiways'])}")
        if spatial.get("affected_runways"):
            print(f"受影响跑道: {', '.join(spatial['affected_runways'])}")

    flight_impact = state.get("flight_impact_prediction", {})
    if flight_impact:
        print("\n## 航班影响预测结果")
        stats = flight_impact.get("statistics", {})
        if stats:
            total = stats.get("total_affected_flights", 0)
            avg_delay = stats.get("average_delay_minutes", 0)
            print(f"预计受影响航班: {total} 架次")
            print(f"预计平均延误: {avg_delay:.1f} 分钟")

            severity = stats.get("severity_distribution", {})
            if severity:
                print(f"影响分布: 严重 {severity.get('high', 0)}, "
                      f"中等 {severity.get('medium', 0)}, "
                      f"轻微 {severity.get('low', 0)}")

    print("\n" + "-" * 70)
    print("\nLLM基于这些信息进行推理:")
    print("思考: 机位燃油泄漏已影响3个机位和1条滑行道")
    print("思考: 预计影响15架航班，平均延误35分钟")
    print("思考: 需要立即通知消防部门，并协调备用跑道")
    print("行动: notify_department -> 通知消防和运行指挥")


def main():
    """主函数"""
    # 确保拓扑图已加载
    try:
        topology = get_topology_loader()
        stats = topology.get_statistics()
        print(f"\n✓ 拓扑图加载成功")
        print(f"  总节点: {stats['total_nodes']}")
        print(f"  机位: {stats['stands']}")
        print(f"  滑行道: {stats['taxiways']}")
        print(f"  跑道: {stats['runways']}")
    except Exception as e:
        print(f"\n✗ 拓扑图加载失败: {e}")
        print("请先运行: python scripts/data_processing/trajectory_clustering.py")
        print("         python scripts/data_processing/build_topology_from_clustering.py")
        return

    # 运行演示
    demo_position_based_impact_analysis()
    demo_react_integration()

    print("\n" + "=" * 70)
    print("演示完成")
    print("=" * 70)
    print("\n总结:")
    print("1. ✅ 拓扑图分析：准确识别影响范围")
    print("2. ✅ 航班影响预测：量化航班延误影响")
    print("3. ✅ ReAct集成：在推理中显示影响分析结果")
    print("4. ✅ 智能建议：基于分析结果生成处置建议")


if __name__ == "__main__":
    main()
