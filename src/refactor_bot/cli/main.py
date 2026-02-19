"""CLI entry point for the Multi-Agent RAG Refactor Bot."""
import argparse
from dotenv import load_dotenv
import json
import os
import sys
import traceback
from pathlib import Path

from refactor_bot.agents.exceptions import AgentError
from refactor_bot.orchestrator.exceptions import OrchestratorError
from refactor_bot.models import PRArtifact, PRRiskLevel, AuditReport, TestReport, TaskStatus, PR_ARTIFACT_SCHEMA_VERSION

load_dotenv()

# Exit codes (L010)
EXIT_SUCCESS = 0
EXIT_INVALID_INPUT = 1
EXIT_AGENT_ERROR = 2
EXIT_ORCHESTRATOR_ERROR = 3
EXIT_GRAPH_ABORT = 4
EXIT_UNEXPECTED = 5
EXIT_KEYBOARD_INTERRUPT = 130

# Defaults
DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT = 120
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_VECTOR_STORE_DIR = "./data/embeddings"

# Abort detection prefix — must match abort_node output in graph.py
ABORT_PREFIX = "ABORT:"

# Safe keys allowed in config output (no secrets)
_SAFE_CONFIG_KEYS = frozenset({
    "directive", "repo_path", "max_retries", "model",
    "vector_store_dir", "timeout", "verbose", "dry_run", "output_json",
    "skills", "allow_no_runner_pass", "llm_provider", "llm_fallback_provider",
    "allow_llm_fallback", "allow_no_runner_pass", "interactive_fallback",
    "output_pr_artifact",
    "output_pr_artifact_format",
})


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="refactor-bot",
        description="Multi-Agent RAG Refactor Bot for JS/TS codebases",
    )
    parser.add_argument("directive", type=str, help="Refactoring directive to execute")
    parser.add_argument("repo_path", type=str, help="Path to the repository root")
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help=f"Maximum retry attempts per task (default: {DEFAULT_MAX_RETRIES})",
    )
    parser.add_argument(
        "--vector-store-dir",
        type=str,
        default=DEFAULT_VECTOR_STORE_DIR,
        help=f"Vector store directory (default: {DEFAULT_VECTOR_STORE_DIR})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Model ID to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print config and exit without running"
    )
    parser.add_argument(
        "--output-json", action="store_true", help="Output results as JSON"
    )
    parser.add_argument(
        "--skills",
        type=str,
        default="",
        help=(
            "Comma-separated skill package names to activate "
            "(for example: vercel-react-best-practices)"
        ),
    )
    parser.add_argument(
        "--allow-no-runner-pass",
        action="store_true",
        help=(
            "Allow LLM-only test validation when no test runner is detected "
            "(low-trust, default blocks pipeline)"
        ),
    )
    parser.add_argument(
        "--llm-provider",
        type=str,
        default="auto",
        choices=("auto", "anthropic", "openai"),
        help=(
            "LLM provider for Planner/Executor/Validator: "
            "auto (default), anthropic, or openai"
        ),
    )
    parser.add_argument(
        "--llm-fallback-provider",
        type=str,
        default="",
        choices=("", "anthropic", "openai"),
        help=(
            "Optional explicit fallback provider when primary provider fails "
            "(for example: openai)"
        ),
    )
    parser.add_argument(
        "--allow-llm-fallback",
        action="store_true",
        help=(
            "Allow manual fallback to alternate provider when primary provider fails"
        ),
    )
    parser.add_argument(
        "--output-pr-artifact",
        type=str,
        default="",
        help=(
            "Write PR artifact JSON to this path (for example: ./artifacts/pr_artifact.json)"
        ),
    )
    parser.add_argument(
        "--output-pr-artifact-format",
        type=str,
        default="json",
        choices=("json", "markdown"),
        help=(
            "Artifact output format: json (default) or markdown. "
            f"Markdown renders schema version {PR_ARTIFACT_SCHEMA_VERSION}."
        ),
    )
    return parser


def validate_repo_path(raw_path: str) -> str:
    """Validate and resolve the repository path.

    Args:
        raw_path: Raw path string from CLI arguments.

    Returns:
        Resolved absolute path as string.

    Raises:
        SystemExit: If path is not a valid directory.
    """
    resolved = Path(raw_path).resolve()
    if not resolved.is_dir():
        print(f"Error: '{raw_path}' is not a valid directory.", file=sys.stderr)
        raise SystemExit(EXIT_INVALID_INPUT)
    return str(resolved)


def create_agents(args: argparse.Namespace) -> dict:
    """Create all agent instances from CLI arguments.

    Agent and RAG imports are deferred to avoid heavy startup cost
    for --help and --dry-run paths.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Dict with keys: indexer, retriever, planner, executor, auditor, validator.
    """
    # Lazy imports — avoid loading anthropic/openai/chromadb/tree-sitter at module level
    from refactor_bot.agents.repo_indexer import RepoIndexer
    from refactor_bot.agents.planner import Planner
    from refactor_bot.agents.refactor_executor import RefactorExecutor
    from refactor_bot.agents.consistency_auditor import ConsistencyAuditor
    from refactor_bot.agents.test_validator import TestValidator
    from refactor_bot.rag.retriever import Retriever
    from refactor_bot.rag.embeddings import EmbeddingService
    from refactor_bot.rag.vector_store import VectorStore

    # API keys from environment (agents also fall back to env internally)
    api_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    llm_provider = args.llm_provider
    llm_fallback_provider = (
        args.llm_fallback_provider or None
        if getattr(args, "llm_fallback_provider", "")
        else None
    )
    allow_llm_fallback = bool(getattr(args, "allow_llm_fallback", False))
    interactive_fallback = sys.stdin.isatty() and not args.dry_run

    embedding_service = EmbeddingService(api_key=openai_key)
    vector_store = VectorStore(persist_dir=args.vector_store_dir)
    retriever = Retriever(
        embedding_service=embedding_service, vector_store=vector_store
    )
    indexer = RepoIndexer()
    planner = Planner(
        api_key=api_key,
        model=args.model,
        llm_provider=llm_provider,
        llm_fallback_provider=llm_fallback_provider,
        allow_fallback=allow_llm_fallback,
        allow_human_fallback=interactive_fallback,
    )
    executor = RefactorExecutor(
        api_key=api_key,
        model=args.model,
        llm_provider=llm_provider,
        llm_fallback_provider=llm_fallback_provider,
        allow_fallback=allow_llm_fallback,
        allow_human_fallback=interactive_fallback,
    )
    auditor = ConsistencyAuditor()
    validator = TestValidator(
        api_key=api_key,
        openai_api_key=openai_key,
        model=args.model,
        timeout_seconds=args.timeout,
        allow_no_runner_pass=args.allow_no_runner_pass,
        llm_provider=llm_provider,
        llm_fallback_provider=llm_fallback_provider,
        allow_fallback=allow_llm_fallback,
        allow_human_fallback=interactive_fallback,
    )

    return {
        "indexer": indexer,
        "retriever": retriever,
        "planner": planner,
        "executor": executor,
        "auditor": auditor,
        "validator": validator,
    }


def format_result_json(result: dict) -> str:
    """Serialize result dict to JSON string.

    Calls .model_dump() on Pydantic model values. Falls back to str()
    for non-serializable types (datetime, Path, etc.) via default=str.
    """

    def _serialize(obj):
        if obj is None:
            return None
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        return obj

    prepared = {k: _serialize(v) for k, v in result.items()}
    return json.dumps(prepared, indent=2, default=str)


def _build_pr_artifact(directive: str, result: dict) -> PRArtifact:
    """Build a minimal PR-ready artifact from orchestrator result."""
    task_tree = result.get("task_tree", [])
    diffs = result.get("diffs", [])
    audit = result.get("audit_results")
    tests = result.get("test_results")
    errors = result.get("errors", [])

    def _file_path(diff_item):
        if hasattr(diff_item, "file_path"):
            return getattr(diff_item, "file_path")
        if hasattr(diff_item, "get"):
            return diff_item.get("file_path")
        return None

    changed_files = sorted({path for path in (_file_path(diff) for diff in diffs) if path is not None})
    completed_count = 0
    skipped_count = 0
    failed_count = 0

    for task in task_tree:
        status = task.status
        if status is None and isinstance(task, dict):
            status = task.get("status")
        if isinstance(status, str):
            try:
                status = TaskStatus(status)
            except ValueError:
                status = status
        if status == TaskStatus.COMPLETED:
            completed_count += 1
        elif status == TaskStatus.SKIPPED:
            skipped_count += 1
        elif status == TaskStatus.FAILED:
            failed_count += 1

    audit_passed = bool(audit.passed) if isinstance(audit, AuditReport) else False
    tests_passed = bool(tests.passed) if isinstance(tests, TestReport) else False
    low_trust_pass = bool(getattr(tests, "low_trust_pass", False)) if isinstance(tests, TestReport) else False

    if any(str(err).startswith(ABORT_PREFIX) for err in errors):
        risk = PRRiskLevel.HIGH
    elif not audit_passed or not tests_passed:
        risk = PRRiskLevel.HIGH
    elif low_trust_pass:
        risk = PRRiskLevel.MEDIUM
    elif failed_count > 0 or skipped_count > 0:
        risk = PRRiskLevel.MEDIUM
    else:
        risk = PRRiskLevel.LOW

    summary = (
        f"directive='{directive}', tasks={len(task_tree)} "
        f"completed={completed_count}, skipped={skipped_count}, failed={failed_count}, "
        f"changed_files={len(changed_files)}, audit_passed={audit_passed}, "
        f"tests_passed={tests_passed}, low_trust={low_trust_pass}"
    )

    rollback_files = [f for f in changed_files]
    reviewer_checklist = _build_reviewer_checklist(
        audit_passed=audit_passed,
        tests_passed=tests_passed,
        low_trust_pass=low_trust_pass,
        failed_count=failed_count,
        skipped_count=skipped_count,
        errors=errors,
    )
    rollback_instructions = _build_rollback_instructions(rollback_files)

    return PRArtifact(
        title=f"Refactor: {directive[:72]}",
        summary=summary,
        risk=risk,
        changed_files=changed_files,
        rollback_files=rollback_files,
        reviewer_checklist=reviewer_checklist,
        rollback_instructions=rollback_instructions,
        task_count=len(task_tree),
        completed_task_count=completed_count,
        skipped_task_count=skipped_count,
        failed_task_count=failed_count,
        audit_passed=audit_passed,
        tests_passed=tests_passed,
        low_trust_pass=low_trust_pass,
    )


def _build_reviewer_checklist(
    *,
    audit_passed: bool,
    tests_passed: bool,
    low_trust_pass: bool,
    failed_count: int,
    skipped_count: int,
    errors: list[str],
) -> list[str]:
    """Build a reviewer checklist based on run outcome."""
    checklist = [
        "Review all generated diffs for correctness and intent.",
        "Confirm changed files are scoped to the requested directive.",
        "Validate task statuses and ensure no critical tasks were unintentionally skipped.",
    ]
    if not audit_passed:
        checklist.append("Address all audit findings before merging.")
    if not tests_passed:
        checklist.append("Resolve test failures before merging.")
    if low_trust_pass:
        checklist.append("Manually approve because low-trust test path was used.")
    if failed_count > 0:
        checklist.append("Investigate failed task execution and re-run this refactor.")
    if skipped_count > 0:
        checklist.append("Confirm skipped tasks are intentionally deferred.")
    if errors:
        checklist.append("Address all listed run errors before merging.")
    checklist.append("Run local smoke checks (lint/targeted tests) before merge.")
    return checklist


def _build_rollback_instructions(rollback_files: list[str]) -> list[str]:
    """Build deterministic rollback instructions for full and partial reverts."""
    if not rollback_files:
        return [
            "No files were changed; no rollback required.",
            "Optional: confirm with git status --short before closeout.",
        ]

    steps = [
        "git status --short",
        "git rev-parse --abbrev-ref HEAD",
        "git restore --source=HEAD --worktree --staged .",
        "git restore --source=HEAD --worktree -- .",
    ]
    steps.extend(
        [
            "Full rollback completed; verify:",
            "git status --short",
        ]
    )
    for path in rollback_files:
        steps.append(f"git restore --source=HEAD --worktree -- {path}")
    steps.append(
        "If restore conflicts occur, inspect with git status and resolve manually before continuing."
    )
    return steps


def _render_pr_artifact_markdown(artifact: PRArtifact) -> str:
    changed = "".join(f"- {path}\n" for path in artifact.changed_files) or "- (none)\n"
    checklist = "".join(f"- [ ] {item}\n" for item in artifact.reviewer_checklist)
    rollback = "".join(f"- `{item}`\n" for item in artifact.rollback_instructions)
    generated_at = artifact.generated_at.isoformat()
    return (
        "---\n"
        f"schema_version: {artifact.schema_version}\n"
        f"title: \"{artifact.title}\"\n"
        f"generated_at: {generated_at}\n"
        f"risk: \"{artifact.risk}\"\n"
        "artifact_type: pr-review\n"
        "---\n\n"
        f"# {artifact.title}\n\n"
        "## Executive Summary\n"
        f"{artifact.summary}\n\n"
        "## Quality and Validation\n"
        f"- Audit passed: {'yes' if artifact.audit_passed else 'no'}\n"
        f"- Tests passed: {'yes' if artifact.tests_passed else 'no'}\n"
        f"- Low trust mode: {'yes' if artifact.low_trust_pass else 'no'}\n"
        f"- Error count: {artifact.failed_task_count + artifact.skipped_task_count}\n\n"
        "## Task Status\n"
        f"- Total tasks: {artifact.task_count}\n"
        f"- Completed: {artifact.completed_task_count}\n"
        f"- Skipped: {artifact.skipped_task_count}\n"
        f"- Failed: {artifact.failed_task_count}\n\n"
        "## Changed files\n"
        f"{changed}\n"
        "## Reviewer checklist\n"
        f"{checklist}\n"
        "## Rollback instructions\n"
        f"{rollback}\n"
    )


def _write_pr_artifact(path: str, artifact: PRArtifact, output_format: str) -> None:
    """Serialize and write PRArtifact to disk."""
    artifact_path = Path(path).expanduser().resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "markdown":
        payload = _render_pr_artifact_markdown(artifact)
    else:
        payload = format_result_json(artifact.model_dump())
    artifact_path.write_text(
        payload,
        encoding="utf-8",
    )


def print_result_human(result: dict) -> None:
    """Print results in human-readable format."""
    print(f"\n{'='*60}")
    print("Refactor Bot Results")
    print(f"{'='*60}")

    if "directive" in result:
        print(f"\nDirective: {result['directive']}")

    tasks = result.get("task_tree", [])
    if tasks:
        status_counts: dict[str, int] = {}
        for task in tasks:
            status = getattr(task, "status", None) or (
                task.get("status") if isinstance(task, dict) else "unknown"
            )
            status_counts[status] = status_counts.get(status, 0) + 1
        print(f"\nTasks ({len(tasks)} total):")
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count}")

    diffs = result.get("diffs", [])
    print(f"\nDiffs generated: {len(diffs)}")

    audit = result.get("audit_results")
    if audit is not None:
        print(f"Audit results: {audit}")

    test = result.get("test_results")
    if test is not None:
        print(f"Test results: {test}")

    errors = result.get("errors", [])
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for err in errors:
            print(f"  - {err}")

    print(f"\n{'='*60}")


def determine_exit_code(result: dict) -> int:
    """Determine the exit code from the result dict."""
    errors = result.get("errors", [])
    if not errors:
        return EXIT_SUCCESS
    for err in errors:
        if str(err).startswith(ABORT_PREFIX):
            return EXIT_GRAPH_ABORT
    return EXIT_ORCHESTRATOR_ERROR


def print_config_human(config: dict) -> None:
    """Print configuration in human-readable format.

    Only prints keys in the safe allowlist to prevent secret leakage.
    """
    print("\nConfiguration:")
    print(f"{'='*40}")
    for key, value in config.items():
        if key in _SAFE_CONFIG_KEYS:
            print(f"  {key}: {value}")
    print(f"{'='*40}")


def _handle_error(label: str, exc: BaseException, verbose: bool, exit_code: int) -> int:
    """Print error message to stderr and return the exit code."""
    print(f"{label}: {exc}", file=sys.stderr)
    if verbose:
        traceback.print_exc(file=sys.stderr)
    return exit_code


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code integer.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        repo_path = validate_repo_path(args.repo_path)
    except SystemExit as exc:
        return exc.code

    config = {
        "directive": args.directive,
        "repo_path": repo_path,
        "max_retries": args.max_retries,
        "model": args.model,
        "vector_store_dir": args.vector_store_dir,
        "timeout": args.timeout,
        "verbose": args.verbose,
        "dry_run": args.dry_run,
        "output_json": args.output_json,
        "skills": args.skills,
        "allow_no_runner_pass": args.allow_no_runner_pass,
        "output_pr_artifact": args.output_pr_artifact,
        "output_pr_artifact_format": args.output_pr_artifact_format,
    }

    if args.dry_run:
        if args.output_json:
            print(json.dumps(config, indent=2))
        else:
            print_config_human(config)
        return EXIT_SUCCESS

    try:
        agents = create_agents(args)

        from refactor_bot.orchestrator.graph import build_graph
        from refactor_bot.orchestrator.state import make_initial_state

        selected_skills = [
            skill.strip() for skill in (args.skills or "").split(",") if skill.strip()
        ]
        graph = build_graph(**agents, selected_skills=selected_skills or None)
        state = make_initial_state(
            directive=args.directive,
            repo_path=repo_path,
            max_retries=args.max_retries,
        )
        result = graph.invoke(state)

        if args.output_json:
            print(format_result_json(result))
        else:
            print_result_human(result)

        artifact_path = args.output_pr_artifact
        if artifact_path:
            artifact_format = args.output_pr_artifact_format
            try:
                artifact = _build_pr_artifact(args.directive, result)
                artifact.output_format = artifact_format
                _write_pr_artifact(artifact_path, artifact, artifact_format)
                if args.verbose:
                    print(f"PR artifact written: {artifact_path}")
            except Exception as exc:
                return _handle_error(
                    "Failed to write PR artifact",
                    exc,
                    args.verbose,
                    EXIT_UNEXPECTED,
                )

        return determine_exit_code(result)

    except AgentError as exc:
        return _handle_error("Agent error", exc, args.verbose, EXIT_AGENT_ERROR)

    except OrchestratorError as exc:
        return _handle_error("Orchestrator error", exc, args.verbose, EXIT_ORCHESTRATOR_ERROR)

    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return EXIT_KEYBOARD_INTERRUPT

    except Exception as exc:
        return _handle_error("Unexpected error", exc, args.verbose, EXIT_UNEXPECTED)
