#!/usr/bin/env python3
"""
测试自动气象查询功能

验证：
1. 当用户提供位置信息后，自动触发气象查询
2. 气象信息显示在上下文摘要中
3. 气象信息存储在 state.weather 中
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from agent.nodes.input_parser import input_parser_node
from agent.nodes.reasoning import build_context_summary, reasoning_node
from agent.nodes.tool_executor import tool_executor_node


def run_weather_pipeline(state: dict) -> dict:
    """运行 input_parser -> reasoning -> tool_executor 的自动气象流程"""
    parsed = input_parser_node(state)
    reasoning = reasoning_node({**state, **parsed})
    if reasoning.get("next_node") == "tool_executor":
        executed = tool_executor_node({**state, **parsed, **reasoning})
        return {**state, **parsed, **reasoning, **executed}
    return {**state, **parsed, **reasoning}


def test_auto_weather_query():
    """测试自动气象查询功能"""
    print("=" * 80)
    print("测试：自动气象查询功能")
    print("=" * 80)
    print()

    # 模拟初始状态
    state = {
        "messages": [
            {"role": "user", "content": "跑道05L发生燃油泄漏"}
        ],
        "scenario_type": "oil_spill",
        "incident": {},
        "checklist": {},
        "iteration_count": 0,
    }

    print("📍 用户输入: 跑道05L发生燃油泄漏")
    print()

    # 调用 input_parser_node
    print("⏳ 调用 input_parser_node...")
    result = run_weather_pipeline(state)

    # 检查结果
    print("\n" + "=" * 80)
    print("✅ 检查结果")
    print("=" * 80)

    # 1. 检查是否提取了位置信息
    position = result.get("incident", {}).get("position")
    print(f"\n1. 位置提取: {'✅ ' + position if position else '❌ 未提取到位置'}")

    # 2. 检查是否获取了气象信息
    weather = result.get("weather")
    if weather:
        print(f"\n2. 气象信息查询: ✅ 成功")
        print(f"   - 观测点: {weather.get('location')}")
        print(f"   - 观测时间: {weather.get('timestamp')}")
        if weather.get('temperature') is not None:
            print(f"   - 温度: {weather['temperature']:.1f}°C")
        if weather.get('wind_speed') is not None:
            print(f"   - 风速: {weather['wind_speed']:.1f} m/s")
    else:
        print(f"\n2. 气象信息查询: ❌ 未获取到气象数据")
        print("   提示: 请先运行 python scripts/data_processing/extract_awos_weather.py")

    # 3. 检查 enrichment_observation 是否包含气象信息
    enrichment = result.get("enrichment_observation", "")
    if "气象" in enrichment or "🌤️" in enrichment:
        print(f"\n3. 增强信息显示: ✅ 包含气象信息")
        # 只显示前200个字符
        preview = enrichment[:200] + "..." if len(enrichment) > 200 else enrichment
        print(f"   预览: {preview}")
    else:
        print(f"\n3. 增强信息显示: ❌ 未包含气象信息")

    # 4. 测试上下文摘要
    print(f"\n" + "=" * 80)
    print("4. 上下文摘要测试")
    print("=" * 80)

    # 更新 state 以包含气象信息
    test_state = state.copy()
    test_state.update(result)

    context = build_context_summary(test_state)
    print("\n📋 上下文摘要:")
    print(context)

    if "气象条件" in context:
        print("\n✅ 气象信息已包含在上下文摘要中")
    else:
        print("\n❌ 气象信息未包含在上下文摘要中")

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


def test_without_position():
    """测试没有位置信息的情况"""
    print("\n\n" + "=" * 80)
    print("测试：无位置信息的情况")
    print("=" * 80)
    print()

    state = {
        "messages": [
            {"role": "user", "content": "发生燃油泄漏"}
        ],
        "scenario_type": "oil_spill",
        "incident": {},
        "checklist": {},
        "iteration_count": 0,
    }

    print("📍 用户输入: 发生燃油泄漏（无位置信息）")
    print()

    print("⏳ 调用 input_parser_node...")
    result = run_weather_pipeline(state)

    weather = result.get("weather")
    if weather:
        print(f"❌ 不应该有气象信息，但获取到了: {weather}")
    else:
        print(f"✅ 正确：没有位置信息时不查询气象")

    print("\n" + "=" * 80)


def test_with_specific_location():
    """测试特定位置"""
    print("\n\n" + "=" * 80)
    print("测试：不同位置的气象查询")
    print("=" * 80)
    print()

    test_positions = ["跑道05L", "跑道06L", "跑道23R"]

    for position in test_positions:
        state = {
            "messages": [
                {"role": "user", "content": f"{position}发生燃油泄漏"}
            ],
            "scenario_type": "oil_spill",
            "incident": {},
            "checklist": {},
            "iteration_count": 0,
        }

        print(f"📍 测试位置: {position}")

        result = run_weather_pipeline(state)

        position_extracted = result.get("incident", {}).get("position")
        weather = result.get("weather")

        if position_extracted:
            print(f"   ✅ 位置提取成功: {position_extracted}")
        else:
            print(f"   ❌ 位置提取失败")

        if weather:
            print(f"   ✅ 气象查询成功: {weather.get('location')} - " +
                  f"风{weather.get('wind_speed', 0):.1f}m/s")
        else:
            print(f"   ❌ 气象查询失败")

        print()


def main():
    """主函数"""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "自动气象查询功能测试" + " " * 32 + "║")
    print("╚" + "═" * 78 + "╝")
    print()

    try:
        # 测试1: 基本功能
        test_auto_weather_query()

        # 测试2: 无位置信息
        test_without_position()

        # 测试3: 不同位置
        test_with_specific_location()

        print("\n" + "=" * 80)
        print("✅ 所有测试完成")
        print("=" * 80)
        print()

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
