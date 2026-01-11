# -*- coding: utf-8 -*-
"""
对话风格与管制通话要求相关测试
"""
from config.airline_codes import format_callsign_display
from scenarios.base import ScenarioRegistry
from tools.information.smart_ask import build_combined_question, group_missing_fields, SmartAskTool


def test_callsign_display_variants():
    """呼号格式化应符合管制通话习惯"""
    assert format_callsign_display("南航1234") == "南航1234"
    assert format_callsign_display("CZ1234") == "南航1234"
    assert format_callsign_display("CSN1234") == "南航1234"
    assert format_callsign_display("3U3349") == "川航3349"


def test_smart_ask_prefix_when_callsign_known():
    """已知机号时必须带呼号前缀"""
    question = build_combined_question(["position", "fluid_type"], "CZ1234")
    assert question.startswith("南航1234，")
    assert "机长" not in question
    assert "请问" not in question
    assert "麻烦" not in question


def test_smart_ask_no_prefix_for_flight_no():
    """未知机号时不应出现呼号前缀"""
    question = build_combined_question(["flight_no"], "CZ1234")
    assert question == "报告你机号"
    assert not question.startswith("南航1234，")


def test_group_missing_fields_max_two():
    """缺失字段分组每组最多两个"""
    groups = group_missing_fields(
        ["position", "fluid_type", "engine_status", "continuous"]
    )
    assert groups
    assert all(len(group) <= 2 for group in groups)


def test_prompt_ask_prompts_style():
    """场景配置中的追问语气应符合管制用语"""
    scenario = ScenarioRegistry.get("oil_spill")
    assert scenario is not None

    ask_prompts = scenario.prompt_config.get("ask_prompts", {})
    assert ask_prompts.get("flight_no") == "报告你机号"

    banned_terms = ["请问", "麻烦", "您"]
    for prompt in ask_prompts.values():
        assert all(term not in prompt for term in banned_terms)


def test_smart_ask_bird_strike_fields():
    """鸟击场景下仅收集鸟击必填字段，不应回退到漏油字段"""
    tool = SmartAskTool()
    state = {
        "scenario_type": "bird_strike",
        "incident": {
            "flight_no": "3U3349",
            "flight_no_display": "川航3349",
            "position": "滑行道12",
            "event_type": "确认鸟击",
            "affected_part": "左发",
            # 未填 current_status/crew_request
        },
        "checklist": {
            "flight_no": True,
            "position": True,
            "event_type": True,
            "affected_part": True,
            "current_status": False,
            "crew_request": False,
        },
    }
    result = tool.execute(state)
    assert result["missing_fields"] == ["current_status", "crew_request"]
    assert "油" not in (result.get("question") or "")
