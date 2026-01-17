"""
FOD场景集成测试 - 模拟真实对话流程
"""
import pytest
from agent.nodes.input_parser import input_parser_node
from agent.state import FSMState


def test_fod_scenario_conversation_flow():
    """测试FOD场景的完整对话流程，验证场景锁定和字段过滤"""

    # ========== 第一轮：初始报告 ==========
    state_1 = {
        "messages": [
            {
                "role": "user",
                "content": "天府机坪，场务巡查汇报，在跑道幺八右附近，发现异物"
            }
        ],
        "incident": {},
        "checklist": {},
        "scenario_type": "",  # 初始场景未确定
        "fsm_state": FSMState.INIT.value,
        "reasoning_steps": [],
        "iteration_count": 1,
    }

    result_1 = input_parser_node(state_1)

    # 验证场景识别
    assert result_1["scenario_type"] == "fod", "应识别为FOD场景"

    # 验证提取的字段
    incident_1 = result_1["incident"]
    assert incident_1.get("position") == "18R", f"位置应为18R，实际为: {incident_1.get('position')}"
    assert incident_1.get("location_area") == "RUNWAY", "位置类别应为RUNWAY"

    # 关键：不应提取oil_spill字段
    assert "fluid_type" not in incident_1, "FOD场景不应提取fluid_type"
    assert "engine_status" not in incident_1, "FOD场景不应提取engine_status"
    assert "continuous" not in incident_1, "FOD场景不应提取continuous"

    # ========== 第二轮：回答FOD种类 ==========
    state_2 = {
        "messages": [
            {
                "role": "user",
                "content": "天府机坪，场务巡查汇报，在跑道幺八右附近，发现异物"
            },
            {
                "role": "assistant",
                "content": "请确认 FOD 种类（金属/塑料橡胶/石块砂石/液体/不明）？"
            },
            {
                "role": "user",
                "content": "金属"
            }
        ],
        "incident": incident_1,
        "checklist": result_1["checklist"],
        "scenario_type": "fod",  # 场景已确定
        "fsm_state": FSMState.INIT.value,
        "reasoning_steps": result_1["reasoning_steps"],
        "iteration_count": 2,
    }

    result_2 = input_parser_node(state_2)

    # 验证场景锁定
    assert result_2["scenario_type"] == "fod", "场景应保持为FOD"

    # 验证提取的字段
    incident_2 = result_2["incident"]
    assert incident_2.get("fod_type") == "METAL", "FOD种类应为METAL"

    # 关键：仍然不应提取oil_spill字段
    assert "fluid_type" not in incident_2, "FOD场景不应提取fluid_type"
    assert "engine_status" not in incident_2, "FOD场景不应提取engine_status"

    # ========== 第三轮：回答是否仍在道面（复现bug的关键场景）==========
    state_3 = {
        "messages": [
            {
                "role": "user",
                "content": "天府机坪，场务巡查汇报，在跑道幺八右附近，发现异物"
            },
            {
                "role": "assistant",
                "content": "请确认 FOD 种类（金属/塑料橡胶/石块砂石/液体/不明）？"
            },
            {
                "role": "user",
                "content": "金属"
            },
            {
                "role": "assistant",
                "content": "FOD 是否仍在道面？（仍在/已移除/被风吹动）"
            },
            {
                "role": "user",
                "content": "已移除"  # 这是触发bug的输入
            }
        ],
        "incident": incident_2,
        "checklist": result_2["checklist"],
        "scenario_type": "fod",  # 场景已锁定
        "fsm_state": FSMState.INIT.value,
        "reasoning_steps": result_2["reasoning_steps"],
        "iteration_count": 3,
    }

    result_3 = input_parser_node(state_3)

    # 验证场景仍然锁定
    assert result_3["scenario_type"] == "fod", "场景应保持为FOD"

    # 验证提取的字段
    incident_3 = result_3["incident"]

    # 打印详细信息用于调试
    print("\n=== 第三轮提取结果 ===")
    print(f"输入文本: '已移除'")
    print(f"场景类型: {result_3['scenario_type']}")
    print(f"incident_3 所有字段:")
    for k, v in incident_3.items():
        print(f"  {k}: {v}")

    assert incident_3.get("presence") == "REMOVED", f"presence应为REMOVED，实际为: {incident_3.get('presence')}"

    # 核心断言：这是bug修复的关键 - 不应提取oil_spill字段
    oil_spill_fields = {"fluid_type", "engine_status", "continuous", "leak_size"}
    incident_3_keys = set(incident_3.keys())

    for field in oil_spill_fields:
        assert field not in incident_3, \
            f"FOD场景在回答'已移除'后不应提取oil_spill字段 {field}，但实际提取了: {incident_3.get(field)}"

    # 打印最终提取的字段（用于调试）
    print("\n=== 最终提取的字段 ===")
    for key, value in incident_3.items():
        if value is not None:
            print(f"{key}: {value}")

    # 验证只包含FOD场景的字段
    fod_specific_fields = {"location_area", "fod_type", "presence", "fod_size", "ops_impact", "related_event"}
    common_fields = {"position", "position_display", "flight_no", "flight_no_display", "report_time", "reported_by"}
    allowed_fields = fod_specific_fields | common_fields

    for key in incident_3_keys:
        if incident_3[key] is not None:
            assert key in allowed_fields, \
                f"字段 {key} 不属于FOD场景或通用字段，可能是其他场景的字段泄漏"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
