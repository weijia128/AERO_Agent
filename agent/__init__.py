"""
Agent core module exports.
"""
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent.state import AgentState, create_initial_state
    from agent.graph import create_agent_graph, compile_agent, agent

__all__ = [
    "AgentState",
    "create_initial_state",
    "create_agent_graph",
    "compile_agent",
    "agent",
]


def __getattr__(name: str) -> Any:
    if name in ("AgentState", "create_initial_state"):
        from agent.state import AgentState, create_initial_state
        return {"AgentState": AgentState, "create_initial_state": create_initial_state}[name]
    if name in ("create_agent_graph", "compile_agent", "agent"):
        from agent.graph import create_agent_graph, compile_agent, agent
        return {
            "create_agent_graph": create_agent_graph,
            "compile_agent": compile_agent,
            "agent": agent,
        }[name]
    raise AttributeError(f"module 'agent' has no attribute {name!r}")
