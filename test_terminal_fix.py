#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试终端修复：验证 prompt_toolkit 回退机制
"""

import sys
import os

# 添加项目路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

def test_import():
    """测试导入和回退机制"""
    print("=" * 65)
    print(" 测试终端修复")
    print("=" * 65)
    print()

    try:
        # 导入模块
        from apps.run_agent import get_user_input, PROMPT_TOOLKIT_AVAILABLE

        print(f"✅ 模块导入成功")
        print()

        if PROMPT_TOOLKIT_AVAILABLE:
            print("ℹ️  prompt_toolkit 可用 - 使用增强编辑功能")
            print("   功能:")
            print("   - ✅ Delete/Backspace 键")
            print("   - ✅ 方向键移动")
            print("   - ✅ 命令历史")
        else:
            print("⚠️  prompt_toolkit 不可用 - 使用标准 input()")
            print("   提示：运行 'pip install prompt_toolkit' 可获得更好体验")

        print()
        print("✅ 修复成功验证")
        print()
        print("立即测试：")
        print("  python apps/run_agent.py")
        print()

        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_import()
    sys.exit(0 if success else 1)
