#!/usr/bin/env python3
"""
端到端测试：自动气象查询在完整流程中的表现
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from agent.nodes.input_parser import input_parser_node
from agent.nodes.reasoning import build_context_summary


def test_end_to_end():
    """端到端测试"""
    print("=" * 80)
    print("端到端测试：自动气象查询")
    print("=" * 80)
    print()

    # 模拟用户消息
    user_input = "501机位发生燃油泄漏，发动机运转中，还在持续漏油"

    state = {
        "messages": [
            {"role": "user", "content": user_input}
        ],
        "scenario_type": "oil_spill",
        "incident": {},
        "checklist": {},
        "iteration_count": 0,
    }

    print(f"📍 用户输入: {user_input}")
    print()

    # 调用 input_parser_node
    print("⏳ 步骤1: 调用 input_parser_node...")
    result = input_parser_node(state)

    # 检查结果
    print("\n" + "=" * 80)
    print("步骤1结果：input_parser_node")
    print("=" * 80)

    # 1. 位置提取
    position = result.get("incident", {}).get("position")
    print(f"\n✅ 位置提取: {position}")

    # 2. 气象信息
    weather = result.get("weather", {})
    if weather:
        print(f"\n✅ 气象信息获取成功:")
        print(f"   - 观测点: {weather.get('location')}")
        print(f"   - 观测时间: {weather.get('timestamp')}")
        if weather.get('temperature') is not None:
            print(f"   - 温度: {weather['temperature']:.1f}°C")
        if weather.get('wind_speed') is not None:
            wind_dir = f"{weather.get('wind_direction', 0):.0f}°" if weather.get('wind_direction') else "未知"
            print(f"   - 风: {wind_dir} {weather['wind_speed']:.1f} m/s")
        if weather.get('qnh') is not None:
            print(f"   - 气压: {weather['qnh']:.0f} hPa")
    else:
        print(f"\n❌ 气象信息未获取")

    # 3. 增强信息
    enrichment = result.get("enrichment_observation", "")
    if enrichment and "气象" in enrichment:
        print(f"\n✅ 增强信息包含气象数据:")
        # 只显示气象部分
        weather_start = enrichment.find("🌤️")
        if weather_start >= 0:
            weather_section = enrichment[weather_start:weather_start+150]
            print(f"   {weather_section}...")
    else:
        print(f"\n❌ 增强信息不包含气象数据")

    # 4. 构建上下文摘要
    print(f"\n" + "=" * 80)
    print("步骤2: 构建上下文摘要")
    print("=" * 80)

    # 更新 state
    test_state = state.copy()
    test_state.update(result)

    context = build_context_summary(test_state)

    print("\n📋 完整上下文摘要:")
    print("-" * 80)
    print(context)
    print("-" * 80)

    if "气象条件" in context:
        print("\n✅ 气象信息已包含在上下文摘要中")

        # 提取气象条件行
        for line in context.split("\n"):
            if "气象条件" in line:
                print(f"   {line}")
    else:
        print("\n❌ 气象信息未包含在上下文摘要中")

    print("\n" + "=" * 80)
    print("✅ 端到端测试完成")
    print("=" * 80)

    # 总结
    print("\n📊 总结:")
    print(f"   ✅ 位置提取: {'成功' if position else '失败'}")
    print(f"   ✅ 气象查询: {'成功' if weather else '失败'}")
    print(f"   ✅ 增强信息: {'包含气象' if '气象' in enrichment else '不包含气象'}")
    print(f"   ✅ 上下文摘要: {'包含气象' if '气象条件' in context else '不包含气象'}")


if __name__ == "__main__":
    test_end_to_end()
