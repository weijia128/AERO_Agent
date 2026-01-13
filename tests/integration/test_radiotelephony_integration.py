"""
端到端测试: 验证航空读法规范化在 input_parser 中的集成
"""
import pytest
from agent.nodes.input_parser import input_parser_node
from agent.state import create_initial_state


class TestRadiotelephonyIntegration:
    """测试航空读法规范化的端到端集成"""

    def test_input_parser_with_runway_radiotelephony(self):
        """测试 input_parser 处理跑道航空读法"""
        # 初始化状态
        state = create_initial_state(
            session_id="test-runway",
            scenario_type="bird_strike",
            initial_message="跑道洞两左 疑似鸟击"
        )

        # 运行 input_parser
        result = input_parser_node(state)

        # 验证规范化结果
        assert result["incident"]["position"] == "02L"
        assert "normalization_result" in result
        print(f"\n✓ 跑道规范化成功: 跑道洞两左 → {result['incident']['position']}")

    def test_input_parser_with_stand_radiotelephony(self):
        """测试 input_parser 处理机位航空读法"""
        # 初始化状态
        state = create_initial_state(
            session_id="test-stand",
            scenario_type="oil_spill",
            initial_message="五洞幺机位 报告燃油泄漏"
        )

        # 运行 input_parser
        result = input_parser_node(state)

        # 验证规范化结果
        assert result["incident"]["position"] == "501"
        assert result["incident"]["fluid_type"] == "FUEL"
        print(f"\n✓ 机位规范化成功: 五洞幺机位 → {result['incident']['position']}")

    def test_input_parser_with_flight_radiotelephony(self):
        """测试 input_parser 处理航班号航空读法"""
        # 初始化状态
        state = create_initial_state(
            session_id="test-flight",
            scenario_type="oil_spill",
            initial_message="川航三幺拐拐 报告漏油"
        )

        # 运行 input_parser
        result = input_parser_node(state)

        # 验证规范化结果
        assert result["incident"]["flight_no"] == "3U3177"
        print(f"\n✓ 航班号规范化成功: 川航三幺拐拐 → {result['incident']['flight_no']}")

    def test_input_parser_with_complex_radiotelephony(self):
        """测试 input_parser 处理复杂航空读法"""
        # 初始化状态
        state = create_initial_state(
            session_id="test-complex",
            scenario_type="oil_spill",
            initial_message="川航三幺拐拐 五洞幺机位 报告燃油泄漏 发动机运转中"
        )

        # 运行 input_parser
        result = input_parser_node(state)

        # 验证规范化结果
        incident = result["incident"]
        assert incident["flight_no"] == "3U3177"
        assert incident["position"] == "501"
        assert incident["fluid_type"] == "FUEL"
        assert incident["engine_status"] == "RUNNING"

        print(f"\n✓ 复杂场景规范化成功:")
        print(f"  - 航班号: 川航三幺拐拐 → {incident['flight_no']}")
        print(f"  - 机位: 五洞幺机位 → {incident['position']}")
        print(f"  - 油液类型: {incident['fluid_type']}")
        print(f"  - 发动机: {incident['engine_status']}")

    def test_input_parser_fallback_on_error(self):
        """测试规范化失败时的 Fallback 机制"""
        # 初始化状态（使用非航空内容）
        state = create_initial_state(
            session_id="test-fallback",
            scenario_type="oil_spill",
            initial_message="今天天气不错"
        )

        # 运行 input_parser（应该不会崩溃）
        result = input_parser_node(state)

        # 验证系统正常运行
        assert "incident" in result
        assert "error" not in result
        print(f"\n✓ Fallback机制正常: 非航空内容不影响系统运行")

    def test_normalization_improves_spatial_analysis(self):
        """测试规范化提升空间分析准确性"""
        # 初始化状态
        state = create_initial_state(
            session_id="test-spatial",
            scenario_type="oil_spill",
            initial_message="五洞幺机位 燃油泄漏"
        )

        # 运行 input_parser
        result = input_parser_node(state)

        # 验证空间分析结果
        assert result["incident"]["position"] == "501"
        # 空间分析应该能够基于标准化的位置执行
        assert "spatial_analysis" in result or "enrichment_observation" in result

        print(f"\n✓ 规范化后空间分析正常执行")
        print(f"  - 标准化位置: {result['incident']['position']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
