"""
测试拓扑图集成

验证真实拓扑图已成功集成到工具系统中
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.spatial.topology_loader import get_topology_loader
from tools.spatial.get_stand_location import GetStandLocationTool
from tools.spatial.calculate_impact_zone import CalculateImpactZoneTool
from tools.spatial.predict_flight_impact import PredictFlightImpactTool


def test_topology_loader():
    """测试拓扑加载器"""
    print("=" * 60)
    print("测试 1: 拓扑加载器")
    print("=" * 60)

    try:
        topology = get_topology_loader()
        stats = topology.get_statistics()

        print("✓ 拓扑图加载成功")
        print(f"  总节点数: {stats['total_nodes']}")
        print(f"  机位: {stats['stands']}")
        print(f"  跑道: {stats['runways']}")
        print(f"  滑行道: {stats['taxiways']}")
        print(f"  总边数: {stats['total_edges']}")

        # 测试查找节点
        stands = topology.get_nodes_by_type('stand')
        if stands:
            test_stand = stands[0]
            print(f"\n  测试机位查找: {test_stand}")
            stand_info = topology.get_stand_info(test_stand)
            if stand_info:
                print(f"    坐标: ({stand_info['lat']:.5f}, {stand_info['lon']:.5f})")
                print(f"    相邻滑行道: {stand_info['adjacent_taxiways']}")
                print(f"    最近跑道: {stand_info['nearest_runway']}")

        return True

    except Exception as e:
        print(f"✗ 拓扑图加载失败: {e}")
        return False


def test_get_stand_location():
    """测试机位位置查询工具"""
    print("\n" + "=" * 60)
    print("测试 2: 机位位置查询工具")
    print("=" * 60)

    try:
        topology = get_topology_loader()
        stands = topology.get_nodes_by_type('stand')

        if not stands:
            print("✗ 未找到机位节点")
            return False

        test_stand = stands[0]
        print(f"测试机位: {test_stand}")

        tool = GetStandLocationTool()

        # 创建模拟状态
        state = {
            "incident": {
                "position": test_stand
            }
        }

        result = tool.execute(state, {})

        print("\n工具执行结果:")
        print(result.get("observation", "无观测结果"))

        if "spatial_analysis" in result:
            print("\n✓ 空间分析成功")
            return True
        else:
            print("\n✗ 空间分析失败")
            return False

    except Exception as e:
        print(f"✗ 工具执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_calculate_impact_zone():
    """测试影响范围计算工具"""
    print("\n" + "=" * 60)
    print("测试 3: 影响范围计算工具")
    print("=" * 60)

    try:
        topology = get_topology_loader()
        stands = topology.get_nodes_by_type('stand')

        if not stands:
            print("✗ 未找到机位节点")
            return False

        test_stand = stands[0]
        print(f"测试场景: {test_stand} 发生燃油泄漏（高风险）")

        tool = CalculateImpactZoneTool()

        # 创建模拟状态
        state = {
            "incident": {
                "position": test_stand,
                "fluid_type": "FUEL"
            },
            "risk_assessment": {
                "level": "HIGH"
            }
        }

        result = tool.execute(state, {})

        print("\n工具执行结果:")
        print(result.get("observation", "无观测结果"))

        if "spatial_analysis" in result:
            analysis = result["spatial_analysis"]
            print("\n空间分析详情:")
            print(f"  起始节点: {analysis.get('anchor_node')}")
            print(f"  隔离区域: {len(analysis.get('isolated_nodes', []))} 个节点")
            print(f"  受影响机位: {len(analysis.get('affected_stands', []))} 个")
            print(f"  受影响滑行道: {len(analysis.get('affected_taxiways', []))} 个")
            print(f"  受影响跑道: {len(analysis.get('affected_runways', []))} 个")
            print(f"  扩散半径: {analysis.get('impact_radius')} 跳")
            print("\n✓ 影响范围计算成功")
            return True, result
        else:
            print("\n✗ 影响范围计算失败")
            return False, None

    except Exception as e:
        print(f"✗ 工具执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_predict_flight_impact():
    """测试航班影响预测工具"""
    print("\n" + "=" * 60)
    print("测试 4: 航班影响预测工具")
    print("=" * 60)

    # 首先执行影响范围计算
    success, impact_result = test_calculate_impact_zone()

    if not success or not impact_result:
        print("✗ 需要先成功计算影响范围")
        return False

    try:
        tool = PredictFlightImpactTool()

        # 使用上一步的结果
        state = {
            "incident": {
                "position": "stand_0",
                "fluid_type": "FUEL"
            },
            "risk_assessment": {
                "level": "HIGH"
            },
            "spatial_analysis": impact_result.get("spatial_analysis", {})
        }

        print("\n执行航班影响预测...")
        result = tool.execute(state, {"time_window": 2})

        print("\n工具执行结果:")
        print(result.get("observation", "无观测结果"))

        if "flight_impact" in result:
            impact = result["flight_impact"]
            stats = impact.get("statistics", {})
            print("\n航班影响统计:")
            print(f"  受影响航班总数: {stats.get('total_affected_flights', 0)}")
            print(f"  累计延误时间: {stats.get('total_delay_minutes', 0)} 分钟")
            print(f"  平均延误: {stats.get('average_delay_minutes', 0):.1f} 分钟")
            print("\n✓ 航班影响预测成功")
            return True
        else:
            print("\n✗ 航班影响预测失败")
            return False

    except Exception as e:
        print(f"✗ 工具执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_end_to_end_scenario():
    """端到端场景测试"""
    print("\n" + "=" * 60)
    print("测试 5: 端到端场景测试")
    print("=" * 60)

    # 使用真实机位ID
    topology = get_topology_loader()
    stands = topology.get_nodes_by_type('stand')
    test_stand = stands[0] if stands else "stand_0"

    print(f"场景: {test_stand}机位发生燃油泄漏，发动机运转中")
    print("=" * 60)

    try:
        # Step 1: 查询位置信息
        print(f"\n[步骤 1] 查询{test_stand}机位位置信息...")
        location_tool = GetStandLocationTool()
        state = {"incident": {"position": test_stand}}
        location_result = location_tool.execute(state, {})
        print(location_result.get("observation", ""))

        # Step 2: 计算影响范围
        print("\n[步骤 2] 计算影响范围（高风险燃油泄漏）...")
        state.update({
            "incident": {
                "position": test_stand,
                "fluid_type": "FUEL"
            },
            "risk_assessment": {
                "level": "HIGH"
            }
        })

        impact_tool = CalculateImpactZoneTool()
        impact_result = impact_tool.execute(state, {})
        print(impact_result.get("observation", ""))

        # 更新状态
        if "spatial_analysis" in impact_result:
            state["spatial_analysis"] = impact_result["spatial_analysis"]

        # Step 3: 预测航班影响
        print("\n[步骤 3] 预测未来2小时航班影响...")
        predict_tool = PredictFlightImpactTool()
        predict_result = predict_tool.execute(state, {"time_window": 2})
        print(predict_result.get("observation", ""))

        print("\n" + "=" * 60)
        print("✓ 端到端场景测试完成")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n✗ 端到端测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("机场拓扑图集成测试")
    print("=" * 60)

    tests = [
        ("拓扑加载器", test_topology_loader),
        ("机位位置查询", test_get_stand_location),
        ("影响范围计算", lambda: test_calculate_impact_zone()[0]),
        ("航班影响预测", test_predict_flight_impact),
        ("端到端场景", test_end_to_end_scenario),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name}测试发生异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # 打印总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status} - {name}")

    print("\n" + "=" * 60)
    print(f"测试结果: {passed}/{total} 通过")
    print("=" * 60)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
