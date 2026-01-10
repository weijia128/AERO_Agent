#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Bug修复验证测试

测试问题1：位置重复提问
测试问题2：P1/P2字段区分
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.nodes.input_parser import extract_entities
from tools.information.smart_ask import get_missing_fields


def test_position_extraction():
    """测试位置实体提取"""
    print("=" * 60)
    print("测试1：位置实体提取")
    print("=" * 60)

    test_cases = [
        ("跑道2", "跑道2"),
        ("滑行道19", "滑行道19"),
        ("跑道2 发动机关闭", "跑道2"),
        ("我在滑行道19", "滑行道19"),
        ("501机位", "501"),
        ("机位501", "501"),
        ("501", "501"),
        ("在TWY A3", "TWYA3"),
    ]

    all_passed = True
    for input_text, expected in test_cases:
        entities = extract_entities(input_text)
        extracted = entities.get("position")

        status = "✓" if extracted == expected else "✗"
        if extracted != expected:
            all_passed = False

        print(f"{status} 输入: '{input_text}'")
        print(f"   期望: {expected}")
        print(f"   实际: {extracted}")
        print()

    return all_passed


def test_get_missing_fields():
    """测试缺失字段判断逻辑"""
    print("=" * 60)
    print("测试2：缺失字段判断（修复后应只检查值，不检查checklist标记）")
    print("=" * 60)

    # 场景1：incident有值，但checklist未标记（修复前会误判为缺失）
    incident1 = {
        "fluid_type": "FUEL",
        "position": "跑道2",
        "engine_status": "STOPPED",
        "continuous": True,
    }
    checklist1 = {
        "fluid_type": True,
        "position": False,  # 标记为未收集（但实际有值）
        "engine_status": True,
        "continuous": True,
    }

    missing1 = get_missing_fields(incident1, checklist1)

    print("场景1：incident有值，但checklist标记延迟")
    print(f"  incident: {incident1}")
    print(f"  checklist: {checklist1}")
    print(f"  缺失字段: {missing1}")
    print(f"  预期结果: [] (空列表，因为所有字段都有值)")
    print(f"  {'✓ 通过' if missing1 == [] else '✗ 失败'}")
    print()

    # 场景2：incident真的缺少值
    incident2 = {
        "fluid_type": "FUEL",
        "position": None,  # 真的缺失
        "engine_status": "STOPPED",
        "continuous": True,
    }
    checklist2 = {
        "fluid_type": True,
        "position": False,
        "engine_status": True,
        "continuous": True,
    }

    missing2 = get_missing_fields(incident2, checklist2)

    print("场景2：incident真的缺少position值")
    print(f"  incident: {incident2}")
    print(f"  checklist: {checklist2}")
    print(f"  缺失字段: {missing2}")
    print(f"  预期结果: ['position']")
    print(f"  {'✓ 通过' if missing2 == ['position'] else '✗ 失败'}")
    print()

    return missing1 == [] and missing2 == ["position"]


def test_integration():
    """集成测试：完整的实体提取 + 缺失字段判断流程"""
    print("=" * 60)
    print("测试3：集成测试（完整流程）")
    print("=" * 60)

    # 模拟用户对话流程
    print("模拟对话流程：")
    print("  用户: 川航3349报告紧急情况，右侧发动机有滑油泄漏，可见持续滴漏")
    print()

    # 第1轮：提取初始信息
    msg1 = "川航3349报告紧急情况，右侧发动机有滑油泄漏，可见持续滴漏"
    entities1 = extract_entities(msg1)

    incident = {
        "flight_no": entities1.get("flight_no"),
        "fluid_type": entities1.get("fluid_type"),
        "position": entities1.get("position"),
        "engine_status": entities1.get("engine_status"),
        "continuous": entities1.get("continuous"),
    }

    print(f"第1轮提取: {incident}")

    checklist = {k: v is not None for k, v in incident.items()}
    missing1 = get_missing_fields(incident, checklist)

    print(f"缺失字段: {missing1}")
    print(f"系统应询问: position, engine_status")
    print()

    # 第2轮：用户回答位置和发动机状态
    print("  用户: 跑道2 发动机关闭")
    msg2 = "跑道2 发动机关闭"
    entities2 = extract_entities(msg2)

    incident.update({
        "position": entities2.get("position") or incident.get("position"),
        "engine_status": entities2.get("engine_status") or incident.get("engine_status"),
    })

    print(f"第2轮提取: {incident}")

    missing2 = get_missing_fields(incident, checklist)
    print(f"缺失字段: {missing2}")
    print(f"预期结果: [] (所有P1字段已收集)")
    print()

    # 检查是否所有P1字段都已收集
    all_p1_collected = all(
        incident.get(field) is not None
        for field in ["fluid_type", "position", "engine_status", "continuous"]
    )

    print(f"✓ P1字段是否全部收集: {all_p1_collected}")
    print(f"✓ 系统应该: 立即调用 assess_risk 进行风险评估")
    print(f"✓ 系统不应该: 继续询问P2字段（aircraft_reg, reported_by等）")
    print()

    return all_p1_collected and missing2 == []


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Bug修复验证测试")
    print("=" * 60)
    print()

    results = []

    # 测试1：位置提取
    try:
        result1 = test_position_extraction()
        results.append(("位置实体提取", result1))
    except Exception as e:
        print(f"✗ 测试1失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("位置实体提取", False))

    # 测试2：缺失字段判断
    try:
        result2 = test_get_missing_fields()
        results.append(("缺失字段判断", result2))
    except Exception as e:
        print(f"✗ 测试2失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("缺失字段判断", False))

    # 测试3：集成测试
    try:
        result3 = test_integration()
        results.append(("集成测试", result3))
    except Exception as e:
        print(f"✗ 测试3失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("集成测试", False))

    # 输出总结
    print("=" * 60)
    print("测试总结")
    print("=" * 60)
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{status}: {name}")

    all_passed = all(passed for _, passed in results)
    print()
    if all_passed:
        print("✓ 所有测试通过！Bug修复成功。")
        return 0
    else:
        print("✗ 部分测试失败，请检查修复代码。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
