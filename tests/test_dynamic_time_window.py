"""
测试基于航班号的动态时间窗口功能

测试流程：
1. 用户提供航班号（例如 CES2876）
2. 使用 flight_plan_lookup 查询航班信息，获取时间
3. 使用 predict_flight_impact 基于查询到的时间分析影响
4. 验证时间窗口是否正确使用航班时间
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from tools.information.flight_plan_lookup import FlightPlanLookupTool
from tools.spatial.predict_flight_impact import PredictFlightImpactTool
from tools.assessment.analyze_spill_comprehensive import AnalyzeSpillComprehensiveTool


def test_flight_plan_lookup_extracts_time():
    """测试 flight_plan_lookup 是否正确提取时间"""
    print("\n" + "=" * 80)
    print("测试1: flight_plan_lookup 提取航班时间")
    print("=" * 80)

    tool = FlightPlanLookupTool()
    state = {}

    # 查询一个已知航班（CES2876 在数据集中）
    result = tool.execute(state, {"flight_no": "CES2876"})

    print("\n查询结果:")
    print(f"  观测: {result.get('observation', '')}")

    # 验证 state 中是否有 reference_flight
    assert "reference_flight" in state, "state 中应该包含 reference_flight"

    ref_flight = state["reference_flight"]
    print(f"\n写入 state 的参考航班信息:")
    print(f"  callsign: {ref_flight.get('callsign')}")
    print(f"  stand: {ref_flight.get('stand')}")
    print(f"  runway: {ref_flight.get('runway')}")
    print(f"  reference_time: {ref_flight.get('reference_time')}")

    # 验证时间字段
    assert ref_flight.get("reference_time"), "reference_time 应该存在"
    print("\n✓ 测试通过：flight_plan_lookup 成功提取时间并写入 state")

    return state


def test_predict_flight_impact_uses_reference_time(state_with_reference):
    """测试 predict_flight_impact 是否使用参考航班时间"""
    print("\n" + "=" * 80)
    print("测试2: predict_flight_impact 使用参考航班时间")
    print("=" * 80)

    # 准备 state（包含空间分析结果）
    state = state_with_reference.copy()
    state["incident"] = {
        "position": "501",
        "fluid_type": "FUEL",
        "leak_size": "LARGE",
    }
    state["spatial_analysis"] = {
        "affected_stands": ["stand_501", "stand_502"],
        "affected_taxiways": ["taxiway_A3"],
        "affected_runways": ["runway_24R"],
        "impact_radius": 2
    }

    tool = PredictFlightImpactTool()

    # 执行预测（使用清理时间 60 分钟 + 30 分钟缓冲 = 1.5 小时）
    result = tool.execute(state, {"time_window": 1.5})

    print("\n预测结果:")
    print(result.get("observation", ""))

    # 验证时间窗口
    flight_impact = result.get("flight_impact", {})
    time_window = flight_impact.get("time_window", {})

    print(f"\n时间窗口:")
    print(f"  start: {time_window.get('start')}")
    print(f"  end: {time_window.get('end')}")

    # 验证起始时间应该是参考航班的时间
    ref_time = state["reference_flight"]["reference_time"]
    start_time = time_window.get("start", "")

    # 将 ref_time 转换为 ISO 格式（添加 "T"）
    ref_time_iso = ref_time.replace(" ", "T") if " " in ref_time else ref_time

    assert start_time == ref_time_iso, \
        f"时间窗口起点应该是参考航班时间。预期: {ref_time_iso}, 实际: {start_time}"

    print("\n✓ 测试通过：predict_flight_impact 正确使用参考航班时间")


def test_comprehensive_analysis_with_reference_flight():
    """测试综合分析工具是否在报告中显示参考航班"""
    print("\n" + "=" * 80)
    print("测试3: 综合分析显示参考航班信息")
    print("=" * 80)

    # 初始化工具
    lookup_tool = FlightPlanLookupTool()
    comprehensive_tool = AnalyzeSpillComprehensiveTool()

    # 第1步：查询航班信息
    state = {
        "incident": {
            "position": "501",
            "fluid_type": "FUEL",
            "leak_size": "LARGE",
        },
        "risk_assessment": {
            "risk_level": "HIGH"
        }
    }

    # 查询参考航班
    lookup_result = lookup_tool.execute(state, {"flight_no": "CES2876"})
    print(f"\n查询航班: {lookup_result.get('observation', '')}")

    # 第2步：执行综合分析
    print("\n开始综合分析...\n")
    result = comprehensive_tool.execute(state, {})

    # 输出观测结果
    observation = result.get("observation", "")
    print(observation)

    # 验证报告中是否包含参考航班信息
    assert "参考航班" in observation or "CES2876" in observation, \
        "综合分析报告应该包含参考航班信息"

    print("\n✓ 测试通过：综合分析报告正确显示参考航班信息")


def test_backward_compatibility():
    """测试向后兼容性：没有参考航班时应该使用默认时间"""
    print("\n" + "=" * 80)
    print("测试4: 向后兼容性（无参考航班时使用默认时间）")
    print("=" * 80)

    tool = PredictFlightImpactTool()

    # 不提供参考航班，只提供事故信息
    state = {
        "incident": {
            "position": "501",
            "fluid_type": "FUEL",
            "incident_time": "2026-01-06 11:00:00"
        },
        "spatial_analysis": {
            "affected_stands": ["stand_501"],
            "affected_taxiways": [],
            "affected_runways": [],
            "impact_radius": 1
        }
    }

    result = tool.execute(state, {"time_window": 1.0})

    flight_impact = result.get("flight_impact", {})
    time_window = flight_impact.get("time_window", {})

    print(f"\n时间窗口（基于 incident_time）:")
    print(f"  start: {time_window.get('start')}")
    print(f"  end: {time_window.get('end')}")

    # 验证使用的是 incident_time
    assert time_window.get("start") == "2026-01-06T11:00:00", \
        "没有参考航班时应该使用 incident_time"

    print("\n✓ 测试通过：向后兼容性正常，无参考航班时使用 incident_time")


def main():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("开始测试基于航班号的动态时间窗口功能")
    print("=" * 80)

    try:
        # 测试1: flight_plan_lookup 提取时间
        state_with_reference = test_flight_plan_lookup_extracts_time()

        # 测试2: predict_flight_impact 使用参考时间
        test_predict_flight_impact_uses_reference_time(state_with_reference)

        # 测试3: 综合分析显示参考航班
        test_comprehensive_analysis_with_reference_flight()

        # 测试4: 向后兼容性
        test_backward_compatibility()

        print("\n" + "=" * 80)
        print("所有测试通过 ✓")
        print("=" * 80)

    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        raise
    except Exception as e:
        print(f"\n✗ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
