"""
测试：位置影响分析工具集成到 input_parser

验证当用户提供漏油信息时，input_parser 是否自动调用 analyze_position_impact
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.nodes.input_parser import input_parser_node
from agent.state import create_initial_state


def test_runway_fuel_leak():
    """测试跑道燃油泄漏"""
    print("=" * 80)
    print("测试1: 跑道燃油泄漏（应该自动调用位置影响分析）")
    print("=" * 80)

    # 创建初始状态
    state = create_initial_state("test_session_001")

    # 模拟用户输入
    user_input = "501机位燃油泄漏，发动机运转中，持续泄漏"
    state["messages"] = [{"role": "user", "content": user_input}]

    # 执行 input_parser
    result = input_parser_node(state)

    # 检查结果
    print("\n【输入】")
    print(f"用户输入: {user_input}")

    print("\n【输出 - 提取的实体】")
    incident = result.get("incident", {})
    print(f"位置: {incident.get('position')}")
    print(f"油液类型: {incident.get('fluid_type')}")
    print(f"发动机状态: {incident.get('engine_status')}")
    print(f"是否持续: {incident.get('continuous')}")

    print("\n【输出 - 位置影响分析】")
    position_impact = result.get("position_impact_analysis", {})

    if position_impact:
        print("✅ 位置影响分析已自动调用")

        direct = position_impact.get("direct_impact", {})
        print(f"  - 设施类型: {direct.get('facility_type')}")
        print(f"  - 预计封闭时间: {direct.get('closure_time_minutes')} 分钟")
        print(f"  - 严重程度: {direct.get('severity_score'):.2f}/5.0")

        adjacent = position_impact.get("adjacent_impact", {})
        print(f"  - 相邻设施影响: {adjacent.get('total_adjacent')} 个")

        efficiency = position_impact.get("efficiency_impact", {})
        print(f"  - 运行效率: {efficiency.get('description', '')}")

        recommendations = position_impact.get("recommendations", [])
        print(f"  - 处置建议: {len(recommendations)} 条")

    else:
        print("❌ 位置影响分析未被调用")

    # 检查 reasoning_steps 中的 observation
    reasoning_steps = result.get("reasoning_steps", [])
    if reasoning_steps:
        observation = reasoning_steps[0].get("observation", "")
        if "位置影响分析完成" in observation:
            print("\n✅ observation 中包含位置影响分析结果")
        else:
            print("\n⚠️  observation 中未找到位置影响分析结果")

    print("\n")


def test_taxiway_hydraulic_leak():
    """测试滑行道液压油泄漏"""
    print("=" * 80)
    print("测试2: 滑行道液压油泄漏")
    print("=" * 80)

    state = create_initial_state("test_session_002")
    user_input = "滑行道19液压油泄漏"
    state["messages"] = [{"role": "user", "content": user_input}]

    result = input_parser_node(state)

    print(f"\n用户输入: {user_input}")

    position_impact = result.get("position_impact_analysis", {})
    if position_impact:
        direct = position_impact.get("direct_impact", {})
        print(f"✅ 设施类型: {direct.get('affected_facility')}")
        print(f"   预计封闭时间: {direct.get('closure_time_minutes')} 分钟")

        efficiency = position_impact.get("efficiency_impact", {})
        print(f"   运行效率: {efficiency.get('description', '')}")
    else:
        print("❌ 位置影响分析未被调用")

    print("\n")


def test_stand_oil_leak():
    """测试机位滑油泄漏"""
    print("=" * 80)
    print("测试3: 机位滑油泄漏")
    print("=" * 80)

    state = create_initial_state("test_session_003")
    user_input = "501机位发现滑油泄漏"
    state["messages"] = [{"role": "user", "content": user_input}]

    result = input_parser_node(state)

    print(f"\n用户输入: {user_input}")

    position_impact = result.get("position_impact_analysis", {})
    if position_impact:
        direct = position_impact.get("direct_impact", {})
        print(f"✅ 设施类型: {direct.get('affected_facility')}")
        print(f"   预计封闭时间: {direct.get('closure_time_minutes')} 分钟")

        adjacent = position_impact.get("adjacent_impact", {})
        count_by_type = adjacent.get("count_by_type", {})
        print(f"   相邻机位影响: {count_by_type.get('机位', 0)} 个")
    else:
        print("❌ 位置影响分析未被调用")

    print("\n")


def test_no_fluid_type():
    """测试没有油液类型的情况（应该不触发位置影响分析）"""
    print("=" * 80)
    print("测试4: 只提供位置，没有油液类型（不应触发位置影响分析）")
    print("=" * 80)

    state = create_initial_state("test_session_004")
    user_input = "501机位"
    state["messages"] = [{"role": "user", "content": user_input}]

    result = input_parser_node(state)

    print(f"\n用户输入: {user_input}")

    position_impact = result.get("position_impact_analysis", {})
    if position_impact:
        print("❌ 位置影响分析被调用了（不应该）")
    else:
        print("✅ 位置影响分析未被调用（符合预期）")

    print("\n")


if __name__ == "__main__":
    print("\n")
    print("=" * 80)
    print("位置影响分析集成测试")
    print("=" * 80)
    print("\n")

    # 运行测试
    test_runway_fuel_leak()
    test_taxiway_hydraulic_leak()
    test_stand_oil_leak()
    test_no_fluid_type()

    print("=" * 80)
    print("测试完成")
    print("=" * 80)
