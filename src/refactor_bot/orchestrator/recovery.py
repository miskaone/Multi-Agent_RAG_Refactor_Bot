"""Pure helper functions for orchestrator recovery logic.

All functions are stateless and have no external dependencies.
"""

from refactor_bot.models import FileDiff, TaskNode, TaskStatus, TestReport
from refactor_bot.orchestrator.state import RefactorState


def find_task_index(task_tree: list[TaskNode], task_id: str) -> int:
    """Find the index of a task by its task_id.

    Args:
        task_tree: List of TaskNode objects.
        task_id: The task_id to search for.

    Returns:
        Index of the task, or -1 if not found.
    """
    for idx, task in enumerate(task_tree):
        if task.task_id == task_id:
            return idx
    return -1


def get_next_pending_task(task_tree: list[TaskNode]) -> TaskNode | None:
    """Return first PENDING task whose dependencies are all COMPLETED.

    Respects DAG ordering — does NOT just return the first PENDING by index.
    A task is eligible only if every task_id listed in its dependencies
    has status COMPLETED in the task_tree.

    Args:
        task_tree: List of TaskNode objects representing the task DAG.

    Returns:
        The first eligible PENDING TaskNode, or None if no eligible task found.
    """
    completed_ids = {
        task.task_id
        for task in task_tree
        if task.status == TaskStatus.COMPLETED
    }

    for task in task_tree:
        if task.status != TaskStatus.PENDING:
            continue
        # All dependencies must be completed
        if all(dep_id in completed_ids for dep_id in task.dependencies):
            return task

    return None


def get_current_task(state: RefactorState) -> TaskNode | None:
    """Return the task at current_task_index, or None if out of bounds.

    Args:
        state: Current pipeline state.

    Returns:
        TaskNode at current_task_index, or None if the index is out of bounds.
    """
    task_tree = state["task_tree"]
    idx = state["current_task_index"]
    if 0 <= idx < len(task_tree):
        return task_tree[idx]
    return None


def compute_test_pass_rate(report: TestReport) -> float:
    """Compute the test pass rate from a TestReport.

    Args:
        report: TestReport with post_run statistics.

    Returns:
        passed / (passed + failed) from report.post_run.
        Returns 1.0 if total == 0 (no tests = no failures).
    """
    if report.post_run is None:
        return 1.0
    total = report.post_run.passed + report.post_run.failed
    if total == 0:
        return 1.0
    return report.post_run.passed / total


def get_task_diffs(diffs: list[FileDiff], task_id: str) -> list[FileDiff]:
    """Filter diffs to those matching the given task_id.

    Args:
        diffs: Full list of FileDiff objects from state.
        task_id: The task_id to filter by.

    Returns:
        List of FileDiff objects whose task_id matches.
    """
    return [diff for diff in diffs if diff.task_id == task_id]


def next_task_or_end(state: RefactorState) -> str:
    """Router function for post-apply/skip conditional edge.

    Args:
        state: Current pipeline state.

    Returns:
        "continue" if get_next_pending_task finds an eligible task, "done" otherwise.
    """
    if get_next_pending_task(state["task_tree"]) is not None:
        return "continue"
    return "done"
