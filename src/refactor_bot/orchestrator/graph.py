"""LangGraph orchestrator graph for the refactor pipeline.

Wires RepoIndexer, Retriever, Planner, RefactorExecutor, ConsistencyAuditor,
and TestValidator into a StateGraph with retry/skip/abort recovery logic.
"""

from typing import Callable

from langgraph.graph import END, START, StateGraph

from refactor_bot.agents.consistency_auditor import ConsistencyAuditor
from refactor_bot.agents.planner import Planner
from refactor_bot.agents.refactor_executor import RefactorExecutor
from refactor_bot.agents.repo_indexer import RepoIndexer
from refactor_bot.agents.test_validator import TestValidator
from refactor_bot.models import AuditReport, TaskStatus, TestReport, TestRunResult
from refactor_bot.orchestrator.exceptions import GraphBuildError
from refactor_bot.skills.manager import activate_skills_for_repo
from refactor_bot.skills.registry import registry
from refactor_bot.orchestrator.recovery import (
    compute_test_pass_rate,
    find_task_index,
    get_next_pending_task,
    get_task_diffs,
    next_task_or_end,
)
from refactor_bot.orchestrator.state import RefactorState
from refactor_bot.rag.retriever import Retriever

# Constants
TEST_PASS_RATE_ABORT_THRESHOLD = 0.85
PLAN_NODE_TOP_K = 10
EXECUTE_NODE_TOP_K = 5


def make_index_node(
    indexer: RepoIndexer,
    retriever: Retriever,
    selected_skills: list[str] | None = None,
) -> Callable[[RefactorState], dict]:
    """Factory: returns a node closure that indexes the repository.

    The closure:
    1. Calls indexer.index(state["repo_path"]) -> RepoIndex
    2. Calls retriever.index_repo(repo_index) -> embedding_stats dict
    3. Returns {"repo_index": ..., "embedding_stats": ..., "is_react_project": ...}

    On error: returns {"errors": [str], "repo_index": None}
    """

    def index_node(state: RefactorState) -> dict:
        try:
            repo_index = indexer.index(state["repo_path"])
            activate_skills_for_repo(
                repo_index=repo_index,
                directive=state["directive"],
                selected_skill_names=selected_skills,
            )
            embedding_stats = retriever.index_repo(repo_index)
            return {
                "repo_index": repo_index,
                "embedding_stats": embedding_stats,
                "is_react_project": repo_index.is_react_project,
            }
        except Exception as exc:
            return {
                "errors": [f"index_node error: {exc}"],
                "repo_index": None,
            }

    return index_node


def make_plan_node(planner: Planner, retriever: Retriever) -> Callable[[RefactorState], dict]:
    """Factory: returns a node closure that decomposes the directive into tasks.

    The closure:
    1. Calls retriever.query(state["directive"], top_k=10) -> context
    2. Stores context in context_bundles["planning"]
    3. Calls planner.decompose(directive, repo_index, context) -> list[TaskNode]
    4. Returns {"task_tree": tasks, "context_bundles": updated, "active_rules": rule_ids}

    On error: returns {"errors": [str], "task_tree": []}
    """

    def plan_node(state: RefactorState) -> dict:
        try:
            context = retriever.query(state["directive"], top_k=PLAN_NODE_TOP_K)
            updated_bundles = dict(state["context_bundles"])
            updated_bundles["planning"] = context

            tasks = planner.decompose(
                directive=state["directive"],
                repo_index=state["repo_index"],
                context=context,
            )

            # Collect rule IDs referenced by tasks
            rule_ids: list[str] = []
            for task in tasks:
                rule_ids.extend(task.applicable_rules)
            # Deduplicate while preserving order
            seen: set[str] = set()
            unique_rules: list[str] = []
            for rule_id in rule_ids:
                if rule_id not in seen:
                    seen.add(rule_id)
                    unique_rules.append(rule_id)

            return {
                "task_tree": tasks,
                "context_bundles": updated_bundles,
                "active_rules": unique_rules,
            }
        except Exception as exc:
            return {
                "errors": [f"plan_node error: {exc}"],
                "task_tree": [],
            }

    return plan_node


def make_execute_node(
    executor: RefactorExecutor, retriever: Retriever
) -> Callable[[RefactorState], dict]:
    """Factory: returns a node closure that executes the next pending task.

    The closure:
    1. Calls get_next_pending_task(state["task_tree"]) to find eligible task
    2. Calls retriever.query(task.description, top_k=5) -> context
    3. Calls executor.execute(task, repo_index, context) -> diffs
    4. Updates task status to IN_PROGRESS in task_tree
    5. Returns {"diffs": diffs, "task_tree": updated, "current_task_index": idx}

    On error: returns {"errors": [str], "diffs": [], "task_tree": updated_with_FAILED}

    IMPORTANT: always returns diffs as list (never None) for Annotated reducer.
    """

    def execute_node(state: RefactorState) -> dict:
        task = get_next_pending_task(state["task_tree"])

        if task is None:
            return {
                "errors": ["execute_node: no eligible pending task found"],
                "diffs": [],
                "current_task_index": -1,
            }

        updated_tree = list(state["task_tree"])
        task_idx = find_task_index(updated_tree, task.task_id)

        # Mark task as IN_PROGRESS (transient — no checkpointer in MVP;
        # apply_node/retry_node will transition to COMPLETED/PENDING)
        if task_idx >= 0:
            updated_tree[task_idx] = updated_tree[task_idx].model_copy(
                update={"status": TaskStatus.IN_PROGRESS}
            )

        try:
            context = retriever.query(task.description, top_k=EXECUTE_NODE_TOP_K)
            diffs = executor.execute(
                task=task,
                repo_index=state["repo_index"],
                context=context,
            )
            # Ensure diffs is always a list
            if diffs is None:
                diffs = []

            return {
                "diffs": diffs,
                "task_tree": updated_tree,
                "current_task_index": task_idx,
            }
        except Exception as exc:
            # Mark task as FAILED
            if task_idx >= 0:
                updated_tree[task_idx] = updated_tree[task_idx].model_copy(
                    update={"status": TaskStatus.FAILED}
                )
            return {
                "errors": [f"execute_node error for task {task.task_id}: {exc}"],
                "diffs": [],
                "task_tree": updated_tree,
                "current_task_index": task_idx,
            }

    return execute_node


def make_audit_node(auditor: ConsistencyAuditor) -> Callable[[RefactorState], dict]:
    """Factory: returns a node closure that audits the current task's diffs.

    The closure:
    1. Gets current task diffs via get_task_diffs()
    2. Calls auditor.audit(task_diffs, repo_index) -> AuditReport
    3. Returns {"audit_results": report}

    On error: returns synthetic failed AuditReport + error message.
    """

    def audit_node(state: RefactorState) -> dict:
        task_tree = state["task_tree"]
        current_idx = state["current_task_index"]

        # Identify current task for diff filtering
        if 0 <= current_idx < len(task_tree):
            current_task = task_tree[current_idx]
            task_diffs = get_task_diffs(state["diffs"], current_task.task_id)
        else:
            task_diffs = list(state["diffs"])

        try:
            active_rules = registry.get_all_rules()
            report = auditor.audit(
                diffs=task_diffs,
                repo_index=state["repo_index"],
                react_rules=active_rules,
            )
            return {"audit_results": report}
        except Exception as exc:
            # Synthetic failed report
            failed_report = AuditReport(
                passed=False,
                findings=[],
                diffs_audited=len(task_diffs),
                error_count=1,
            )
            return {
                "audit_results": failed_report,
                "errors": [f"audit_node error: {exc}"],
            }

    return audit_node


def make_validate_node(validator: TestValidator) -> Callable[[RefactorState], dict]:
    """Factory: returns a node closure that validates tests after execution.

    The closure:
    1. Calls validator.validate(repo_path, state["diffs"]) -> TestReport
    2. Returns {"test_results": report}

    On error: returns synthetic failed TestReport + error message.
    """

    def validate_node(state: RefactorState) -> dict:
        try:
            report = validator.validate(
                repo_path=state["repo_path"],
                diffs=state["diffs"],
            )
            return {"test_results": report}
        except Exception as exc:
            # Synthetic failed report
            failed_run = TestRunResult(
                runner="none",
                exit_code=1,
                stdout="",
                stderr=str(exc),
                passed=0,
                failed=1,
            )
            failed_report = TestReport(
                passed=False,
                pre_run=None,
                post_run=failed_run,
                breaking_changes=[],
                runner_available=False,
            )
            return {
                "test_results": failed_report,
                "errors": [f"validate_node error: {exc}"],
            }

    return validate_node


def apply_node(state: RefactorState) -> dict:
    """Mark current task as COMPLETED.

    Returns:
        {"task_tree": updated} with current task status set to COMPLETED.
    """
    updated_tree = list(state["task_tree"])
    current_idx = state["current_task_index"]

    if 0 <= current_idx < len(updated_tree):
        updated_tree[current_idx] = updated_tree[current_idx].model_copy(
            update={"status": TaskStatus.COMPLETED}
        )

    return {"task_tree": updated_tree}


def retry_node(state: RefactorState) -> dict:
    """Increment retry_counts for current task and mark it PENDING for re-execution.

    Also appends error context from audit_results and test_results so that
    the re-execution has feedback for improvement.

    Returns:
        {"retry_counts": updated, "task_tree": updated, "errors": [context_msg]}
    """
    updated_tree = list(state["task_tree"])
    current_idx = state["current_task_index"]
    updated_counts = dict(state["retry_counts"])

    context_messages: list[str] = []

    if 0 <= current_idx < len(updated_tree):
        task = updated_tree[current_idx]
        task_id = task.task_id

        # Increment retry count
        updated_counts[task_id] = updated_counts.get(task_id, 0) + 1

        # Mark task PENDING for re-execution
        updated_tree[current_idx] = task.model_copy(
            update={"status": TaskStatus.PENDING}
        )

        # Build feedback context from audit results
        if state["audit_results"] is not None:
            audit = state["audit_results"]
            context_messages.append(
                f"retry_node [{task_id}] attempt {updated_counts[task_id]}: "
                f"audit_passed={audit.passed}, findings={audit.error_count} errors"
            )

        # Build feedback context from test results
        if state["test_results"] is not None:
            tests = state["test_results"]
            pass_rate = compute_test_pass_rate(tests)
            if tests.post_run is not None:
                context_messages.append(
                    f"retry_node [{task_id}] attempt {updated_counts[task_id]}: "
                    f"test_pass_rate={pass_rate:.2%}, passed={tests.post_run.passed}, "
                    f"failed={tests.post_run.failed}"
                )
            else:
                context_messages.append(
                    f"retry_node [{task_id}] attempt {updated_counts[task_id]}: "
                    f"test_pass_rate={pass_rate:.2%}, no post_run data"
                )
    else:
        context_messages.append(
            "retry_node: current_task_index out of bounds, cannot retry"
        )

    return {
        "retry_counts": updated_counts,
        "task_tree": updated_tree,
        "errors": context_messages,
    }


def skip_node(state: RefactorState) -> dict:
    """Mark current task as SKIPPED.

    Returns:
        {"task_tree": updated} with current task status set to SKIPPED.
    """
    updated_tree = list(state["task_tree"])
    current_idx = state["current_task_index"]

    if 0 <= current_idx < len(updated_tree):
        updated_tree[current_idx] = updated_tree[current_idx].model_copy(
            update={"status": TaskStatus.SKIPPED}
        )

    return {"task_tree": updated_tree}


def abort_node(state: RefactorState) -> dict:
    """Write a diagnostic abort summary to the errors list.

    Returns:
        {"errors": [summary]} describing the abort reason.
    """
    task_tree = state["task_tree"]
    current_idx = state["current_task_index"]
    retry_counts = state["retry_counts"]

    task_id = "unknown"
    if 0 <= current_idx < len(task_tree):
        task_id = task_tree[current_idx].task_id

    retries_used = retry_counts.get(task_id, 0)
    max_retries = state["max_retries"]

    # Collect test pass rate if available
    test_summary = "N/A"
    if state["test_results"] is not None:
        pass_rate = compute_test_pass_rate(state["test_results"])
        test_summary = f"{pass_rate:.2%}"

    audit_summary = "N/A"
    if state["audit_results"] is not None:
        audit = state["audit_results"]
        audit_summary = (
            f"passed={audit.passed}, errors={audit.error_count}"
        )

    summary = (
        f"ABORT: pipeline aborted on task {task_id}. "
        f"Retries used: {retries_used}/{max_retries}. "
        f"Test pass rate: {test_summary}. "
        f"Audit: {audit_summary}."
    )

    return {"errors": [summary]}


def make_decide_fn() -> Callable[[RefactorState], str]:
    """Factory: returns router function for post-validate conditional edge.

    Decision logic:
    1. audit passed AND tests passed -> "apply"
    2. test pass rate < 85% -> "abort"
    3. retries < max_retries -> "retry"
    4. else -> "abort" (retries exhausted)

    Returns:
        Callable that returns one of: "apply", "retry", "abort"
    """

    def decide_fn(state: RefactorState) -> str:
        audit_results = state["audit_results"]
        test_results = state["test_results"]
        current_idx = state["current_task_index"]
        task_tree = state["task_tree"]
        retry_counts = state["retry_counts"]
        max_retries = state["max_retries"]

        # If there is no valid current task, do not retry in-place repeatedly.
        # This can happen when planning produced zero tasks or state became desynced.
        if not (0 <= current_idx < len(task_tree)):
            return "abort"

        # Determine current task id for retry count lookup
        task_id = "unknown"
        if 0 <= current_idx < len(task_tree):
            task_id = task_tree[current_idx].task_id

        # Check audit result
        audit_passed = audit_results is not None and audit_results.passed

        # Check test result
        tests_passed = test_results is not None and test_results.passed

        if test_results is not None and getattr(test_results, "low_trust_pass", False):
            return "abort"

        if audit_passed and tests_passed:
            return "apply"

        # Check test pass rate threshold for immediate abort
        if test_results is not None:
            pass_rate = compute_test_pass_rate(test_results)
            if pass_rate < TEST_PASS_RATE_ABORT_THRESHOLD:
                return "abort"

        # Check retry budget
        current_retries = retry_counts.get(task_id, 0)
        if current_retries < max_retries:
            return "retry"

        # Retries exhausted — abort
        return "abort"

    return decide_fn


def build_graph(
    indexer: RepoIndexer,
    retriever: Retriever,
    planner: Planner,
    executor: RefactorExecutor,
    auditor: ConsistencyAuditor,
    validator: TestValidator,
    selected_skills: list[str] | None = None,
):
    """Build and compile the orchestrator StateGraph.

    Edge topology:
      START -> index_node -> plan_node -> execute_node
      execute_node -> audit_node -> validate_node
      validate_node -> conditional(decide_fn) -> {apply_node, retry_node, skip_node, abort_node}
      apply_node -> conditional(next_task_or_end) -> {execute_node, END}
      retry_node -> execute_node
      skip_node -> conditional(next_task_or_end) -> {execute_node, END}
      abort_node -> END

    No checkpointer (MVP — in-memory state only).

    Args:
        indexer: RepoIndexer agent instance.
        retriever: Retriever agent instance.
        planner: Planner agent instance.
        executor: RefactorExecutor agent instance.
        auditor: ConsistencyAuditor agent instance.
        validator: TestValidator agent instance.

    Returns:
        CompiledStateGraph ready to invoke.

    Raises:
        GraphBuildError: If graph construction fails.
    """
    try:
        graph = StateGraph(RefactorState)

        # Create node closures
        _index_node = make_index_node(indexer, retriever, selected_skills)
        _plan_node = make_plan_node(planner, retriever)
        _execute_node = make_execute_node(executor, retriever)
        _audit_node = make_audit_node(auditor)
        _validate_node = make_validate_node(validator)
        _decide_fn = make_decide_fn()

        # Register nodes
        graph.add_node("index_node", _index_node)
        graph.add_node("plan_node", _plan_node)
        graph.add_node("execute_node", _execute_node)
        graph.add_node("audit_node", _audit_node)
        graph.add_node("validate_node", _validate_node)
        graph.add_node("apply_node", apply_node)
        graph.add_node("retry_node", retry_node)
        graph.add_node("abort_node", abort_node)

        # Linear edges: START -> index -> plan -> execute -> audit -> validate
        graph.add_edge(START, "index_node")
        graph.add_edge("index_node", "plan_node")
        graph.add_edge("plan_node", "execute_node")
        graph.add_edge("execute_node", "audit_node")
        graph.add_edge("audit_node", "validate_node")

        # Conditional edge: validate -> {apply, retry, abort}
        graph.add_conditional_edges(
            "validate_node",
            _decide_fn,
            {
                "apply": "apply_node",
                "retry": "retry_node",
                "abort": "abort_node",
            },
        )

        # apply_node: loop back to execute or end
        graph.add_conditional_edges(
            "apply_node",
            next_task_or_end,
            {
                "continue": "execute_node",
                "done": END,
            },
        )

        # retry_node: always goes back to execute
        graph.add_edge("retry_node", "execute_node")

        # abort_node: always ends
        graph.add_edge("abort_node", END)

        return graph.compile()

    except Exception as exc:
        raise GraphBuildError(f"Failed to build orchestrator graph: {exc}") from exc
