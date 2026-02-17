"""State definition for the LangGraph orchestrator pipeline."""

import operator
from typing import Annotated, TypedDict

from refactor_bot.models import AuditReport, FileDiff, RepoIndex, TaskNode, TestReport

MAX_RETRIES_LIMIT = 10


class RefactorState(TypedDict):
    """State for the LangGraph refactor orchestrator.

    Fields with Annotated[list, operator.add] reducers accumulate across nodes.
    All other fields use default overwrite semantics.
    """

    # Input
    directive: str
    repo_path: str
    max_retries: int

    # Indexing
    repo_index: RepoIndex | None
    embedding_stats: dict | None
    is_react_project: bool

    # Planning
    context_bundles: dict[str, list]
    task_tree: list[TaskNode]
    active_rules: list[str]
    current_task_index: int

    # Execution (accumulating reducers)
    diffs: Annotated[list[FileDiff], operator.add]

    # Audit and test results
    audit_results: AuditReport | None
    test_results: TestReport | None

    # Recovery
    retry_counts: dict[str, int]

    # Error accumulation
    errors: Annotated[list[str], operator.add]


def make_initial_state(
    directive: str,
    repo_path: str,
    max_retries: int = 3,
) -> RefactorState:
    """Create the initial state for the refactor pipeline.

    Args:
        directive: The refactoring directive to execute.
        repo_path: Absolute path to the repository root.
        max_retries: Maximum retry attempts per task before aborting.

    Returns:
        RefactorState dict with all fields initialised to defaults.
    """
    clamped_retries = max(1, min(max_retries, MAX_RETRIES_LIMIT))
    return {
        "directive": directive,
        "repo_path": repo_path,
        "max_retries": clamped_retries,
        "repo_index": None,
        "embedding_stats": None,
        "context_bundles": {},
        "task_tree": [],
        "active_rules": [],
        "current_task_index": 0,
        "diffs": [],
        "audit_results": None,
        "test_results": None,
        "retry_counts": {},
        "errors": [],
        "is_react_project": False,
    }
