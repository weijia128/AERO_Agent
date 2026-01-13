#!/usr/bin/env python3
"""
测试鸟击场景中的自动气象查询
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from agent.nodes.input_parser import input_parser_node
from agent.nodes.reasoning import build_context_summary


def test_bird_strike_with_weather():
    """测试鸟击场景中的气象查询"""
    print("=" * 80)
    print("测试：鸟击场景 + 自动气象查询")
    print("=" * 80)
    print()

    # 模拟鸟击场景的用户输入
    user_input = "川航3349报告紧急情况，在起飞滑跑阶段于跑道27L发生确认鸟击，影响部位为左发"

    state = {
        "messages": [
            {"role": "user", "content": user_input}
        ],
        "scenario_type": "bird_strike",  # 鸟击场景
        "incident": {},
        "checklist": {},
        "iteration_count": 0,
    }

    print(f"📍 用户输入: {user_input}")
    print()

    # 调用 input_parser_node
    print("⏳ 调用 input_parser_node...")
    result = input_parser_node(state)

    # 检查结果
    print("\n" + "=" * 80)
    print("✅ 检查结果")
    print("=" * 80)

    # 1. 场景识别
    scenario = result.get("scenario_type", "")
    print(f"\n1. 场景识别: {scenario}")

    # 2. 位置提取
    position = result.get("incident", {}).get("position")
    print(f"\n2. 位置提取: {position}")

    # 3. 航班号
    flight_no = result.get("incident", {}).get("flight_no")
    print(f"   航班号: {flight_no}")

    # 4. 气象信息
    weather = result.get("weather", {})
    if weather:
        print(f"\n3. 气象信息查询: ✅ 成功")
        print(f"   观测点: {weather.get('location')}")
        print(f"   观测时间: {weather.get('timestamp')}")
        if weather.get('temperature') is not None:
            print(f"   温度: {weather['temperature']:.1f}°C")
        if weather.get('wind_speed') is not None:
            wind_dir = f"{weather.get('wind_direction', 0):.0f}°" if weather.get('wind_direction') else "未知"
            print(f"   风: {wind_dir} {weather['wind_speed']:.1f} m/s")
        if weather.get('qnh') is not None:
            print(f"   气压: {weather['qnh']:.0f} hPa")
    else:
        print(f"\n3. 气象信息查询: ❌ 未获取")

    # 5. 查看上下文摘要
    print(f"\n" + "=" * 80)
    print("4. 上下文摘要")
    print("=" * 80)

    test_state = state.copy()
    test_state.update(result)
    context = build_context_summary(test_state)

    print("\n📋 完整上下文:")
    print(context)

    if "气象条件" in context:
        print("\n✅ 气象信息已包含在上下文中")
    else:
        print("\n❌ 气象信息未包含在上下文中")

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


def test_position_mapping():
    """测试不同位置的映射"""
    print("\n\n" + "=" * 80)
    print("测试：位置映射")
    print("=" * 80)
    print()

    from tools.information.get_weather import GetWeatherTool

    tool = GetWeatherTool()

    test_positions = [
        ("501", "机位501"),
        ("601", "机位601"),
        ("跑道27L", "跑道27L"),
        ("23R", "23R跑道"),
        ("滑行道A3", "滑行道A3"),
    ]

    for position, desc in test_positions:
        state = {"incident": {"position": position}}
        print(f"\n测试: {desc} (position={position})")

        result = tool.execute(state, {"location": "推荐"})

        if "weather" in result:
            weather = result["weather"]
            wind_speed = weather.get('wind_speed')
            wind_str = f"风{wind_speed:.1f}m/s" if wind_speed is not None else "风: 无数据"
            print(f"  ✅ 查询成功: {weather.get('location')} - " + wind_str)
        else:
            print(f"  ❌ 查询失败")
            print(f"  消息: {result.get('observation', '无')[:100]}")


if __name__ == "__main__":
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 25 + "鸟击场景气象查询测试" + " " * 30 + "║")
    print("╚" + "═" * 78 + "╝")
    print()

    try:
        test_bird_strike_with_weather()
        test_position_mapping()

        print("\n" + "=" * 80)
        print("✅ 所有测试完成")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
