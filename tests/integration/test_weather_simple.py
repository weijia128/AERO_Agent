#!/usr/bin/env python3
"""
简单的气象查询测试
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from agent.nodes.input_parser import apply_auto_enrichment


def test_apply_enrichment():
    """测试 apply_auto_enrichment 函数"""
    print("=" * 80)
    print("测试 apply_auto_enrichment 函数")
    print("=" * 80)
    print()

    # 模拟状态
    state = {
        "incident": {},
        "spatial_analysis": {},
    }

    current_incident = {
        "position": "501",
        "fluid_type": "FUEL",
        "engine_status": "RUNNING",
    }

    print("输入:")
    print(f"  state.incident: {state.get('incident', {})}")
    print(f"  current_incident: {current_incident}")
    print()

    print("⏳ 调用 apply_auto_enrichment...")
    result = apply_auto_enrichment(state, current_incident)

    print()
    print("=" * 80)
    print("结果:")
    print("=" * 80)

    print(f"\n1. updated incident:")
    incident = result.get("incident", {})
    for key, value in incident.items():
        print(f"   - {key}: {value}")

    print(f"\n2. weather:")
    weather = result.get("weather", {})
    if weather:
        for key, value in weather.items():
            print(f"   - {key}: {value}")
    else:
        print("   ❌ 没有气象数据")

    print(f"\n3. enrichment_observation:")
    obs = result.get("enrichment_observation", "")
    if obs:
        print(f"   长度: {len(obs)} 字符")
        print(f"   内容: {obs[:500]}")
    else:
        print("   ❌ 没有观测信息")

    print()
    print("=" * 80)


if __name__ == "__main__":
    test_apply_enrichment()
