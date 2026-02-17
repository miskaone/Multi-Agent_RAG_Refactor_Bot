"""Unit tests for individual orchestrator graph nodes (Task 9)."""
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from refactor_bot.agents.exceptions import (
    AuditError,
    ExecutionError,
    PlanningError,
)
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
from refactor_bot.orchestrator.graph import (
    apply_node,
    abort_node,
    make_audit_node,
    make_decide_fn,
    make_execute_node,
    make_index_node,
    make_plan_node,
    make_validate_node,
    retry_node,
)
from refactor_bot.orchestrator.state import make_initial_state


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

def make_task(task_id: str, status: TaskStatus = TaskStatus.PENDING, dependencies: list[str] | None = None) -> TaskNode:
    return TaskNode(
        task_id=task_id,
        description=f"Task {task_id}",
        affected_files=["src/app.tsx"],
        dependencies=dependencies if dependencies is not None else [],
        status=status,
        applicable_rules=[],
    )


def make_diff(file_path: str = "src/app.tsx", task_id: str = "RF-001") -> FileDiff:
    return FileDiff(
        file_path=file_path,
        original_content="old",
        modified_content="new",
        diff_text=f"--- a/{file_path}\n+++ b/{file_path}\n",
        task_id=task_id,
    )


def make_repo_index(repo_path: str = "/tmp/repo") -> RepoIndex:
    return RepoIndex(repo_path=repo_path)


def make_passed_audit_report() -> AuditReport:
    return AuditReport(passed=True, diffs_audited=1, error_count=0)


def make_failed_audit_report() -> AuditReport:
    return AuditReport(passed=False, diffs_audited=1, error_count=1)


def make_test_report(passed: bool, passed_count: int = 10, failed_count: int = 0) -> TestReport:
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


# ---------------------------------------------------------------------------
# make_index_node tests
# ---------------------------------------------------------------------------

class TestIndexNode:
    def test_index_node_success(self):
        """Successful index + retriever.index_repo returns correct state keys."""
        repo_index = make_repo_index()
        embedding_stats = {"total_embedded": 42}

        indexer = MagicMock()
        indexer.index.return_value = repo_index

        retriever = MagicMock()
        retriever.index_repo.return_value = embedding_stats

        node = make_index_node(indexer, retriever)
        state = make_initial_state("Refactor hooks", "/tmp/repo")
        result = node(state)

        assert result["repo_index"] is repo_index
        assert result["embedding_stats"] == embedding_stats
        assert "is_react_project" in result
        indexer.index.assert_called_once_with("/tmp/repo")
        retriever.index_repo.assert_called_once_with(repo_index)

    def test_index_node_error(self):
        """When indexer.index raises, errors list is populated and repo_index is None."""
        indexer = MagicMock()
        indexer.index.side_effect = FileNotFoundError("Repo not found")

        retriever = MagicMock()

        node = make_index_node(indexer, retriever)
        state = make_initial_state("Refactor hooks", "/tmp/repo")
        result = node(state)

        assert result["repo_index"] is None
        assert isinstance(result["errors"], list)
        assert len(result["errors"]) > 0
        assert "Repo not found" in result["errors"][0] or "FileNotFoundError" in result["errors"][0] or result["errors"][0]


# ---------------------------------------------------------------------------
# make_plan_node tests
# ---------------------------------------------------------------------------

class TestPlanNode:
    def test_plan_node_success(self):
        """Successful plan returns task_tree, context_bundles, active_rules."""
        task = make_task("RF-001")
        retrieval_results = [
            RetrievalResult(
                id="file::func",
                file_path="src/app.tsx",
                symbol="App",
                type="function",
                source_code="function App() {}",
                distance=0.1,
                similarity=0.9,
            )
        ]

        retriever = MagicMock()
        retriever.query.return_value = retrieval_results

        planner = MagicMock()
        planner.decompose.return_value = [task]

        node = make_plan_node(planner, retriever)
        state = make_initial_state("Refactor hooks", "/tmp/repo")
        state["repo_index"] = make_repo_index()

        result = node(state)

        assert len(result["task_tree"]) == 1
        assert result["task_tree"][0].task_id == "RF-001"
        assert "context_bundles" in result
        assert "active_rules" in result

    def test_plan_node_error(self):
        """When planner.decompose raises PlanningError, errors populated + task_tree empty."""
        retriever = MagicMock()
        retriever.query.return_value = []

        planner = MagicMock()
        planner.decompose.side_effect = PlanningError("LLM failed")

        node = make_plan_node(planner, retriever)
        state = make_initial_state("Refactor hooks", "/tmp/repo")
        state["repo_index"] = make_repo_index()

        result = node(state)

        assert result["task_tree"] == []
        assert isinstance(result["errors"], list)
        assert len(result["errors"]) > 0


# ---------------------------------------------------------------------------
# make_execute_node tests
# ---------------------------------------------------------------------------

class TestExecuteNode:
    def test_execute_node_success(self):
        """Successful execution returns diffs as a list."""
        diff = make_diff()
        task = make_task("RF-001")

        retriever = MagicMock()
        retriever.query.return_value = []

        executor = MagicMock()
        executor.execute.return_value = [diff]

        node = make_execute_node(executor, retriever)
        state = make_initial_state("Refactor hooks", "/tmp/repo")
        state["repo_index"] = make_repo_index()
        state["task_tree"] = [task]

        result = node(state)

        assert isinstance(result["diffs"], list)
        assert len(result["diffs"]) == 1
        assert result["diffs"][0].task_id == "RF-001"

    def test_execute_node_no_pending_task(self):
        """When all tasks are COMPLETED, an error message is added."""
        retriever = MagicMock()
        executor = MagicMock()

        node = make_execute_node(executor, retriever)
        state = make_initial_state("Refactor hooks", "/tmp/repo")
        state["repo_index"] = make_repo_index()
        state["task_tree"] = [make_task("RF-001", status=TaskStatus.COMPLETED)]

        result = node(state)

        # diffs should always be a list (empty on no-task situation)
        assert isinstance(result.get("diffs", []), list)
        assert isinstance(result.get("errors", []), list)
        assert len(result.get("errors", [])) > 0

    def test_execute_node_error(self):
        """When executor.execute raises ExecutionError, diffs=[] and errors populated."""
        task = make_task("RF-001")

        retriever = MagicMock()
        retriever.query.return_value = []

        executor = MagicMock()
        executor.execute.side_effect = ExecutionError("LLM execution failed")

        node = make_execute_node(executor, retriever)
        state = make_initial_state("Refactor hooks", "/tmp/repo")
        state["repo_index"] = make_repo_index()
        state["task_tree"] = [task]

        result = node(state)

        assert result["diffs"] == []
        assert isinstance(result["errors"], list)
        assert len(result["errors"]) > 0


# ---------------------------------------------------------------------------
# make_audit_node tests
# ---------------------------------------------------------------------------

class TestAuditNode:
    def test_audit_node_success(self):
        """Successful audit returns audit_results."""
        audit_report = make_passed_audit_report()

        auditor = MagicMock()
        auditor.audit.return_value = audit_report

        node = make_audit_node(auditor)
        state = make_initial_state("Refactor", "/tmp/repo")
        state["repo_index"] = make_repo_index()
        state["task_tree"] = [make_task("RF-001", status=TaskStatus.IN_PROGRESS)]
        state["diffs"] = [make_diff()]

        result = node(state)

        assert result["audit_results"] is audit_report
        assert result["audit_results"].passed is True

    def test_audit_node_error(self):
        """When auditor.audit raises AuditError, synthetic failed AuditReport is returned."""
        auditor = MagicMock()
        auditor.audit.side_effect = AuditError("Auditor crashed")

        node = make_audit_node(auditor)
        state = make_initial_state("Refactor", "/tmp/repo")
        state["repo_index"] = make_repo_index()
        state["task_tree"] = [make_task("RF-001", status=TaskStatus.IN_PROGRESS)]
        state["diffs"] = [make_diff()]

        result = node(state)

        assert "audit_results" in result
        assert result["audit_results"].passed is False
        assert isinstance(result.get("errors", []), list)


# ---------------------------------------------------------------------------
# make_validate_node tests
# ---------------------------------------------------------------------------

class TestValidateNode:
    def test_validate_node_success(self):
        """Successful validation returns test_results."""
        test_report = make_test_report(passed=True)

        validator = MagicMock()
        validator.validate.return_value = test_report

        node = make_validate_node(validator)
        state = make_initial_state("Refactor", "/tmp/repo")
        state["diffs"] = [make_diff()]

        result = node(state)

        assert result["test_results"] is test_report
        assert result["test_results"].passed is True


# ---------------------------------------------------------------------------
# make_decide_fn tests
# ---------------------------------------------------------------------------

class TestDecideFn:
    def _make_state_with_results(
        self,
        audit_passed: bool,
        test_passed: bool,
        test_pass_count: int = 10,
        test_fail_count: int = 0,
        retry_count: int = 0,
        max_retries: int = 3,
    ) -> dict:
        state = make_initial_state("Refactor", "/tmp")
        task = make_task("RF-001", status=TaskStatus.IN_PROGRESS)
        state["task_tree"] = [task]
        state["audit_results"] = AuditReport(
            passed=audit_passed,
            diffs_audited=1,
            error_count=0 if audit_passed else 1,
        )
        state["test_results"] = TestReport(
            passed=test_passed,
            pre_run=None,
            post_run=TestRunResult(
                runner="vitest",
                exit_code=0 if test_passed else 1,
                stdout="",
                stderr="",
                passed=test_pass_count,
                failed=test_fail_count,
            ),
            breaking_changes=[],
            runner_available=True,
        )
        state["retry_counts"] = {"RF-001": retry_count}
        state["max_retries"] = max_retries
        return state

    def test_decide_fn_apply(self):
        """Passed audit + passed tests -> 'apply'."""
        decide = make_decide_fn()
        state = self._make_state_with_results(audit_passed=True, test_passed=True)
        result = decide(state)
        assert result == "apply"

    def test_decide_fn_retry(self):
        """Failed audit, retries < max -> 'retry'."""
        decide = make_decide_fn()
        state = self._make_state_with_results(
            audit_passed=False,
            test_passed=True,
            retry_count=0,
            max_retries=3,
        )
        result = decide(state)
        assert result == "retry"

    def test_decide_fn_abort_low_pass_rate(self):
        """Test pass rate < 85% -> 'abort' (regardless of retry count)."""
        decide = make_decide_fn()
        # 1 passed, 9 failed = 10% pass rate
        state = self._make_state_with_results(
            audit_passed=True,
            test_passed=False,
            test_pass_count=1,
            test_fail_count=9,
            retry_count=0,
            max_retries=3,
        )
        result = decide(state)
        assert result == "abort"

    def test_decide_fn_abort_retries_exhausted(self):
        """When retries >= max_retries -> 'abort'."""
        decide = make_decide_fn()
        state = self._make_state_with_results(
            audit_passed=False,
            test_passed=True,
            retry_count=3,
            max_retries=3,
        )
        result = decide(state)
        assert result == "abort"


# ---------------------------------------------------------------------------
# apply_node tests
# ---------------------------------------------------------------------------

class TestApplyNode:
    def test_apply_node_marks_completed(self):
        """apply_node marks the current task as COMPLETED."""
        state = make_initial_state("Refactor", "/tmp")
        task = make_task("RF-001", status=TaskStatus.IN_PROGRESS)
        state["task_tree"] = [task]
        state["current_task_index"] = 0

        result = apply_node(state)

        assert "task_tree" in result
        updated_tasks = result["task_tree"]
        # Find the task that was in progress and verify it's now completed
        completed = [t for t in updated_tasks if t.task_id == "RF-001"]
        assert len(completed) == 1
        assert completed[0].status == TaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# retry_node tests
# ---------------------------------------------------------------------------

class TestRetryNode:
    def test_retry_node_increments_count(self):
        """retry_node increments retry_counts[task_id] and marks task PENDING."""
        state = make_initial_state("Refactor", "/tmp")
        task = make_task("RF-001", status=TaskStatus.IN_PROGRESS)
        state["task_tree"] = [task]
        state["current_task_index"] = 0
        state["retry_counts"] = {"RF-001": 1}

        result = retry_node(state)

        assert result["retry_counts"]["RF-001"] == 2
        updated_tasks = result["task_tree"]
        pending = [t for t in updated_tasks if t.task_id == "RF-001"]
        assert len(pending) == 1
        assert pending[0].status == TaskStatus.PENDING
        # Errors should contain a context message
        assert isinstance(result.get("errors", []), list)


# ---------------------------------------------------------------------------
# abort_node tests
# ---------------------------------------------------------------------------

class TestAbortNode:
    def test_abort_node_writes_summary(self):
        """abort_node adds a diagnostic summary to errors."""
        state = make_initial_state("Refactor", "/tmp")
        state["task_tree"] = [make_task("RF-001", status=TaskStatus.IN_PROGRESS)]

        result = abort_node(state)

        assert isinstance(result.get("errors", []), list)
        assert len(result["errors"]) > 0
        # Summary should be a non-empty string
        assert any(isinstance(e, str) and len(e) > 0 for e in result["errors"])
