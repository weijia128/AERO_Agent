"""
演示：位置特定影响分析

展示漏油发生在不同位置（机位/滑行道/跑道）时对机场运行的不同影响
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.spatial.analyze_position_impact import AnalyzePositionImpactTool


def demo_position_impact_analysis():
    """演示不同位置的漏油影响分析"""
    print("=" * 80)
    print("位置特定影响分析演示")
    print("=" * 80)
    print()

    # 定义测试场景
    scenarios = [
        {
            "name": "场景1: 跑道燃油泄漏（高危）",
            "position": "runway_0",
            "fluid_type": "FUEL",
            "risk_level": "HIGH",
            "description": "最严重的漏油场景，跑道需要关闭"
        },
        {
            "name": "场景2: 关键滑行道液压油泄漏（中危）",
            "position": "taxiway_19",
            "fluid_type": "HYDRAULIC",
            "risk_level": "MEDIUM",
            "description": "滑行道封闭，航班需要绕行"
        },
        {
            "name": "场景3: 高使用率机位滑油泄漏（低危）",
            "position": "corrected_stand_0",
            "fluid_type": "OIL",
            "risk_level": "LOW",
            "description": "机位暂时无法使用，影响相对较小"
        },
        {
            "name": "场景4: 跑道液压油泄漏（中危）",
            "position": "runway_0",
            "fluid_type": "HYDRAULIC",
            "risk_level": "MEDIUM",
            "description": "对比不同油液类型在跑道的影响"
        },
        {
            "name": "场景5: 普通机位燃油泄漏（高危）",
            "position": "corrected_stand_5",
            "fluid_type": "FUEL",
            "risk_level": "HIGH",
            "description": "机位燃油泄漏，需要疏散和消防处置"
        },
    ]

    tool = AnalyzePositionImpactTool()

    for i, scenario in enumerate(scenarios, 1):
        print("=" * 80)
        print(f"{scenario['name']}")
        print(f"{scenario['description']}")
        print("=" * 80)

        # 创建模拟状态
        state = {
            "incident": {
                "position": scenario["position"],
                "fluid_type": scenario["fluid_type"]
            },
            "risk_assessment": {
                "level": scenario["risk_level"]
            }
        }

        # 执行分析
        result = tool.execute(state, {})

        # 输出结果
        if result.get("observation"):
            print(result["observation"])
        else:
            print("分析失败")

        print("\n" * 2)

    print("=" * 80)
    print("演示完成")
    print("=" * 80)


def demo_comparison_summary():
    """生成对比总结"""
    print("\n")
    print("=" * 80)
    print("位置影响对比总结")
    print("=" * 80)
    print()

    scenarios = [
        ("runway_0", "FUEL", "HIGH", "跑道"),
        ("taxiway_19", "FUEL", "HIGH", "滑行道"),
        ("corrected_stand_0", "FUEL", "HIGH", "机位"),
    ]

    tool = AnalyzePositionImpactTool()

    print(f"{'位置类型':<10} {'油液类型':<10} {'风险等级':<10} {'封闭时间(分钟)':<15} {'严重程度':<10}")
    print("-" * 80)

    for position, fluid_type, risk_level, pos_type in scenarios:
        state = {
            "incident": {
                "position": position,
                "fluid_type": fluid_type
            },
            "risk_assessment": {"level": risk_level}
        }

        result = tool.execute(state, {})

        if result.get("position_impact_analysis"):
            analysis = result["position_impact_analysis"]
            direct = analysis["direct_impact"]

            print(f"{pos_type:<10} {fluid_type:<10} {risk_level:<10} "
                  f"{direct['closure_time_minutes']:<15} {direct['severity_score']:<10.2f}")

    print()
    print("结论:")
    print("1. 跑道漏油影响最严重，封闭时间最长（120-180分钟）")
    print("2. 滑行道漏油影响中等，导致绕行延误（30-60分钟）")
    print("3. 机位漏油影响相对较小，主要是机位重新分配（45-90分钟）")
    print()


if __name__ == "__main__":
    # 运行完整演示
    demo_position_impact_analysis()

    # 显示对比总结
    demo_comparison_summary()
