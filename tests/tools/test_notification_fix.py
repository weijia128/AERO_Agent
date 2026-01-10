#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试通知修复
"""
import sys
from agent.state import create_initial_state
from agent.nodes.reasoning import check_immediate_triggers
from agent.nodes.output_generator import generate_coordination_units

def test_notification_fix():
    """测试通知修复"""
    print("=" * 60)
    print("测试通知修复")
    print("=" * 60)

    # 创建初始状态
    state = create_initial_state("test_session", "oil_spill", "")

    # 设置事件信息
    state["incident"] = {
        "fluid_type": "OIL",
        "continuous": True,
        "engine_status": "STOPPED",
        "position": "滑行道19",
        "flight_no": "CSC3349",
        "leak_size": "MEDIUM",
    }

    # 模拟风险评估完成
    state["risk_assessment"] = {
        "level": "MEDIUM",
        "score": 50,
        "factors": ["fluid_type=OIL", "continuous=True"],
        "rationale": "发动机滑油持续泄漏=中风险(可燃)",
        "immediate_actions": [
            "通知消防部门待命",
            "通知机务部门",
            "准备应急物资",
            "使用吸附材料控制扩散",
            "注意防滑处理",
        ],
    }

    print("\n1. 初始状态（风险评估完成）:")
    print(f"   风险等级: {state['risk_assessment']['level']}")
    print(f"   风险分数: {state['risk_assessment']['score']}")

    # 测试 check_immediate_triggers
    print("\n2. 检查立即触发器:")
    trigger = check_immediate_triggers(state)
    if trigger:
        print(f"   发现触发器: {trigger['forced_action']}")
        print(f"   部门: {trigger['forced_input']['department']}")
        print(f"   优先级: {trigger['forced_input']['priority']}")
        print(f"   原因: {trigger['reason']}")
    else:
        print("   未发现触发器")

    # 模拟通知机务
    print("\n3. 模拟通知机务:")
    state["mandatory_actions_done"] = {
        "maintenance_notified": True,
        "fire_dept_notified": False,
        "operations_notified": False,
    }
    state["notifications_sent"] = [
        {
            "department": "机务",
            "priority": "high",
            "message": "滑行道19发生滑油泄漏，风险等级: MEDIUM",
            "timestamp": "2026-01-07T16:21:30",
            "status": "SENT",
        }
    ]

    # 再次检查触发器
    print("\n4. 第二次检查立即触发器:")
    trigger = check_immediate_triggers(state)
    if trigger:
        print(f"   发现触发器: {trigger['forced_action']}")
        print(f"   部门: {trigger['forced_input']['department']}")
        print(f"   优先级: {trigger['forced_input']['priority']}")
        print(f"   原因: {trigger['reason']}")
    else:
        print("   未发现触发器")

    # 模拟通知消防
    print("\n5. 模拟通知消防:")
    state["mandatory_actions_done"]["fire_dept_notified"] = True
    state["notifications_sent"].append({
        "department": "消防",
        "priority": "normal",
        "message": "滑行道19发生滑油泄漏，风险等级: MEDIUM",
        "timestamp": "2026-01-07T16:21:35",
        "status": "SENT",
    })

    # 再次检查触发器
    print("\n6. 第三次检查立即触发器:")
    trigger = check_immediate_triggers(state)
    if trigger:
        print(f"   发现触发器: {trigger['forced_action']}")
        print(f"   部门: {trigger['forced_input']['department']}")
        print(f"   优先级: {trigger['forced_input']['priority']}")
        print(f"   原因: {trigger['reason']}")
    else:
        print("   未发现触发器（所有通知已发送）")

    # 模拟通知运控
    print("\n7. 模拟通知运控:")
    state["mandatory_actions_done"]["operations_notified"] = True
    state["notifications_sent"].append({
        "department": "运控",
        "priority": "normal",
        "message": "滑行道19发生滑油泄漏，风险等级: MEDIUM",
        "timestamp": "2026-01-07T16:21:40",
        "status": "SENT",
    })

    # 最终检查触发器
    print("\n8. 最终检查立即触发器:")
    trigger = check_immediate_triggers(state)
    if trigger:
        print(f"   发现触发器: {trigger['forced_action']}")
        print(f"   部门: {trigger['forced_input']['department']}")
        print(f"   优先级: {trigger['forced_input']['priority']}")
    else:
        print("   ✓ 未发现触发器（所有通知已发送）")

    # 测试 generate_coordination_units
    print("\n9. 测试协调单位生成:")
    coordination_units = generate_coordination_units(state)
    print("   协同单位通知记录:")
    for unit in coordination_units:
        status = "☑ 已通知" if unit["notified"] else "☐ 未通知"
        print(f"   - {unit['name']}: {status} (时间: {unit['notify_time'][:19] if unit['notify_time'] else '——'})")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_notification_fix()
