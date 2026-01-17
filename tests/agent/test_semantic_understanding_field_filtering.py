"""
测试ENABLE_SEMANTIC_UNDERSTANDING=true时的字段过滤
"""
import pytest
from unittest.mock import patch
from agent.nodes.input_parser import input_parser_node
from agent.state import FSMState


@patch('agent.nodes.input_parser.settings.ENABLE_SEMANTIC_UNDERSTANDING', True)
@patch('agent.nodes.input_parser.understand_conversation')
def test_semantic_understanding_field_filtering(mock_understand):
    """测试语义理解模式下的字段过滤"""

    # Mock语义理解返回oil_spill字段（在FOD场景中应被过滤）
    mock_understand.return_value = {
        "extracted_facts": {
            "position": "18R",
            "fluid_type": "HYDRAULIC",  # oil_spill字段，应被过滤
            "engine_status": "STOPPED",  # oil_spill字段，应被过滤
            "fod_type": "METAL",         # FOD字段，应保留
            "presence": "REMOVED",       # FOD字段，应保留
        },
        "confidence_scores": {
            "position": 0.95,
            "fluid_type": 0.90,
            "engine_status": 0.85,
            "fod_type": 0.92,
            "presence": 0.88,
        },
        "semantic_issues": [],
        "conversation_summary": "测试摘要"
    }

    state = {
        "messages": [
            {
                "role": "user",
                "content": "跑道18R发现金属异物已移除"
            }
        ],
        "incident": {},
        "checklist": {},
        "scenario_type": "fod",  # FOD场景
        "fsm_state": FSMState.INIT.value,
        "reasoning_steps": [],
        "iteration_count": 1,
    }

    result = input_parser_node(state)

    # 验证场景保持
    assert result["scenario_type"] == "fod"

    # 验证提取的字段
    incident = result["incident"]

    # FOD字段应该被保留
    assert "fod_type" in incident
    assert "presence" in incident
    assert incident.get("position") is not None

    # oil_spill字段应该被过滤
    assert "fluid_type" not in incident, "语义理解不应在FOD场景中提取fluid_type"
    assert "engine_status" not in incident, "语义理解不应在FOD场景中提取engine_status"
    assert "continuous" not in incident, "语义理解不应在FOD场景中提取continuous"
    assert "leak_size" not in incident, "语义理解不应在FOD场景中提取leak_size"

    print("\n=== 语义理解字段过滤测试通过 ===")
    print(f"保留的FOD字段: {[k for k, v in incident.items() if v is not None and k in ['fod_type', 'presence', 'location_area']]}")
    print(f"所有字段: {list(incident.keys())}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
