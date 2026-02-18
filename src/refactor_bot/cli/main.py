"""CLI entry point for the Multi-Agent RAG Refactor Bot."""
import argparse
import json
import os
import sys
import traceback
from pathlib import Path

from refactor_bot.agents.exceptions import AgentError
from refactor_bot.orchestrator.exceptions import OrchestratorError

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
    "skills", "allow_no_runner_pass",
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

    embedding_service = EmbeddingService(api_key=openai_key)
    vector_store = VectorStore(persist_dir=args.vector_store_dir)
    retriever = Retriever(
        embedding_service=embedding_service, vector_store=vector_store
    )
    indexer = RepoIndexer()
    planner = Planner(api_key=api_key, model=args.model)
    executor = RefactorExecutor(api_key=api_key, model=args.model)
    auditor = ConsistencyAuditor()
    validator = TestValidator(
        api_key=api_key,
        model=args.model,
        timeout_seconds=args.timeout,
        allow_no_runner_pass=args.allow_no_runner_pass,
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
