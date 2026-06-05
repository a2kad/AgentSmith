from __future__ import annotations

from typing import Any

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, StateGraph

from orchestration.state import AgentSharedState


def architect_node(state: AgentSharedState) -> dict[str, Any]:
    raise NotImplementedError


def developer_node(state: AgentSharedState) -> dict[str, Any]:
    raise NotImplementedError


def security_node(state: AgentSharedState) -> dict[str, Any]:
    raise NotImplementedError


def qa_node(state: AgentSharedState) -> dict[str, Any]:
    raise NotImplementedError


def approval_gate_node(state: AgentSharedState) -> dict[str, Any]:
    raise NotImplementedError


def git_commit_node(state: AgentSharedState) -> dict[str, Any]:
    raise NotImplementedError


def route_after_architect(state: AgentSharedState) -> str:
    raise NotImplementedError


def route_after_dev(state: AgentSharedState) -> str:
    raise NotImplementedError


def route_after_security(state: AgentSharedState) -> str:
    raise NotImplementedError


def route_after_qa(state: AgentSharedState) -> str:
    raise NotImplementedError


def route_after_approval(state: AgentSharedState) -> str:
    raise NotImplementedError


def build_agent_graph(checkpointer: PostgresSaver) -> StateGraph:
    graph = StateGraph(AgentSharedState)

    # Nodes
    graph.add_node("architect", architect_node)
    graph.add_node("developer", developer_node)
    graph.add_node("security", security_node)
    graph.add_node("qa", qa_node)
    graph.add_node("approval_gate", approval_gate_node)
    graph.add_node("git_commit", git_commit_node)

    # Entry
    graph.set_entry_point("architect")

    # Conditional edges
    graph.add_conditional_edges(
        "architect",
        route_after_architect,
        {
            "implement": "developer",
            "need_clarification": "approval_gate",
        },
    )

    graph.add_conditional_edges(
        "developer",
        route_after_dev,
        {
            "test": "qa",
            "security_check": "security",
            "retry": "developer",
        },
    )

    graph.add_conditional_edges(
        "security",
        route_after_security,
        {
            "approve": "qa",
            "request_changes": "developer",
            "escalate": "approval_gate",
        },
    )

    graph.add_conditional_edges(
        "qa",
        route_after_qa,
        {
            "approve": "approval_gate",
            "fix": "developer",
            "commit": "git_commit",
        },
    )

    graph.add_conditional_edges(
        "approval_gate",
        route_after_approval,
        {
            "approved": "git_commit",
            "rejected": "developer",
            "done": END,
        },
    )

    graph.add_edge("git_commit", END)

    return graph
