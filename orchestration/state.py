from typing import Annotated, Literal, TypedDict

import operator

from langgraph.graph.message import add_messages


class CodebaseContext(TypedDict):
    file_path: str
    content: str
    embedding_id: str
    last_modified: str


class ArchitecturalDecision(TypedDict):
    id: str
    timestamp: str
    decision: str
    rationale: str
    approved_by: str
    affected_components: list[str]


class SecurityFinding(TypedDict):
    severity: Literal["critical", "high", "medium", "low"]
    cwe_id: str
    location: str
    description: str
    remediation: str


class AgentSharedState(TypedDict):
    task_id: str
    sprint_goal: str
    current_phase: Literal[
        "planning",
        "architecture",
        "implementation",
        "security_review",
        "testing",
        "awaiting_approval",
        "done",
    ]
    messages: Annotated[list, add_messages]
    files_to_create: dict[str, str]
    files_modified: dict[str, str]
    test_results: dict[str, bool]
    codebase_context: list[CodebaseContext]
    architectural_decisions: Annotated[list[ArchitecturalDecision], operator.add]
    security_findings: list[SecurityFinding]
    iteration_count: int
    max_iterations: int
    human_feedback: str | None
    approval_required: bool
    approved: bool | None
    tokens_used: Annotated[dict, operator.or_]
    token_budget_remaining: int


OrchestrationState = AgentSharedState
