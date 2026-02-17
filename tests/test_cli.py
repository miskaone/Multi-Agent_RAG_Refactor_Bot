"""Unit tests for the CLI module (refactor_bot.cli.main)."""

from __future__ import annotations

import json
import pytest
from unittest.mock import patch, MagicMock

from refactor_bot.cli.main import (
    build_parser,
    validate_repo_path,
    create_agents,
    format_result_json,
    determine_exit_code,
    main,
    EXIT_SUCCESS,
    EXIT_INVALID_INPUT,
    EXIT_AGENT_ERROR,
    EXIT_ORCHESTRATOR_ERROR,
    EXIT_GRAPH_ABORT,
    EXIT_UNEXPECTED,
    EXIT_KEYBOARD_INTERRUPT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    DEFAULT_MODEL,
    DEFAULT_VECTOR_STORE_DIR,
    ABORT_PREFIX,
)
from refactor_bot.agents.exceptions import AgentError
from refactor_bot.orchestrator.exceptions import GraphBuildError, OrchestratorError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_agents():
    """Return a mock agent dict matching create_agents() output."""
    return {k: MagicMock() for k in ("indexer", "retriever", "planner", "executor", "auditor", "validator")}


def _mock_result(**overrides):
    """Return a minimal successful graph result dict."""
    base = {
        "errors": [], "task_tree": [], "diffs": [],
        "audit_results": None, "test_results": None,
        "directive": "test",
    }
    base.update(overrides)
    return base


# Patch targets for lazy imports inside create_agents()
_AGENT_PATCHES = [
    "refactor_bot.rag.embeddings.EmbeddingService",
    "refactor_bot.rag.vector_store.VectorStore",
    "refactor_bot.rag.retriever.Retriever",
    "refactor_bot.agents.repo_indexer.RepoIndexer",
    "refactor_bot.agents.planner.Planner",
    "refactor_bot.agents.refactor_executor.RefactorExecutor",
    "refactor_bot.agents.consistency_auditor.ConsistencyAuditor",
    "refactor_bot.agents.test_validator.TestValidator",
]

_AGENT_KEYS = ["emb", "vs", "ret", "idx", "plan", "exec", "aud", "val"]


@pytest.fixture()
def patched_agents():
    """Patch all agent constructors inside create_agents."""
    patches = [patch(p) for p in _AGENT_PATCHES]
    mocks = [p.start() for p in patches]
    yield dict(zip(_AGENT_KEYS, mocks))
    for p in patches:
        p.stop()


# ---------------------------------------------------------------------------
# TestBuildParser
# ---------------------------------------------------------------------------
class TestBuildParser:
    def test_parser_positional_args(self):
        parser = build_parser()
        args = parser.parse_args(["my directive", "/tmp"])
        assert args.directive == "my directive"
        assert args.repo_path == "/tmp"

    def test_parser_all_optional_flags(self):
        parser = build_parser()
        args = parser.parse_args([
            "directive text",
            "/tmp",
            "--max-retries", "5",
            "--timeout", "300",
            "--model", "gpt-4",
            "--vector-store-dir", "/data/vs",
            "--output-json",
            "--dry-run",
            "--verbose",
        ])
        assert args.max_retries == 5
        assert args.timeout == 300
        assert args.model == "gpt-4"
        assert args.vector_store_dir == "/data/vs"
        assert args.output_json is True
        assert args.dry_run is True
        assert args.verbose is True

    def test_parser_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["d", "/tmp"])
        assert args.max_retries == DEFAULT_MAX_RETRIES
        assert args.timeout == DEFAULT_TIMEOUT
        assert args.model == DEFAULT_MODEL
        assert args.vector_store_dir == DEFAULT_VECTOR_STORE_DIR
        assert args.output_json is False
        assert args.dry_run is False
        assert args.verbose is False

    def test_parser_no_api_key_flags(self):
        """API keys removed from CLI args (SEC-C7-001); verify they don't exist."""
        parser = build_parser()
        args = parser.parse_args(["d", "/tmp"])
        assert not hasattr(args, "api_key")
        assert not hasattr(args, "openai_key")


# ---------------------------------------------------------------------------
# TestValidateRepoPath
# ---------------------------------------------------------------------------
class TestValidateRepoPath:
    def test_validate_valid_dir(self, tmp_path):
        result = validate_repo_path(str(tmp_path))
        assert result == str(tmp_path.resolve())

    def test_validate_nonexistent(self):
        with pytest.raises(SystemExit) as exc_info:
            validate_repo_path("/nonexistent/path/xyz_abc_123")
        assert exc_info.value.code == EXIT_INVALID_INPUT

    def test_validate_file_not_dir(self, tmp_path):
        f = tmp_path / "afile.txt"
        f.write_text("hello")
        with pytest.raises(SystemExit) as exc_info:
            validate_repo_path(str(f))
        assert exc_info.value.code == EXIT_INVALID_INPUT


# ---------------------------------------------------------------------------
# TestDryRun
# ---------------------------------------------------------------------------
class TestDryRun:
    def test_dry_run_exits_zero(self, tmp_path):
        assert main(["test", str(tmp_path), "--dry-run"]) == EXIT_SUCCESS

    def test_dry_run_json_output(self, tmp_path, capsys):
        rc = main(["test", str(tmp_path), "--dry-run", "--output-json"])
        assert rc == EXIT_SUCCESS
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, dict)
        # Verify no secrets in output
        assert "api_key" not in data
        assert "openai_key" not in data


# ---------------------------------------------------------------------------
# TestCreateAgents
# ---------------------------------------------------------------------------
class TestCreateAgents:
    def test_create_agents_returns_all_keys(self, patched_agents):
        args = build_parser().parse_args(["d", "/tmp"])
        result = create_agents(args)
        assert set(result.keys()) == {
            "indexer", "retriever", "planner", "executor", "auditor", "validator",
        }

    def test_create_agents_reads_env_api_key(self, patched_agents, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test123")
        args = build_parser().parse_args(["d", "/tmp"])
        create_agents(args)
        for mock_cls in (patched_agents["plan"], patched_agents["exec"], patched_agents["val"]):
            assert mock_cls.call_args.kwargs.get("api_key") == "sk-test123"

    def test_create_agents_reads_env_openai_key(self, patched_agents, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "ok-test456")
        args = build_parser().parse_args(["d", "/tmp"])
        create_agents(args)
        assert patched_agents["emb"].call_args.kwargs.get("api_key") == "ok-test456"


# ---------------------------------------------------------------------------
# TestOutputFormatting
# ---------------------------------------------------------------------------
class TestOutputFormatting:
    def test_format_result_json_valid(self):
        result = {
            "errors": [],
            "task_tree": [{"id": 1}],
            "diffs": ["--- a\n+++ b\n"],
            "directive": "refactor",
        }
        output = format_result_json(result)
        parsed = json.loads(output)
        assert parsed["directive"] == "refactor"

    def test_determine_exit_code_success(self):
        result = {"errors": []}
        assert determine_exit_code(result) == EXIT_SUCCESS

    def test_determine_exit_code_abort(self):
        result = {"errors": [f"{ABORT_PREFIX} pipeline aborted on task RF-001"]}
        assert determine_exit_code(result) == EXIT_GRAPH_ABORT

    def test_determine_exit_code_errors(self):
        result = {"errors": ["something went wrong"]}
        assert determine_exit_code(result) == EXIT_ORCHESTRATOR_ERROR

    def test_determine_exit_code_no_false_abort(self):
        """Error containing 'abort' but not starting with ABORT_PREFIX should not trigger abort exit."""
        result = {"errors": ["cannot abort the rollback"]}
        assert determine_exit_code(result) == EXIT_ORCHESTRATOR_ERROR


# ---------------------------------------------------------------------------
# TestErrorHandling
# ---------------------------------------------------------------------------
class TestErrorHandling:
    @patch("refactor_bot.cli.main.create_agents", side_effect=AgentError("boom"))
    def test_main_agent_error(self, _mock, tmp_path):
        rc = main(["test", str(tmp_path)])
        assert rc == EXIT_AGENT_ERROR

    @patch("refactor_bot.orchestrator.graph.build_graph", side_effect=GraphBuildError("boom"))
    @patch("refactor_bot.cli.main.create_agents")
    def test_main_graph_build_error(self, mock_create, mock_build, tmp_path):
        mock_create.return_value = _mock_agents()
        rc = main(["test", str(tmp_path)])
        assert rc == EXIT_ORCHESTRATOR_ERROR

    @patch("refactor_bot.orchestrator.graph.build_graph", side_effect=OrchestratorError("boom"))
    @patch("refactor_bot.cli.main.create_agents")
    def test_main_orchestrator_error(self, mock_create, mock_build, tmp_path):
        mock_create.return_value = _mock_agents()
        rc = main(["test", str(tmp_path)])
        assert rc == EXIT_ORCHESTRATOR_ERROR

    def test_main_nonexistent_repo(self):
        rc = main(["test", "/nonexistent/path/xyz"])
        assert rc == EXIT_INVALID_INPUT

    @patch("refactor_bot.orchestrator.graph.build_graph", side_effect=KeyboardInterrupt)
    @patch("refactor_bot.cli.main.create_agents")
    def test_main_keyboard_interrupt(self, mock_create, mock_build, tmp_path):
        mock_create.return_value = _mock_agents()
        rc = main(["test", str(tmp_path)])
        assert rc == EXIT_KEYBOARD_INTERRUPT

    @patch("refactor_bot.orchestrator.graph.build_graph", side_effect=RuntimeError("oops"))
    @patch("refactor_bot.cli.main.create_agents")
    def test_main_unexpected_error(self, mock_create, mock_build, tmp_path):
        mock_create.return_value = _mock_agents()
        rc = main(["test", str(tmp_path)])
        assert rc == EXIT_UNEXPECTED


# ---------------------------------------------------------------------------
# TestMainHappyPath
# ---------------------------------------------------------------------------
class TestMainHappyPath:
    @patch("refactor_bot.orchestrator.graph.build_graph")
    @patch("refactor_bot.cli.main.create_agents")
    def test_main_happy_path(self, mock_create, mock_build, tmp_path):
        mock_create.return_value = _mock_agents()
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = _mock_result()
        mock_build.return_value = mock_graph
        assert main(["test directive", str(tmp_path)]) == EXIT_SUCCESS
