"""
LangGraph 图定义

融合架构核心：
- ReAct 循环作为主推理引擎
- FSM 验证作为检查点
- 约束检查贯穿全程
"""
from typing import Literal
from langgraph.graph import StateGraph, END

from agent.state import AgentState, FSMState
from agent.llm_guard import get_llm_guard
from agent.nodes.input_parser import input_parser_node
from agent.nodes.reasoning import reasoning_node
from agent.nodes.tool_executor import tool_executor_node
from agent.nodes.fsm_validator import fsm_validator_node
from agent.nodes.output_generator import output_generator_node
from config.settings import settings


def should_continue(state: AgentState) -> Literal["reasoning", "tool_executor", "fsm_validator", "output_generator", "end"]:
    """
    决定下一步路由
    
    融合设计：
    - 主要由 ReAct Agent 的输出决定
    - 但在关键节点加入 FSM 验证
    """
    # 检查是否超过最大迭代次数
    if state.get("iteration_count", 0) >= settings.MAX_ITERATIONS:
        return "output_generator"
    
    # 检查是否有错误
    if state.get("error"):
        return "end"
    
    # 检查是否完成
    if state.get("is_complete"):
        return "output_generator"
    
    # 根据当前节点和下一步决定路由
    next_node = state.get("next_node", "")
    
    if next_node == "tool_executor":
        return "tool_executor"
    elif next_node == "fsm_validator":
        return "fsm_validator"
    elif next_node == "output_generator":
        return "output_generator"
    elif next_node == "end":
        return "end"
    else:
        return "reasoning"


def after_tool_execution(state: AgentState) -> Literal["reasoning", "fsm_validator"]:
    """
    工具执行后的路由
    
    融合设计：
    - 执行完关键工具后，触发 FSM 验证
    - 其他情况返回推理节点
    """
    current_action = state.get("current_action", "")
    
    # 这些工具执行后需要 FSM 验证
    fsm_trigger_actions = [
        "assess_risk",           # 风险评估后验证
        "calculate_impact_zone", # 空间分析后验证
        "notify_department",     # 通知部门后验证
    ]
    
    if current_action in fsm_trigger_actions:
        return "fsm_validator"
    
    return "reasoning"


def after_fsm_validation(state: AgentState) -> Literal["reasoning", "output_generator", "end"]:
    """
    FSM 验证后的路由

    融合设计：
    - 验证通过且达到完成条件 → 生成报告
    - 验证通过但未完成 → 继续推理（检查是否需要触发通知）
    - 验证失败 → 返回推理，Agent 需要补救
    """
    fsm_state = state.get("fsm_state", "")
    validation_errors = state.get("fsm_validation_errors", [])

    # 有验证错误，返回推理节点处理
    if validation_errors:
        return "reasoning"

    # 达到完成状态
    if fsm_state == FSMState.COMPLETED.value:
        if (
            state.get("scenario_type") == "oil_spill"
            and not state.get("supplemental_prompted")
            and not state.get("awaiting_supplemental_info")
            and not state.get("report_generated")
        ):
            return "reasoning"
        return "output_generator"

    # 达到 P8 关闭状态
    if fsm_state == FSMState.P8_CLOSE.value:
        if (
            state.get("scenario_type") == "oil_spill"
            and not state.get("supplemental_prompted")
            and not state.get("awaiting_supplemental_info")
            and not state.get("report_generated")
        ):
            return "reasoning"
        # 检查是否还有待执行的强制动作（如通知部门）
        # 如果有，返回 reasoning 让 check_immediate_triggers 触发
        from agent.nodes.reasoning import check_immediate_triggers
        if check_immediate_triggers(state):
            return "reasoning"
        return "output_generator"

    return "reasoning"


def create_agent_graph() -> StateGraph:
    """
    创建 Agent 图
    
    图结构：
    
    ┌─────────────┐
    │   START     │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │input_parser │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐◀─────────────────────────────────┐
    │  reasoning  │                                   │
    └──────┬──────┘                                   │
           │                                          │
           ├─────────────────┐                        │
           ▼                 ▼                        │
    ┌─────────────┐   ┌─────────────┐                │
    │tool_executor│   │   output    │                │
    └──────┬──────┘   │  generator  │                │
           │          └──────┬──────┘                │
           │                 │                        │
           ▼                 ▼                        │
    ┌─────────────┐   ┌─────────────┐                │
    │fsm_validator│   │     END     │                │
    └──────┬──────┘   └─────────────┘                │
           │                                          │
           └──────────────────────────────────────────┘
    """
    get_llm_guard()

    # 创建图
    graph = StateGraph(AgentState)  # type: ignore[type-var]
    
    # 添加节点
    graph.add_node("input_parser", input_parser_node)  # type: ignore[type-var]
    graph.add_node("reasoning", reasoning_node)  # type: ignore[type-var]
    graph.add_node("tool_executor", tool_executor_node)  # type: ignore[type-var]
    graph.add_node("fsm_validator", fsm_validator_node)  # type: ignore[type-var]
    graph.add_node("output_generator", output_generator_node)  # type: ignore[type-var]
    
    # 设置入口
    graph.set_entry_point("input_parser")
    
    # input_parser → reasoning
    graph.add_edge("input_parser", "reasoning")
    
    # reasoning → 条件路由
    graph.add_conditional_edges(
        "reasoning",
        should_continue,
        {
            "reasoning": "reasoning",
            "tool_executor": "tool_executor",
            "fsm_validator": "fsm_validator",
            "output_generator": "output_generator",
            "end": END,
        }
    )
    
    # tool_executor → 条件路由（关键工具后需要 FSM 验证）
    graph.add_conditional_edges(
        "tool_executor",
        after_tool_execution,
        {
            "reasoning": "reasoning",
            "fsm_validator": "fsm_validator",
        }
    )
    
    # fsm_validator → 条件路由
    graph.add_conditional_edges(
        "fsm_validator",
        after_fsm_validation,
        {
            "reasoning": "reasoning",
            "output_generator": "output_generator",
            "end": END,
        }
    )
    
    # output_generator → END
    graph.add_edge("output_generator", END)
    
    return graph


def compile_agent(checkpointer=None):
    """编译 Agent

    Args:
        checkpointer: 可选的检查点存储器，用于状态持久化
    """
    graph = create_agent_graph()

    # 编译配置
    compile_kwargs = {
        "name": "airport-emergency-agent",
    }

    # 如果有检查点存储器，添加配置
    if checkpointer:
        compile_kwargs["checkpointer"] = checkpointer

    return graph.compile(**compile_kwargs)


def get_agent_config():
    """获取Agent运行配置

    返回包含recursion_limit等配置的字典
    """
    return {
        "recursion_limit": 50,  # 增加递归限制到50（默认25）
    }


# 导出编译好的 Agent（默认不带检查点）
agent = compile_agent()
