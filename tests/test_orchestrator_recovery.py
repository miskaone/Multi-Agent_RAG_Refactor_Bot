"""Tests for orchestrator recovery module (Task 8)."""
import pytest

from refactor_bot.models import TaskNode, TaskStatus, FileDiff, TestReport, TestRunResult
from refactor_bot.orchestrator.recovery import (
    get_next_pending_task,
    get_current_task,
    compute_test_pass_rate,
    get_task_diffs,
    next_task_or_end,
)
from refactor_bot.orchestrator.state import make_initial_state


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_task(task_id: str, status: TaskStatus = TaskStatus.PENDING, dependencies: list[str] | None = None) -> TaskNode:
    """Helper to create a TaskNode with sensible defaults."""
    return TaskNode(
        task_id=task_id,
        description=f"Task {task_id}",
        affected_files=["src/app.tsx"],
        dependencies=dependencies if dependencies is not None else [],
        status=status,
        applicable_rules=[],
    )


def make_diff(file_path: str, task_id: str) -> FileDiff:
    """Helper to create a FileDiff."""
    return FileDiff(
        file_path=file_path,
        original_content="old",
        modified_content="new",
        diff_text=f"--- a/{file_path}\n+++ b/{file_path}\n",
        task_id=task_id,
    )


def make_test_report(passed_count: int, failed_count: int) -> TestReport:
    """Helper to create a TestReport with given pass/fail counts."""
    return TestReport(
        passed=failed_count == 0,
        pre_run=None,
        post_run=TestRunResult(
            runner="none",
            exit_code=0 if failed_count == 0 else 1,
            stdout="",
            stderr="",
            passed=passed_count,
            failed=failed_count,
        ),
        breaking_changes=[],
        runner_available=False,
    )


# ---------------------------------------------------------------------------
# get_next_pending_task
# ---------------------------------------------------------------------------

class TestGetNextPendingTask:
    """Tests for DAG-aware task selection."""

    def test_get_next_pending_task_returns_first_eligible(self):
        """PENDING task with all deps COMPLETED is returned."""
        task_a = make_task("RF-001", status=TaskStatus.COMPLETED)
        task_b = make_task("RF-002", status=TaskStatus.PENDING, dependencies=["RF-001"])

        result = get_next_pending_task([task_a, task_b])
        assert result is not None
        assert result.task_id == "RF-002"

    def test_get_next_pending_task_skips_blocked(self):
        """PENDING task with a PENDING dep is NOT returned."""
        task_a = make_task("RF-001", status=TaskStatus.PENDING)
        task_b = make_task("RF-002", status=TaskStatus.PENDING, dependencies=["RF-001"])

        result = get_next_pending_task([task_a, task_b])
        # task_a is eligible (no deps), task_b is blocked
        assert result is not None
        assert result.task_id == "RF-001"

    def test_get_next_pending_task_returns_none_when_all_done(self):
        """When all tasks are COMPLETED, None is returned."""
        tasks = [
            make_task("RF-001", status=TaskStatus.COMPLETED),
            make_task("RF-002", status=TaskStatus.COMPLETED),
        ]
        result = get_next_pending_task(tasks)
        assert result is None

    def test_get_next_pending_task_no_deps(self):
        """Task with empty dependencies list is immediately eligible."""
        task = TaskNode(
            task_id="RF-001",
            description="Refactor component",
            affected_files=["src/app.tsx"],
            dependencies=[],
            status=TaskStatus.PENDING,
            applicable_rules=[],
        )
        result = get_next_pending_task([task])
        assert result is not None
        assert result.task_id == "RF-001"


# ---------------------------------------------------------------------------
# compute_test_pass_rate
# ---------------------------------------------------------------------------

class TestComputeTestPassRate:
    """Tests for pass rate computation."""

    def test_compute_test_pass_rate_all_pass(self):
        """10/10 -> 1.0"""
        report = make_test_report(passed_count=10, failed_count=0)
        rate = compute_test_pass_rate(report)
        assert rate == 1.0

    def test_compute_test_pass_rate_partial(self):
        """8 passed, 2 failed -> 0.8"""
        report = make_test_report(passed_count=8, failed_count=2)
        rate = compute_test_pass_rate(report)
        assert abs(rate - 0.8) < 1e-9

    def test_compute_test_pass_rate_no_tests(self):
        """0 passed, 0 failed -> 1.0 (no failures = no problem)."""
        report = make_test_report(passed_count=0, failed_count=0)
        rate = compute_test_pass_rate(report)
        assert rate == 1.0


# ---------------------------------------------------------------------------
# get_task_diffs
# ---------------------------------------------------------------------------

class TestGetTaskDiffs:
    """Tests for filtering diffs by task_id."""

    def test_get_task_diffs_filters_by_id(self):
        """Returns only diffs matching the given task_id."""
        diff_a1 = make_diff("src/app.tsx", "RF-001")
        diff_a2 = make_diff("src/utils.ts", "RF-001")
        diff_b = make_diff("src/index.ts", "RF-002")

        result = get_task_diffs([diff_a1, diff_a2, diff_b], "RF-001")
        assert len(result) == 2
        assert all(d.task_id == "RF-001" for d in result)

    def test_get_task_diffs_returns_empty_when_no_match(self):
        """Returns [] when no diffs match task_id."""
        diff_b = make_diff("src/index.ts", "RF-002")
        result = get_task_diffs([diff_b], "RF-001")
        assert result == []


# ---------------------------------------------------------------------------
# next_task_or_end
# ---------------------------------------------------------------------------

class TestNextTaskOrEnd:
    """Tests for the routing function."""

    def test_next_task_or_end_continue(self):
        """Returns 'continue' when there are pending tasks available."""
        state = make_initial_state("Refactor", "/tmp")
        state["task_tree"] = [make_task("RF-001", status=TaskStatus.PENDING)]
        result = next_task_or_end(state)
        assert result == "continue"

    def test_next_task_or_end_done(self):
        """Returns 'done' when no pending tasks remain."""
        state = make_initial_state("Refactor", "/tmp")
        state["task_tree"] = [make_task("RF-001", status=TaskStatus.COMPLETED)]
        result = next_task_or_end(state)
        assert result == "done"
