#!/usr/bin/env python3
"""
get_weather 工具演示脚本

展示如何使用 get_weather 工具查询机场气象信息
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.information.get_weather import GetWeatherTool


def print_separator():
    """打印分隔线"""
    print("=" * 80)


def demo_query_weather_by_location():
    """演示1: 按位置查询气象"""
    print_separator()
    print("演示1: 查询特定位置的气象信息")
    print_separator()

    tool = GetWeatherTool()

    # 模拟state
    state = {
        "incident": {
            "position": "501",
            "fluid_type": "FUEL",
        }
    }

    # 查询05L跑道端的气象
    print("\n📍 查询位置: 05L")
    result = tool.execute(state, {"location": "05L"})
    print(result["observation"])

    print("\n" + "-" * 80 + "\n")

    # 查询NORTH区域的气象
    print("📍 查询位置: NORTH")
    result = tool.execute(state, {"location": "NORTH"})
    print(result["observation"])


def demo_query_weather_with_timestamp():
    """演示2: 按时间查询气象"""
    print_separator()
    print("演示2: 查询特定时间的气象信息")
    print_separator()

    tool = GetWeatherTool()
    state = {"incident": {}}

    # 查询05:30时刻的气象
    print("\n🕐 查询时间: 2026-01-06 05:30:00")
    print("📍 位置: 05L")
    result = tool.execute(
        state,
        {
            "location": "05L",
            "timestamp": "2026-01-06 05:30:00"
        }
    )
    print(result["observation"])


def demo_auto_location_selection():
    """演示3: 自动选择观测点"""
    print_separator()
    print("演示3: 自动选择观测点（基于事件位置）")
    print_separator()

    tool = GetWeatherTool()

    # 事件发生在501机位
    state = {
        "incident": {
            "position": "501",
            "fluid_type": "FUEL",
        }
    }

    print("\n✈️  事件位置: 501机位")
    print("🤖 使用 location='推荐' 自动选择最近的观测点")
    result = tool.execute(state, {"location": "推荐"})
    print(result["observation"])


def demo_multiple_locations():
    """演示4: 对比多个位置的气象"""
    print_separator()
    print("演示4: 对比多个位置的气象条件")
    print_separator()

    tool = GetWeatherTool()
    state = {"incident": {}}

    locations = ["05L", "06L", "NORTH", "SOUTH"]

    print("\n📍 各位置气象对比:")
    for loc in locations:
        print(f"\n【{loc}】")
        result = tool.execute(state, {"location": loc})
        # 只显示核心信息
        obs = result["observation"]
        lines = obs.split("\n")
        for line in lines[1:]:  # 跳过标题行
            if line.strip():
                print(f"  {line}")


def demo_weather_data_structure():
    """演示5: 访问结构化的气象数据"""
    print_separator()
    print("演示5: 访问结构化的气象数据（用于程序化处理）")
    print_separator()

    tool = GetWeatherTool()
    state = {"incident": {}}

    result = tool.execute(state, {"location": "05L"})

    if "weather" in result:
        weather = result["weather"]
        print("\n📊 结构化气象数据:")
        print(f"  位置: {weather.get('location')}")
        print(f"  时间: {weather.get('timestamp')}")

        if weather.get('temperature') is not None:
            print(f"  温度: {weather['temperature']}°C")

        if weather.get('wind_speed') is not None:
            print(f"  风速: {weather['wind_speed']} m/s")
            print(f"  风向: {weather.get('wind_direction')}°")

        if weather.get('qnh') is not None:
            print(f"  气压QNH: {weather['qnh']} hPa")

        print("\n💡 这些数据可以用于:")
        print("  - 风险评估计算")
        print("  - 决策逻辑判断")
        print("  - 报告生成")


def demo_error_handling():
    """演示6: 错误处理"""
    print_separator()
    print("演示6: 错误处理和边界情况")
    print_separator()

    tool = GetWeatherTool()
    state = {"incident": {}}

    # 缺少位置参数
    print("\n❌ 测试1: 缺少位置参数")
    result = tool.execute(state, {})
    print(result["observation"])

    # 无效的位置
    print("\n❌ 测试2: 无效的位置")
    result = tool.execute(state, {"location": "999Z"})
    print(result["observation"])

    # 无效的时间格式
    print("\n❌ 测试3: 无效的时间格式")
    result = tool.execute(
        state,
        {"location": "05L", "timestamp": "invalid-time"}
    )
    print(result["observation"])


def main():
    """主函数"""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "get_weather 工具演示" + " " * 38 + "║")
    print("╚" + "═" * 78 + "╝")
    print()

    # 检查气象数据是否可用
    from tools.information.get_weather import load_weather_data as load_weather_data_check
    df = load_weather_data_check()

    if df is None:
        print("❌ 警告: 未找到气象数据文件")
        print("   请先运行以下命令生成气象数据:")
        print("   python scripts/data_processing/extract_awos_weather.py")
        return

    print(f"✅ 已加载气象数据: {len(df)} 条记录")
    print(f"   时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
    print(f"   可用位置: {', '.join(sorted(df['location_id'].unique()))}")
    print()

    # 运行各个演示
    demo_query_weather_by_location()
    print("\n")

    demo_query_weather_with_timestamp()
    print("\n")

    demo_auto_location_selection()
    print("\n")

    demo_multiple_locations()
    print("\n")

    demo_weather_data_structure()
    print("\n")

    demo_error_handling()
    print("\n")

    print_separator()
    print("✅ 演示完成！")
    print_separator()
    print("\n💡 提示:")
    print("  1. 在Agent系统中，LLM会自动调用此工具")
    print("  2. 支持的位置: 05L, 05R, 06L, 06R, 23L, 23R, 24L, 24R, NORTH, SOUTH")
    print("  3. 使用 location='推荐' 可自动选择最近的观测点")
    print("  4. 时间参数可选，不提供则返回最新数据")
    print()


if __name__ == "__main__":
    main()
