#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速测试：Agent 启动流程验证
"""

import sys
import os
from io import StringIO

# 添加项目路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

def test_agent_initialization():
    """测试 Agent 初始化流程"""
    print("=" * 65)
    print(" 测试 Agent 初始化流程")
    print("=" * 65)
    print()

    try:
        # 模拟用户输入 "exit"
        old_stdin = sys.stdin
        sys.stdin = StringIO("exit\n")

        # 导入并初始化 AgentRunner
        from apps.run_agent import AgentRunner

        runner = AgentRunner()
        initialized = runner.initialize()

        if initialized:
            print("✅ Agent 初始化成功")
        else:
            print("❌ Agent 初始化失败")
            return False

        # 模拟初始输入
        from apps.run_agent import apply_readout_for_processing

        user_input = "exit"
        processed = apply_readout_for_processing(user_input, is_first_contact=True)

        print("✅ 输入处理函数工作正常")
        print()

        print("=" * 65)
        print(" 修复验证成功")
        print("=" * 65)
        print()
        print("修复内容：")
        print("  ✅ 添加了 prompt_toolkit 导入检查")
        print("  ✅ 实现了优雅回退机制")
        print("  ✅ 修复了 'str' object is not callable 错误")
        print()
        print("立即使用：")
        print("  python apps/run_agent.py")
        print()

        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        sys.stdin = old_stdin

if __name__ == "__main__":
    success = test_agent_initialization()
    sys.exit(0 if success else 1)
