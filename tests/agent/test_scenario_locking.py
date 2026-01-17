"""
测试场景锁定和字段过滤机制
"""
import pytest
from agent.nodes.input_parser import (
    _get_scenario_field_keys,
    _build_field_descriptions_for_llm,
    extract_entities_hybrid,
)


def test_get_scenario_field_keys():
    """测试获取场景字段key列表"""
    # 测试FOD场景
    fod_fields = _get_scenario_field_keys("fod")
    assert "location_area" in fod_fields
    assert "fod_type" in fod_fields
    assert "presence" in fod_fields
    # 不应包含oil_spill字段
    assert "fluid_type" not in fod_fields
    assert "engine_status" not in fod_fields
    assert "continuous" not in fod_fields

    # 测试oil_spill场景
    oil_fields = _get_scenario_field_keys("oil_spill")
    assert "fluid_type" in oil_fields
    assert "engine_status" in oil_fields
    assert "continuous" in oil_fields
    # 不应包含FOD字段
    assert "fod_type" not in oil_fields
    assert "presence" not in oil_fields


def test_build_field_descriptions():
    """测试动态构建字段描述"""
    # FOD场景
    fod_desc = _build_field_descriptions_for_llm("fod")
    assert "location_area" in fod_desc
    assert "fod_type" in fod_desc
    assert "RUNWAY" in fod_desc  # 应该包含枚举选项
    assert "METAL" in fod_desc

    # 不应包含oil_spill字段
    assert "fluid_type" not in fod_desc
    assert "engine_status" not in fod_desc

    # oil_spill场景
    oil_desc = _build_field_descriptions_for_llm("oil_spill")
    assert "fluid_type" in oil_desc
    assert "engine_status" in oil_desc
    assert "FUEL" in oil_desc

    # 不应包含FOD字段
    assert "fod_type" not in oil_desc
    assert "presence" not in oil_desc


def test_extract_entities_hybrid_field_filtering():
    """测试混合提取时的字段过滤"""
    # 模拟FOD场景下的提取
    # 即使文本中提到了油液相关词汇，也不应提取fluid_type
    text = "已移除"  # 简单回答
    history = "用户: 跑道18R发现异物\n助手: 请确认FOD种类？\n用户: 金属"

    # 使用FOD场景提取
    entities = extract_entities_hybrid(text, history, scenario_type="fod")

    # 不应包含oil_spill场景的字段
    assert "fluid_type" not in entities
    assert "engine_status" not in entities
    assert "continuous" not in entities
    assert "leak_size" not in entities


def test_scenario_field_isolation():
    """测试场景字段隔离 - 核心测试用例"""
    # 这是复现bug的测试用例
    # 在FOD场景中，即使对话历史中有oil_spill相关信息，
    # 也不应该提取oil_spill字段

    text = "已移除"
    history = """
    用户: 国航1234，跑道09C发现异物
    助手: 请确认FOD种类？
    用户: 金属
    助手: FOD是否仍在道面？
    """

    # 使用FOD场景提取
    fod_entities = extract_entities_hybrid(text, history, scenario_type="fod")

    # 关键断言：不应提取任何oil_spill字段
    oil_spill_fields = {"fluid_type", "engine_status", "continuous", "leak_size"}
    extracted_keys = set(fod_entities.keys())

    assert not extracted_keys.intersection(oil_spill_fields), \
        f"FOD场景不应提取oil_spill字段，但提取了: {extracted_keys.intersection(oil_spill_fields)}"


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])
