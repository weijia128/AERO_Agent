#!/usr/bin/env python3
"""
测试新的对话模式：机坪管制Agent ←→ 机务人员

场景：机务人员初次报告后，机坪管制Agent主动询问详情
"""
import sys
from agent.state import create_initial_state
from agent.graph import compile_agent

def test_new_dialogue():
    """测试新的角色对话流程"""

    print("=" * 70)
    print("测试场景：机坪管制Agent与机务人员对话")
    print("=" * 70)
    print()

    # 模拟机务初次报告
    initial_report = "这里是机务，501机位发现漏油"

    print("【机务】：", initial_report)
    print()

    # 创建初始状态
    state = create_initial_state(
        session_id="test_001",
        scenario_type="oil_spill",
        initial_message=initial_report
    )

    # 编译Agent
    agent = compile_agent()

    # 执行Agent（模拟第一轮对话）
    print("【系统】：Agent开始处理...")
    print()

    try:
        # 运行一步
        result = agent.invoke(state)

        # 提取Agent的响应
        messages = result.get("messages", [])
        if messages:
            last_message = messages[-1]
            if last_message.get("role") == "assistant":
                print("【机坪管制】：", last_message.get("content"))
                print()

        # 显示当前状态
        print("-" * 70)
        print("当前状态摘要：")
        print(f"  - 场景类型: {result.get('scenario_type')}")
        print(f"  - FSM状态: {result.get('fsm_state')}")
        print(f"  - 当前节点: {result.get('current_node')}")
        print(f"  - 已收集信息: {result.get('incident', {})}")
        print(f"  - Checklist: {result.get('checklist', {})}")
        print("-" * 70)
        print()

        # 模拟机务回答
        print("预期对话流程示例：")
        print()
        print("【机坪管制】：报告你机号")
        print("【机务】：CA1521")
        print()
        print("【机坪管制】：具体位置？停机位还是滑行道？")
        print("【机务】：501机位")
        print()
        print("【机坪管制】：什么油？燃油、液压油还是滑油？")
        print("【机务】：航空燃油")
        print()
        print("【机坪管制】：发动机当前状态？运转还是关车？")
        print("【机务】：发动机还在转")
        print()
        print("【机坪管制】：还在漏吗？持续滴漏还是已经停了？")
        print("【机务】：还在漏，持续的")
        print()
        print("【机坪管制】：目测面积多大？大概几平米？")
        print("【机务】：大概2平米左右")
        print()
        print("【机坪管制】：收到！燃油泄漏+发动机运转=高风险，")
        print("              我立即通知消防和塔台，你们现场先设置警戒区，")
        print("              禁止任何火源靠近！")
        print()

        print("=" * 70)
        print("✅ 对话模式测试完成")
        print("=" * 70)

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()


def show_role_comparison():
    """展示角色对比"""
    print()
    print("=" * 70)
    print("角色对比：修改前 vs 修改后")
    print("=" * 70)
    print()

    print("【修改前】")
    print("  用户角色：管制员（报告事件）")
    print("  Agent角色：应急响应专家（接收报告并处理）")
    print("  对话示例：")
    print("    管制员：501机位发现漏油")
    print("    Agent：请提供航班号")
    print()

    print("【修改后】")
    print("  用户角色：机务人员（现场人员）")
    print("  Agent角色：机坪管制员（主动询问）")
    print("  对话示例：")
    print("    机务：这里是机务，501机位发现漏油")
    print("    机坪管制：报告你机号")
    print()

    print("【关键差异】")
    print("  1. Agent从被动接收 → 主动询问")
    print("  2. 语气从客气 → 专业简洁")
    print("  3. 用户从报告者 → 现场执行者")
    print("=" * 70)
    print()


if __name__ == "__main__":
    show_role_comparison()

    print("\n按回车开始测试...")
    input()

    test_new_dialogue()
