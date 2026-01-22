"""
测试 smart_ask 工具正确处理航班号状态

确保当航班号已从初次报告中提取后，不会重复询问。
"""
import pytest
from tools.information.smart_ask import SmartAskTool, get_missing_fields
from agent.nodes.input_parser import update_checklist


def test_flight_no_extracted_should_not_ask_again():
    """测试：当航班号已提取时，不应再次询问"""
    # 模拟状态：已提取到航班号
    incident = {
        "flight_no_display": "东航2392",
        "flight_no": "MU2392",
        "fluid_type": "OIL",
        "continuous": True,
    }

    checklist_template = {
        "flight_no": False,
        "fluid_type": False,
        "continuous": False,
        "engine_status": False,
        "position": False,
    }

    # 更新 checklist
    checklist = update_checklist(incident, checklist_template)

    # 航班号应该被标记为已收集
    assert checklist["flight_no"] is True, "航班号应该被标记为已收集"

    # 获取缺失字段
    missing = get_missing_fields(incident, checklist, "oil_spill")

    # 航班号不应该在缺失列表中
    assert "flight_no" not in missing, "航班号不应该在缺失字段列表中"

    # 只应该缺失 engine_status 和 position
    assert set(missing) == {"engine_status", "position"}


def test_smart_ask_with_flight_no_should_have_callsign_prefix():
    """测试：问题应该包含航班号前缀（符合航空通话规范）"""
    state = {
        "incident": {
            "flight_no_display": "东航2392",
            "flight_no": "MU2392",
            "fluid_type": "OIL",
            "continuous": True,
        },
        "checklist": {
            "flight_no": True,
            "fluid_type": True,
            "continuous": True,
            "engine_status": False,
            "position": False,
        },
        "scenario_type": "oil_spill",
    }

    tool = SmartAskTool()
    result = tool.execute(state, {})

    question = result.get("question", "")

    # 问题不应该询问航班号
    assert "机号" not in question, "不应该询问机号"
    assert "航班号" not in question or "报告你航班号" not in question, "不应该询问航班号"

    # 问题应该包含航班号前缀
    assert "东航2392" in question or "MU2392" in question, "问题应该包含航班号前缀"


def test_flight_no_display_only_should_also_mark_as_collected():
    """测试：即使只有 flight_no_display，也应该标记为已收集"""
    incident = {
        "flight_no_display": "东航2392",
        # 注意：没有 flight_no（ICAO格式）
        "fluid_type": "OIL",
    }

    checklist_template = {
        "flight_no": False,
        "fluid_type": False,
        "continuous": False,
        "engine_status": False,
        "position": False,
    }

    checklist = update_checklist(incident, checklist_template)

    # 即使只有 flight_no_display，也应该标记为已收集
    assert checklist["flight_no"] is True, "flight_no_display 应该触发 flight_no 标记"

    missing = get_missing_fields(incident, checklist, "oil_spill")
    assert "flight_no" not in missing, "flight_no 不应该在缺失列表中"


def test_no_flight_no_should_ask():
    """测试：当真的没有航班号时，应该询问"""
    incident = {
        "fluid_type": "OIL",
        "continuous": True,
    }

    checklist_template = {
        "flight_no": False,
        "fluid_type": False,
        "continuous": False,
        "engine_status": False,
        "position": False,
    }

    checklist = update_checklist(incident, checklist_template)

    # 航班号应该未收集
    assert checklist["flight_no"] is False

    missing = get_missing_fields(incident, checklist, "oil_spill")

    # 航班号应该在缺失列表中
    assert "flight_no" in missing, "缺少航班号时应该询问"
