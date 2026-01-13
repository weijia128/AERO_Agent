#!/usr/bin/env python3
"""
调试气象查询功能
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tools.information.get_weather import GetWeatherTool, load_weather_data


def main():
    print("=" * 80)
    print("气象查询调试")
    print("=" * 80)
    print()

    # 1. 检查数据加载
    print("1. 检查气象数据加载")
    print("-" * 80)
    df = load_weather_data()

    if df is None:
        print("❌ 气象数据未加载")
        return

    print(f"✅ 气象数据已加载: {len(df)} 条记录")
    print(f"   时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
    print(f"   可用位置: {', '.join(sorted(df['location_id'].unique()))}")
    print()

    # 2. 测试工具
    print("2. 测试气象查询工具")
    print("-" * 80)

    tool = GetWeatherTool()

    # 测试不同位置
    test_cases = [
        {"location": "05L", "desc": "直接查询05L"},
        {"location": "推荐", "desc": "自动选择（state中有501）"},
        {"location": "推荐", "desc": "自动选择（state中有601）"},
        {"location": "NORTH", "desc": "直接查询NORTH"},
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试 {i}: {test_case['desc']}")

        state = {"incident": {}}

        # 如果是"推荐"，需要设置位置
        if test_case["location"] == "推荐":
            if "501" in test_case["desc"]:
                state["incident"]["position"] = "501"
            elif "601" in test_case["desc"]:
                state["incident"]["position"] = "601"

        print(f"   输入: location={test_case['location']}", end="")
        if test_case["location"] == "推荐":
            print(f", incident.position={state['incident'].get('position')}")
        else:
            print()

        result = tool.execute(state, {"location": test_case["location"]})

        if "weather" in result:
            weather = result["weather"]
            print(f"   ✅ 查询成功")
            print(f"   - 观测点: {weather.get('location')}")
            print(f"   - 时间: {weather.get('timestamp')}")
            if weather.get('temperature') is not None:
                print(f"   - 温度: {weather['temperature']:.1f}°C")
            if weather.get('wind_speed') is not None:
                print(f"   - 风速: {weather['wind_speed']:.1f} m/s")
        else:
            print(f"   ❌ 查询失败")
            print(f"   - 消息: {result.get('observation', '无')[:100]}")

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
