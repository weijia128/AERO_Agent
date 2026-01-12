#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动化对话测试脚本

自动模拟完整的对话流程，包括多轮交互
"""

import sys
import os
import time
from io import StringIO

# 添加项目路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

def automated_test():
    """自动化测试完整对话流程"""
    print("=" * 70)
    print(" 自动化测试：川航3349滑油泄漏事件完整流程")
    print("=" * 70)
    print()

    # 模拟的对话输入
    dialogue_inputs = [
        "天府机坪，川航3349报告紧急情况，右侧发动机有滑油泄漏，可见持续滴漏，泄漏面积不明，请求支援。",
        "我在滑行道10，发动机已关机。",
        "无补充信息，完毕。",
    ]

    print("模拟输入序列：")
    for i, inp in enumerate(dialogue_inputs, 1):
        print(f"  [{i}] {inp}")
    print()

    print("=" * 70)
    print(" 系统处理流程")
    print("=" * 70)
    print()

    # 模拟系统处理
    print("[1] 初始呼叫阶段")
    print("    机坪管制: 天府机坪，请讲。")
    print()

    print("[2] 接收紧急报告")
    print("    机长: 川航3349报告紧急情况...")
    print("    [系统] 自动提取实体: 航班号=川航3349, 液体类型=滑油, 持续=是")
    print("    [系统] 自动触发: 航班信息查询、位置分析")
    print()

    print("[3] 信息收集")
    print("    机坪管制: 川航3349，具体位置？发动机状态？")
    print("    机长: 滑行道10，发动机已关机")
    print("    [系统] 自动提取: 位置=滑行道10, 发动机=关闭")
    print("    [系统] 自动触发: 空间拓扑分析、风险评估")
    print()

    print("[4] 风险评估")
    print("    [系统] 分析结果:")
    print("      - 液体类型: 滑油 (MEDIUM 风险)")
    print("      - 泄漏状态: 持续滴漏")
    print("      - 发动机: 已关闭 (降低风险)")
    print("      - 位置: 滑行道10 (影响局部区域)")
    print("      - 综合风险: MEDIUM (45/100分)")
    print()

    print("[5] 空间分析")
    print("    [系统] 影响范围:")
    print("      - 起始节点: 滑行道10")
    print("      - 隔离区域: 滑行道10, 相邻滑行道")
    print("      - 受影响设施: 停机位A1-A5 (间接影响)")
    print("      - 建议: 封闭滑行道10，启用备用路线")
    print()

    print("[6] 部门通知")
    print("    [系统] 自动通知:")
    print("      - 机务部门: ✓ 已通知")
    print("      - 运控中心: ✓ 已通知")
    print("      - 清洗部门: ✓ 已通知")
    print("      - 安全监察: ✓ 已通知")
    print()

    print("[7] 流程完成")
    print("    机坪管制: 川航3349，处置流程已完成。有补充吗？")
    print("    机长: 无补充信息，完毕")
    print()

    print("=" * 70)
    print(" 最终输出")
    print("=" * 70)
    print()

    print("✅ 生成报告: 机坪特情处置检查单")
    print("   - 11个标准章节")
    print("   - 风险评估结果")
    print("   - 影响范围分析")
    print("   - 协同单位记录")
    print("   - 改进建议")
    print()

    print("✅ 状态跟踪:")
    print("   - 会话ID: SESSION-20260111-001")
    print("   - FSM状态: COMPLETED")
    print("   - 执行步骤: 8步")
    print("   - 耗时: 约2分钟")
    print()

    print("=" * 70)
    print(" 自动化测试完成")
    print("=" * 70)
    print()
    print("注意：这是模拟测试。要进行真实LLM测试，请运行：")
    print("  python apps/run_agent.py")
    print("然后手动输入对话内容。")


if __name__ == "__main__":
    automated_test()
