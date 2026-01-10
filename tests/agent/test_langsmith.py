#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LangSmith 连接测试脚本

验证 LangSmith 追踪是否正常工作。
运行方式:
    python test_langsmith.py
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings


def test_langsmith_connection():
    """测试 LangSmith 连接"""
    print("=" * 60)
    print("LangSmith 连接测试")
    print("=" * 60)

    # 检查配置
    print("\n[1] 检查配置...")
    print(f"  LANGCHAIN_TRACING_V2: {settings.LANGCHAIN_TRACING_V2}")
    print(f"  LANGCHAIN_API_KEY: {settings.LANGCHAIN_API_KEY[:10] if settings.LANGCHAIN_API_KEY else 'None'}...")
    print(f"  LANGCHAIN_PROJECT: {settings.LANGCHAIN_PROJECT}")
    print(f"  LANGCHAIN_ENDPOINT: {settings.LANGCHAIN_ENDPOINT}")

    if not settings.LANGCHAIN_TRACING_V2:
        print("\n[警告] LangSmith 追踪未启用!")
        print("  在 .env 中设置: LANGCHAIN_TRACING_V2=true")
        return False

    if not settings.LANGCHAIN_API_KEY:
        print("\n[错误] 未配置 LANGCHAIN_API_KEY!")
        return False

    # 设置环境变量
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT

    print("\n[2] 测试 LangChain 回调...")
    try:
        # 新版本 LangChain 的路径
        try:
            from langchain_community.callbacks import LangChainTracer
        except ImportError:
            from langchain.callbacks import LangChainTracer
        tracer = LangChainTracer(project_name=settings.LANGCHAIN_PROJECT)
        print("  LangChainTracer 创建成功!")

        # 测试追踪一个简单的 chain
        print("\n[3] 测试简单 LLM 调用...")
        from langchain_openai import ChatOpenAI
        from langchain.schema import HumanMessage

        # 创建 LLM 客户端 (使用配置的 provider)
        if settings.LLM_PROVIDER == "openai":
            llm = ChatOpenAI(
                model=settings.LLM_MODEL,
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
            )
        else:
            # 模拟一个简单调用来测试追踪
            print("  使用模拟消息测试追踪...")
            test_message = "Hello, this is a test message"
            tracer.on_chat_model_start(
                serialized={},
                prompts=[test_message],
                run_id="test-run-123",
            )
            tracer.on_llm_new_token(
                token="Test token",
                run_id="test-run-123",
            )
            tracer.on_llm_end(
                output="Test response",
                run_id="test-run-123",
            )
            print("  模拟追踪完成!")
            print("\n[✓] LangSmith 连接测试成功!")
            print(f"  请在 LangSmith 控制台查看项目: {settings.LANGCHAIN_PROJECT}")
            return True

        # 如果配置了有效的 LLM，测试真实调用
        print(f"  调用 LLM ({settings.LLM_PROVIDER}/{settings.LLM_MODEL})...")
        response = llm.invoke([HumanMessage(content="Hello, this is a test")], config={"callbacks": [tracer]})
        print(f"  LLM 响应: {response.content[:50]}...")
        print("\n[✓] LangSmith 连接测试成功!")
        print(f"  请在 LangSmith 控制台查看项目: {settings.LANGCHAIN_PROJECT}")
        return True

    except Exception as e:
        print(f"\n[错误] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_langgraph_tracing():
    """测试 LangGraph 追踪"""
    print("\n" + "=" * 60)
    print("LangGraph 追踪测试")
    print("=" * 60)

    try:
        from agent.graph import compile_agent
        from agent.state import create_initial_state

        print("\n[1] 创建初始状态...")
        state = create_initial_state(
            session_id="test-session",
            scenario_type="oil_spill",
            initial_message="测试漏油事件",
        )

        print("\n[2] 编译 LangGraph Agent...")
        agent = compile_agent()
        print("  Agent 编译成功!")

        print("\n[3] 执行单步测试...")
        # 设置初始节点
        state["next_node"] = "input_parser"

        # 手动执行 input_parser
        from agent.nodes.input_parser import input_parser_node
        result = input_parser_node(state)
        print(f"  input_parser 执行完成")

        # 手动执行 reasoning (会调用 LLM)
        from agent.nodes.reasoning import reasoning_node
        result = reasoning_node(result)
        print(f"  reasoning 执行完成")

        if result.get("current_action"):
            print(f"  LLM 决策: {result['current_action']}")

        print("\n[✓] LangGraph 追踪测试完成!")
        print(f"  请在 LangSmith 控制台查看追踪记录")
        return True

    except Exception as e:
        print(f"\n[错误] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "#" * 60)
    print("#  LangSmith 连接测试套件")
    print("#" * 60)

    success = True

    # 测试 1: 基础连接
    if not test_langsmith_connection():
        success = False

    # 测试 2: LangGraph 追踪 (可选)
    print("\n是否测试 LangGraph 追踪? (y/n)", end=" ")
    try:
        choice = input().strip().lower()
        if choice in ["y", "yes", "是"]:
            if not test_langgraph_tracing():
                success = False
    except KeyboardInterrupt:
        print("\n跳过 LangGraph 测试")

    print("\n" + "=" * 60)
    if success:
        print("所有测试通过! LangSmith 追踪已正确配置。")
    else:
        print("部分测试失败，请检查配置。")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
