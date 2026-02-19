"""End-to-end orchestrator tests (Task 10).

All agents are mocked via unittest.mock.MagicMock.
Real Pydantic model instances are used for all data fixtures.
No real API calls, no disk I/O, no subprocesses.
"""
from unittest.mock import MagicMock, call

import pytest

from refactor_bot.models import (
    AuditReport,
    FileDiff,
    RepoIndex,
    RetrievalResult,
    TaskNode,
    TaskStatus,
    TestReport,
    TestRunResult,
)
from refactor_bot.orchestrator import build_graph, make_initial_state


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_task(
    task_id: str,
    status: TaskStatus = TaskStatus.PENDING,
    dependencies: list[str] | None = None,
) -> TaskNode:
    return TaskNode(
        task_id=task_id,
        description=f"Task {task_id}",
        affected_files=["src/app.tsx"],
        dependencies=dependencies if dependencies is not None else [],
        status=status,
        applicable_rules=[],
    )


def _make_diff(task_id: str = "RF-001", file_path: str = "src/app.tsx") -> FileDiff:
    return FileDiff(
        file_path=file_path,
        original_content="old",
        modified_content="new",
        diff_text=f"--- a/{file_path}\n+++ b/{file_path}\n",
        task_id=task_id,
    )


def _make_repo_index(repo_path: str = "/tmp/repo") -> RepoIndex:
    return RepoIndex(repo_path=repo_path)


def _make_passed_audit() -> AuditReport:
    return AuditReport(passed=True, diffs_audited=1, error_count=0)


def _make_failed_audit() -> AuditReport:
    return AuditReport(passed=False, diffs_audited=1, error_count=1)


def _make_test_report(passed: bool, passed_count: int = 10, failed_count: int = 0) -> TestReport:
    return TestReport(
        passed=passed,
        pre_run=None,
        post_run=TestRunResult(
            runner="vitest",
            exit_code=0 if passed else 1,
            stdout="",
            stderr="",
            passed=passed_count,
            failed=failed_count,
        ),
        breaking_changes=[],
        runner_available=True,
    )


def _make_retrieval_results() -> list[RetrievalResult]:
    return [
        RetrievalResult(
            id="src/app.tsx::App",
            file_path="src/app.tsx",
            symbol="App",
            type="function",
            source_code="function App() {}",
            distance=0.1,
            similarity=0.9,
        )
    ]


def _build_mock_agents(
    *,
    task_tree: list[TaskNode],
    diffs: list[FileDiff],
    audit_report: AuditReport,
    test_report: TestReport,
):
    """Create a full set of mocked agents with the given return values."""
    repo_index = _make_repo_index()
    embedding_stats = {"total_embedded": 5}

    indexer = MagicMock()
    indexer.index.return_value = repo_index

    retriever = MagicMock()
    retriever.index_repo.return_value = embedding_stats
    retriever.query.return_value = _make_retrieval_results()

    planner = MagicMock()
    planner.decompose.return_value = task_tree

    executor = MagicMock()
    executor.execute.return_value = diffs

    auditor = MagicMock()
    auditor.audit.return_value = audit_report

    validator = MagicMock()
    validator.validate.return_value = test_report

    return indexer, retriever, planner, executor, auditor, validator


# ---------------------------------------------------------------------------
# Test 1: Happy path
# ---------------------------------------------------------------------------

class TestE2EHappyPath:
    def test_e2e_happy_path(self):
        """Single task, all agents succeed.

        Verify:
        - result["diffs"] is non-empty
        - result["audit_results"].passed is True
        - result["test_results"].passed is True
        - Task has status COMPLETED
        - result["errors"] is empty
        """
        task = _make_task("RF-001")
        diff = _make_diff("RF-001")

        indexer, retriever, planner, executor, auditor, validator = _build_mock_agents(
            task_tree=[task],
            diffs=[diff],
            audit_report=_make_passed_audit(),
            test_report=_make_test_report(passed=True),
        )

        graph = build_graph(indexer, retriever, planner, executor, auditor, validator)
        result = graph.invoke(make_initial_state(directive="Refactor hooks", repo_path="/tmp/repo"))

        assert len(result["diffs"]) > 0
        assert result["audit_results"].passed is True
        assert result["test_results"].passed is True

        completed_tasks = [t for t in result["task_tree"] if t.task_id == "RF-001"]
        assert len(completed_tasks) == 1
        assert completed_tasks[0].status == TaskStatus.COMPLETED

        assert result["errors"] == []


# ---------------------------------------------------------------------------
# Test 2: Retry then succeed
# ---------------------------------------------------------------------------

class TestE2ERetryThenSucceed:
    def test_e2e_retry_then_succeed(self):
        """Audit fails on first attempt (triggering retry), then audit passes on second.

        The retry flow is: execute -> audit (fail) -> validate -> decide (retry) ->
        retry_node -> execute (again) -> audit (pass) -> validate -> decide (apply) -> END.

        Verify:
        - Task ends up COMPLETED
        - result["retry_counts"] has entry with value >= 1
        - result["diffs"] contains diffs from execution
        """
        task = _make_task("RF-001")
        diff = _make_diff("RF-001")
        repo_index = _make_repo_index()

        indexer = MagicMock()
        indexer.index.return_value = repo_index

        retriever = MagicMock()
        retriever.index_repo.return_value = {"total_embedded": 5}
        retriever.query.return_value = _make_retrieval_results()

        planner = MagicMock()
        planner.decompose.return_value = [task]

        # Both execute calls succeed (returning diffs)
        executor = MagicMock()
        executor.execute.return_value = [diff]

        # Audit fails on first call, passes on second
        auditor = MagicMock()
        auditor.audit.side_effect = [_make_failed_audit(), _make_passed_audit()]

        validator = MagicMock()
        validator.validate.return_value = _make_test_report(passed=True)

        graph = build_graph(indexer, retriever, planner, executor, auditor, validator)
        result = graph.invoke(
            make_initial_state(directive="Refactor hooks", repo_path="/tmp/repo"),
            config={"recursion_limit": 100},
        )

        # Task must eventually be COMPLETED
        completed_tasks = [t for t in result["task_tree"] if t.task_id == "RF-001"]
        assert len(completed_tasks) == 1
        assert completed_tasks[0].status == TaskStatus.COMPLETED

        # There must be at least one retry recorded
        assert "RF-001" in result["retry_counts"]
        assert result["retry_counts"]["RF-001"] >= 1

        # Diffs from execution must be present
        assert len(result["diffs"]) > 0


# ---------------------------------------------------------------------------
# Test 2b: Skip when retries exhausted
# ---------------------------------------------------------------------------

class TestE2ESkipOnRetriesExhausted:
    def test_e2e_skip_on_retries_exhausted(self):
        """Repeated audit failures and passing tests -> final state is skipped task."""
        task = _make_task("RF-001")
        diff = _make_diff("RF-001")
        repo_index = _make_repo_index()

        indexer = MagicMock()
        indexer.index.return_value = repo_index

        retriever = MagicMock()
        retriever.index_repo.return_value = {"total_embedded": 5}
        retriever.query.return_value = _make_retrieval_results()

        planner = MagicMock()
        planner.decompose.return_value = [task]

        executor = MagicMock()
        executor.execute.return_value = [diff]

        # Audit fails every pass; retries exhaust and task is marked skipped.
        auditor = MagicMock()
        auditor.audit.side_effect = [_make_failed_audit(), _make_failed_audit()]

        validator = MagicMock()
        validator.validate.return_value = _make_test_report(passed=True)

        graph = build_graph(indexer, retriever, planner, executor, auditor, validator)
        result = graph.invoke(
            make_initial_state(directive="Refactor hooks", repo_path="/tmp/repo", max_retries=1),
            config={"recursion_limit": 100},
        )

        skipped_tasks = [t for t in result["task_tree"] if t.task_id == "RF-001"]
        assert len(skipped_tasks) == 1
        assert skipped_tasks[0].status == TaskStatus.SKIPPED


# ---------------------------------------------------------------------------
# Test 3: Abort on low test pass rate
# ---------------------------------------------------------------------------

class TestE2EAbortOnLowPassRate:
    def test_e2e_abort_on_low_test_pass_rate(self):
        """validator returns 1 passed / 9 failed (10% pass rate) -> pipeline aborts.

        Verify:
        - Pipeline terminates (no infinite loop)
        - result["errors"] contains an abort summary
        """
        task = _make_task("RF-001")
        diff = _make_diff("RF-001")

        indexer, retriever, planner, executor, auditor, validator = _build_mock_agents(
            task_tree=[task],
            diffs=[diff],
            audit_report=_make_passed_audit(),
            test_report=_make_test_report(passed=False, passed_count=1, failed_count=9),
        )

        graph = build_graph(indexer, retriever, planner, executor, auditor, validator)
        # Use recursion_limit to guard against bugs that create infinite loops
        result = graph.invoke(
            make_initial_state(directive="Refactor hooks", repo_path="/tmp/repo"),
            config={"recursion_limit": 50},
        )

        # Errors must contain an abort summary
        assert isinstance(result["errors"], list)
        assert len(result["errors"]) > 0


# ---------------------------------------------------------------------------
# Test 4: Multiple tasks with DAG ordering
# ---------------------------------------------------------------------------

class TestE2EMultipleTasksDagOrder:
    def test_e2e_multiple_tasks_dag_order(self):
        """Planner returns 2 tasks: task B depends on task A.

        Verify:
        - Task A executes before task B (call order)
        - Both tasks end up COMPLETED
        """
        task_a = _make_task("RF-001", dependencies=[])
        task_b = _make_task("RF-002", dependencies=["RF-001"])

        diff_a = _make_diff("RF-001", "src/app.tsx")
        diff_b = _make_diff("RF-002", "src/utils.tsx")

        repo_index = _make_repo_index()

        indexer = MagicMock()
        indexer.index.return_value = repo_index

        retriever = MagicMock()
        retriever.index_repo.return_value = {"total_embedded": 5}
        retriever.query.return_value = _make_retrieval_results()

        planner = MagicMock()
        planner.decompose.return_value = [task_a, task_b]

        executor = MagicMock()
        # Each call returns the diff for whichever task was executed
        executor.execute.side_effect = [[diff_a], [diff_b]]

        auditor = MagicMock()
        auditor.audit.return_value = _make_passed_audit()

        validator = MagicMock()
        validator.validate.return_value = _make_test_report(passed=True)

        graph = build_graph(indexer, retriever, planner, executor, auditor, validator)
        result = graph.invoke(
            make_initial_state(directive="Refactor DAG", repo_path="/tmp/repo"),
            config={"recursion_limit": 100},
        )

        # Both tasks must be completed
        task_statuses = {t.task_id: t.status for t in result["task_tree"]}
        assert task_statuses.get("RF-001") == TaskStatus.COMPLETED
        assert task_statuses.get("RF-002") == TaskStatus.COMPLETED

        # Verify executor was called twice (once for each task)
        assert executor.execute.call_count == 2

        # Verify task A was executed before task B by checking call args.
        # executor.execute is called with keyword arguments: execute(task=..., repo_index=..., context=...)
        calls = executor.execute.call_args_list
        first_call_task = calls[0].kwargs["task"]
        second_call_task = calls[1].kwargs["task"]
        assert first_call_task.task_id == "RF-001"
        assert second_call_task.task_id == "RF-002"
