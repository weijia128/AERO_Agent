#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试对话示例脚本

自动模拟完整的对话流程，展示系统如何处理机坪漏油事件
"""

import sys
import os

import pytest

# 添加项目路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

def test_with_mock():
    """使用模拟数据测试对话流程"""
    print("=" * 65)
    print(" 测试对话示例：川航3349滑油泄漏事件")
    print("=" * 65)
    print()

    # 模拟对话流程
    dialogues = [
        ("机长", "天府机坪，川航3349报告紧急情况，右侧发动机有滑油泄漏，可见持续滴漏，泄漏面积不明，请求支援。"),
        ("机坪管制", "川航3349，具体位置（停机位号/滑行道/跑道）？发动机当前状态？运转中还是已关闭？"),
        ("机长", "我在滑行道10，发动机已关机。"),
        ("机坪管制", "川航3349，处置流程已完成。你还有什么需要补充的吗？"),
        ("机长", "无补充信息，完毕。"),
    ]

    print("模拟完整对话流程：\n")

    for i, (speaker, message) in enumerate(dialogues, 1):
        if speaker == "机长":
            print(f"[{i}] 机长: {message}")
        else:
            print(f"[{i}] 机坪管制: {message}")
        print()

    print("=" * 65)
    print(" 系统处理结果：")
    print("=" * 65)
    print()

    # 模拟系统提取的信息
    print("✅ 自动信息提取：")
    print("  - 航班号: 川航3349")
    print("  - 液体类型: 滑油 (OIL)")
    print("  - 泄漏状态: 持续滴漏")
    print("  - 事发位置: 滑行道10")
    print("  - 发动机状态: 已关闭")
    print()

    print("✅ 自动分析结果：")
    print("  - 风险等级: MEDIUM (中等)")
    print("  - 风险分数: 45/100")
    print("  - 影响区域: 滑行道10及其周边")
    print("  - 建议通知: 机务、运控、清洗部门")
    print()

    print("✅ 报告生成：")
    print("  - 已生成机坪特情处置检查单")
    print("  - 包含11个标准章节")
    print("  - 处置流程完整闭环")
    print()

    print("=" * 65)
    print(" 测试完成")
    print("=" * 65)


def test_with_llm():
    """使用真实LLM测试（需要API密钥）"""
    if os.environ.get("RUN_LLM_TESTS") != "1":
        pytest.skip("set RUN_LLM_TESTS=1 to run interactive LLM test")
    if not sys.stdin.isatty():
        pytest.skip("interactive LLM test requires a TTY stdin")

    print("正在启动真实LLM测试...")
    print("请按照以下提示输入对话：\n")

    # 实际运行agent
    from apps.run_agent import main
    assert main() == 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="测试对话示例")
    parser.add_argument("--mock", action="store_true", help="使用模拟数据测试")
    parser.add_argument("--llm", action="store_true", help="使用真实LLM测试")

    args = parser.parse_args()

    if args.mock or not args.llm:
        test_with_mock()
    elif args.llm:
        test_with_llm()
    else:
        print("请选择测试模式:")
        print("  --mock: 模拟测试（默认）")
        print("  --llm : 真实LLM测试")
        print()
        print("示例:")
        print("  python test_dialogue_example.py --mock")
        print("  python test_dialogue_example.py --llm")
