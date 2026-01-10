"""
空间分析工具测试
"""
import pytest
from tools.spatial.topology_loader import get_topology_loader
from tools.spatial.calculate_impact_zone import CalculateImpactZoneTool


class TestTopologyLoader:
    """拓扑加载器测试"""

    def test_load_topology(self):
        """测试加载拓扑图"""
        topology = get_topology_loader()
        stats = topology.get_statistics()

        assert stats['total_nodes'] > 0
        assert stats['total_edges'] > 0
        assert stats['stands'] > 0
        assert stats['runways'] > 0
        assert stats['taxiways'] > 0

    def test_find_node_by_english_id(self):
        """测试通过英文ID查找节点"""
        topology = get_topology_loader()

        # 测试滑行道
        result = topology.find_nearest_node("taxiway_19")
        assert result is not None
        node_id, node_info = result
        assert node_id == "taxiway_19"
        assert node_info['type'] == 'taxiway'

        # 测试跑道
        result = topology.find_nearest_node("runway_0")
        assert result is not None
        node_id, node_info = result
        assert node_id == "runway_0"
        assert node_info['type'] == 'runway'

    def test_find_node_by_chinese_name(self):
        """测试通过中文名称查找节点"""
        topology = get_topology_loader()

        test_cases = [
            ("滑行道19", "taxiway_19", "taxiway"),
            ("跑道0", "runway_0", "runway"),
            ("机位0", "corrected_stand_0", "stand"),
            ("停机位0", "corrected_stand_0", "stand"),
        ]

        for chinese_name, expected_id, expected_type in test_cases:
            result = topology.find_nearest_node(chinese_name)
            assert result is not None, f"未找到节点: {chinese_name}"
            node_id, node_info = result
            assert node_id == expected_id, f"期望 {expected_id}，实际 {node_id}"
            assert node_info['type'] == expected_type

    def test_find_nonexistent_node(self):
        """测试查找不存在的节点"""
        topology = get_topology_loader()

        result = topology.find_nearest_node("滑行道999")
        assert result is None

        result = topology.find_nearest_node("机位999")
        assert result is None

    def test_get_stand_info(self):
        """测试获取机位信息"""
        topology = get_topology_loader()

        stand_info = topology.get_stand_info("corrected_stand_0")
        assert stand_info is not None
        assert stand_info['type'] == 'stand'
        assert 'lat' in stand_info
        assert 'lon' in stand_info
        assert 'adjacent_taxiways' in stand_info

    def test_bfs_spread(self):
        """测试BFS扩散算法"""
        topology = get_topology_loader()

        # 测试1跳扩散
        affected = topology.bfs_spread("taxiway_19", max_hops=1)
        assert "taxiway_19" in affected
        assert len(affected) > 1  # 应该包含至少一个相邻节点

        # 测试2跳扩散
        affected_2 = topology.bfs_spread("taxiway_19", max_hops=2)
        assert len(affected_2) > len(affected)


class TestCalculateImpactZone:
    """影响范围计算测试"""

    def test_calculate_impact_zone_with_english_position(self):
        """测试使用英文位置计算影响范围"""
        tool = CalculateImpactZoneTool()

        state = {
            "incident": {"position": "taxiway_19", "fluid_type": "OIL"},
            "risk_assessment": {"level": "MEDIUM"}
        }

        result = tool.execute(state, {
            "position": "taxiway_19",
            "fluid_type": "OIL",
            "risk_level": "MEDIUM"
        })

        assert "spatial_analysis" in result
        analysis = result["spatial_analysis"]
        assert analysis["anchor_node"] == "taxiway_19"
        assert analysis["anchor_node_type"] == "taxiway"
        assert len(analysis["isolated_nodes"]) > 0

    def test_calculate_impact_zone_with_chinese_position(self):
        """测试使用中文位置计算影响范围"""
        tool = CalculateImpactZoneTool()

        state = {
            "incident": {"position": "滑行道19", "fluid_type": "OIL"},
            "risk_assessment": {"level": "MEDIUM"}
        }

        result = tool.execute(state, {
            "position": "滑行道19",
            "fluid_type": "OIL",
            "risk_level": "MEDIUM"
        })

        assert "spatial_analysis" in result
        analysis = result["spatial_analysis"]
        assert analysis["anchor_node"] == "taxiway_19"
        assert analysis["anchor_node_type"] == "taxiway"
        assert len(analysis["isolated_nodes"]) > 0

    def test_calculate_impact_zone_invalid_position(self):
        """测试使用无效位置计算影响范围"""
        tool = CalculateImpactZoneTool()

        state = {
            "incident": {"position": "不存在的位置", "fluid_type": "OIL"},
            "risk_assessment": {"level": "MEDIUM"}
        }

        result = tool.execute(state, {
            "position": "不存在的位置",
            "fluid_type": "OIL",
            "risk_level": "MEDIUM"
        })

        assert "observation" in result
        assert "未在拓扑图中找到位置" in result["observation"]
        assert "spatial_analysis" not in result

    def test_calculate_impact_zone_different_risk_levels(self):
        """测试不同风险等级的影响范围"""
        tool = CalculateImpactZoneTool()

        base_state = {
            "incident": {"position": "滑行道19", "fluid_type": "FUEL"},
            "risk_assessment": {"level": "LOW"}
        }

        # 低风险
        result_low = tool.execute(base_state, {
            "position": "滑行道19",
            "fluid_type": "FUEL",
            "risk_level": "LOW"
        })

        # 中等风险
        result_medium = tool.execute(base_state, {
            "position": "滑行道19",
            "fluid_type": "FUEL",
            "risk_level": "MEDIUM"
        })

        # 高风险
        result_high = tool.execute(base_state, {
            "position": "滑行道19",
            "fluid_type": "FUEL",
            "risk_level": "HIGH"
        })

        # 验证风险等级越高，影响范围越大
        nodes_low = len(result_low["spatial_analysis"]["isolated_nodes"])
        nodes_medium = len(result_medium["spatial_analysis"]["isolated_nodes"])
        nodes_high = len(result_high["spatial_analysis"]["isolated_nodes"])

        assert nodes_low <= nodes_medium <= nodes_high


class TestAnalyzePositionImpact:
    """位置特定影响分析测试"""

    def test_analyze_runway_impact(self):
        """测试跑道漏油影响分析"""
        from tools.spatial.analyze_position_impact import AnalyzePositionImpactTool

        tool = AnalyzePositionImpactTool()

        state = {
            "incident": {"position": "runway_0", "fluid_type": "FUEL"},
            "risk_assessment": {"level": "HIGH"}
        }

        result = tool.execute(state, {})

        assert "observation" in result
        assert "位置影响分析完成" in result["observation"]
        assert "position_impact_analysis" in result

        analysis = result["position_impact_analysis"]
        assert analysis["node_type"] == "runway"
        assert analysis["fluid_type"] == "FUEL"
        assert analysis["direct_impact"]["facility_type"] == "runway"

        # 跑道漏油应该有更长的封闭时间
        assert analysis["direct_impact"]["closure_time_minutes"] > 100

        # 应该有处置建议
        assert len(analysis["recommendations"]) > 0

    def test_analyze_taxiway_impact(self):
        """测试滑行道漏油影响分析"""
        from tools.spatial.analyze_position_impact import AnalyzePositionImpactTool

        tool = AnalyzePositionImpactTool()

        state = {
            "incident": {"position": "taxiway_19", "fluid_type": "HYDRAULIC"},
            "risk_assessment": {"level": "MEDIUM"}
        }

        result = tool.execute(state, {})

        assert "observation" in result
        assert "position_impact_analysis" in result

        analysis = result["position_impact_analysis"]
        assert analysis["node_type"] == "taxiway"

        # 滑行道漏油的封闭时间应该比跑道短
        assert analysis["direct_impact"]["closure_time_minutes"] < 100

    def test_analyze_stand_impact(self):
        """测试机位漏油影响分析"""
        from tools.spatial.analyze_position_impact import AnalyzePositionImpactTool

        tool = AnalyzePositionImpactTool()

        state = {
            "incident": {"position": "corrected_stand_0", "fluid_type": "OIL"},
            "risk_assessment": {"level": "LOW"}
        }

        result = tool.execute(state, {})

        assert "observation" in result
        assert "position_impact_analysis" in result

        analysis = result["position_impact_analysis"]
        assert analysis["node_type"] == "stand"

        # 应该有相邻设施分析
        assert "adjacent_impact" in analysis
        assert "total_adjacent" in analysis["adjacent_impact"]

    def test_analyze_different_fluid_types(self):
        """测试不同油液类型的影响"""
        from tools.spatial.analyze_position_impact import AnalyzePositionImpactTool

        tool = AnalyzePositionImpactTool()

        fluid_types = ["FUEL", "HYDRAULIC", "OIL"]
        results = {}

        for fluid_type in fluid_types:
            state = {
                "incident": {"position": "runway_0", "fluid_type": fluid_type},
                "risk_assessment": {"level": "MEDIUM"}
            }
            result = tool.execute(state, {})
            results[fluid_type] = result["position_impact_analysis"]["direct_impact"]["closure_time_minutes"]

        # 燃油应该有最长的清理时间
        assert results["FUEL"] >= results["HYDRAULIC"]
        assert results["FUEL"] >= results["OIL"]

    def test_efficiency_impact_single_runway(self):
        """测试单跑道机场的效率影响"""
        from tools.spatial.analyze_position_impact import AnalyzePositionImpactTool

        tool = AnalyzePositionImpactTool()

        state = {
            "incident": {"position": "runway_0", "fluid_type": "FUEL"},
            "risk_assessment": {"level": "HIGH"}
        }

        result = tool.execute(state, {})

        analysis = result["position_impact_analysis"]
        efficiency = analysis["efficiency_impact"]

        # 单跑道机场应该有严重的延误
        if efficiency["impact_type"] == "single_runway_airport":
            assert efficiency["delay_per_flight"] >= 40
            assert efficiency["capacity_reduction_percent"] >= 70

    def test_position_impact_invalid_position(self):
        """测试无效位置的影响分析"""
        from tools.spatial.analyze_position_impact import AnalyzePositionImpactTool

        tool = AnalyzePositionImpactTool()

        state = {
            "incident": {"position": "不存在的位置", "fluid_type": "FUEL"},
            "risk_assessment": {"level": "MEDIUM"}
        }

        result = tool.execute(state, {})

        assert "observation" in result
        assert "未在拓扑图中找到位置" in result["observation"]
        assert "position_impact_analysis" not in result
