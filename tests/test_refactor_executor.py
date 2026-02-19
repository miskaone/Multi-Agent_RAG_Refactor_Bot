"""Tests for RefactorExecutor agent."""

import pytest
from unittest.mock import MagicMock, patch

from refactor_bot.agents.exceptions import (
    AgentError,
    DiffGenerationError,
    DiffValidationError,
    ExecutionError,
    SourceFileError,
)
from refactor_bot.agents.refactor_executor import MAX_FILE_SIZE, RefactorExecutor
from refactor_bot.models import FileInfo, RepoIndex, RetrievalResult
from refactor_bot.models.diff_models import FileDiff
from refactor_bot.models.task_models import TaskNode
from refactor_bot.rules import REACT_RULES


# --- Fixtures ---


@pytest.fixture
def executor():
    """RefactorExecutor with test API key."""
    return RefactorExecutor(api_key="test-key")


@pytest.fixture
def sample_task():
    return TaskNode(
        task_id="test-1",
        description="Convert sync functions to async",
        affected_files=["src/db.py"],
        dependencies=[],
        applicable_rules=[],
        confidence_score=0.9,
    )


@pytest.fixture
def sample_task_with_rules():
    return TaskNode(
        task_id="test-2",
        description="Fix waterfall fetches",
        affected_files=["src/app.tsx"],
        dependencies=[],
        applicable_rules=["async-parallel"],
        confidence_score=0.85,
    )


@pytest.fixture
def sample_repo_index(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    db_file = src / "db.py"
    db_file.write_text("def sync_func():\n    pass\n")
    app_file = src / "app.tsx"
    app_file.write_text(
        "async function loadData() {\n"
        "  const a = await fetchA();\n"
        "  const b = await fetchB();\n"
        "}\n"
    )

    return RepoIndex(
        repo_path=str(tmp_path),
        files=[
            FileInfo(
                file_path=str(db_file),
                relative_path="src/db.py",
                language="python",
                hash="abc123",
            ),
            FileInfo(
                file_path=str(app_file),
                relative_path="src/app.tsx",
                language="tsx",
                hash="def456",
            ),
        ],
        is_react_project=True,
    )


@pytest.fixture
def sample_context():
    return [
        RetrievalResult(
            id="ctx-1",
            file_path="src/utils.py",
            symbol="helper",
            type="function",
            source_code="def helper(): pass",
            distance=0.1,
            similarity=0.9,
        )
    ]


# --- Init tests ---


def test_init_with_api_key():
    """Executor initializes with explicit API key."""
    ex = RefactorExecutor(api_key="sk-test")
    assert ex.api_key == "sk-test"


@patch("refactor_bot.agents.refactor_executor.openai.OpenAI")
@patch("refactor_bot.agents.refactor_executor.Anthropic")
def test_init_prefers_anthropic_in_auto(mock_anthropic, mock_openai, monkeypatch):
    """Auto mode prefers Anthropic when both keys are present."""
    mock_anthropic.return_value = object()
    mock_openai.return_value = object()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")

    ex = RefactorExecutor(api_key=None)
    assert ex._primary_provider() == "anthropic"


def test_init_no_api_key_raises():
    """Executor raises AgentError when no key provided and env var unset."""
    import os

    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"ANTHROPIC_API_KEY", "OPENAI_API_KEY"}
    }
    with patch.dict("os.environ", env, clear=True):
        with pytest.raises(AgentError, match="No Anthropic or OpenAI API key found"):
            RefactorExecutor(api_key=None)


@patch("refactor_bot.agents.refactor_executor.openai.OpenAI")
@patch("refactor_bot.agents.refactor_executor.Anthropic")
def test_executor_provider_chain_with_fallback(mock_anthropic, mock_openai):
    """Configured fallback provider should be included in chain when enabled."""
    mock_anthropic.return_value = object()
    mock_openai.return_value = object()

    ex = RefactorExecutor(
        api_key="test-key",
        llm_provider="anthropic",
        llm_fallback_provider="openai",
        allow_fallback=True,
    )
    assert ex._provider_chain() == ["anthropic", "openai"]


@patch("refactor_bot.agents.refactor_executor.openai.OpenAI")
@patch("refactor_bot.agents.refactor_executor.Anthropic")
def test_executor_provider_chain_omits_duplicate_fallback(mock_anthropic, mock_openai):
    """Fallback identical to primary should not duplicate provider in chain."""
    mock_anthropic.return_value = object()
    mock_openai.return_value = object()

    ex = RefactorExecutor(
        api_key="test-key",
        llm_provider="anthropic",
        llm_fallback_provider="anthropic",
        allow_fallback=True,
    )
    assert ex._provider_chain() == ["anthropic"]


# --- _read_source_files tests ---


def test_read_source_files_success(executor, sample_repo_index):
    """Reads file content for affected files."""
    result = executor._read_source_files(["src/db.py"], sample_repo_index)
    assert "src/db.py" in result
    assert "def sync_func" in result["src/db.py"]


def test_read_source_files_missing_file(executor, sample_repo_index):
    """Raises SourceFileError for files not in repo_index."""
    with pytest.raises(SourceFileError):
        executor._read_source_files(["src/nonexistent.py"], sample_repo_index)


def test_read_source_files_too_large(executor, sample_repo_index, tmp_path):
    """Raises SourceFileError when file exceeds MAX_FILE_SIZE."""
    big_file = tmp_path / "src" / "big.py"
    big_file.write_text("x" * (MAX_FILE_SIZE + 1))
    sample_repo_index.files.append(
        FileInfo(
            file_path=str(big_file),
            relative_path="src/big.py",
            language="python",
            hash="big",
        )
    )
    with pytest.raises(SourceFileError, match="exceeds"):
        executor._read_source_files(["src/big.py"], sample_repo_index)


# --- _get_applicable_rules tests ---


def test_get_applicable_rules_found(executor):
    """Returns matching ReactRule objects."""
    rules = executor._get_applicable_rules(["async-parallel"])
    assert len(rules) == 1
    assert rules[0].rule_id == "async-parallel"


def test_get_applicable_rules_empty(executor):
    """Returns empty list when no rule IDs provided."""
    rules = executor._get_applicable_rules([])
    assert rules == []


def test_get_applicable_rules_unknown_id(executor):
    """Unknown rule IDs are silently ignored."""
    rules = executor._get_applicable_rules(["nonexistent-rule"])
    assert rules == []


# --- _build_prompt tests ---


def test_build_prompt_includes_task_description(executor, sample_task, sample_context):
    """Prompt contains the task description."""
    prompt = executor._build_prompt(
        sample_task,
        {"src/db.py": "def sync_func():\n    pass\n"},
        sample_context,
        [],
        {"indent": "4 spaces", "quotes": "double"},
    )
    assert "Convert sync functions to async" in prompt


def test_build_prompt_includes_rules_when_present(
    executor, sample_task_with_rules, sample_context
):
    """Prompt includes rule patterns when applicable_rules is non-empty."""
    rules = [r for r in REACT_RULES if r.rule_id == "async-parallel"]
    prompt = executor._build_prompt(
        sample_task_with_rules,
        {"src/app.tsx": "code"},
        sample_context,
        rules,
        {"indent": "2 spaces", "quotes": "single"},
    )
    assert "async-parallel" in prompt
    assert "Promise.all" in prompt
    assert "incorrect" in prompt.lower() or "Incorrect" in prompt


def test_build_prompt_includes_style(executor, sample_task, sample_context):
    """Prompt includes detected style instructions."""
    prompt = executor._build_prompt(
        sample_task,
        {"src/db.py": "code"},
        sample_context,
        [],
        {"indent": "2 spaces", "quotes": "single"},
    )
    assert "2 spaces" in prompt
    assert "single" in prompt.lower()


# --- execute tests (mocked API) ---


@patch("refactor_bot.agents.refactor_executor.Anthropic")
def test_execute_success(
    mock_anthropic_cls, sample_task, sample_repo_index, sample_context
):
    """execute() returns list[FileDiff] on successful API call."""
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.name = "generate_refactored_code"
    mock_tool_use.input = {
        "file_diffs": [
            {
                "file_path": "src/db.py",
                "modified_content": "async def async_func():\n    pass\n",
            }
        ]
    }
    mock_response = MagicMock()
    mock_response.content = [mock_tool_use]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_cls.return_value = mock_client

    executor = RefactorExecutor(api_key="test-key")
    diffs = executor.execute(sample_task, sample_repo_index, sample_context)

    assert isinstance(diffs, list)
    assert len(diffs) == 1
    assert isinstance(diffs[0], FileDiff)
    assert diffs[0].file_path == "src/db.py"
    assert diffs[0].task_id == "test-1"
    assert diffs[0].diff_text != ""


@patch("refactor_bot.agents.refactor_executor.Anthropic")
def test_execute_api_failure(
    mock_anthropic_cls, sample_task, sample_repo_index, sample_context
):
    """execute() raises ExecutionError on API failure."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API timeout")
    mock_anthropic_cls.return_value = mock_client

    executor = RefactorExecutor(api_key="test-key")
    with pytest.raises(ExecutionError):
        executor.execute(sample_task, sample_repo_index, sample_context)


@patch("refactor_bot.agents.refactor_executor.Anthropic")
def test_execute_no_tool_use_in_response(
    mock_anthropic_cls, sample_task, sample_repo_index, sample_context
):
    """execute() raises DiffGenerationError when no tool_use block found."""
    mock_text = MagicMock()
    mock_text.type = "text"
    mock_response = MagicMock()
    mock_response.content = [mock_text]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_cls.return_value = mock_client

    executor = RefactorExecutor(api_key="test-key")
    with pytest.raises(DiffGenerationError):
        executor.execute(sample_task, sample_repo_index, sample_context)


@patch("refactor_bot.agents.refactor_executor.Anthropic")
def test_execute_with_react_rules(
    mock_anthropic_cls, sample_task_with_rules, sample_repo_index, sample_context
):
    """execute() includes rule patterns in prompt when applicable_rules is set."""
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.name = "generate_refactored_code"
    mock_tool_use.input = {
        "file_diffs": [
            {
                "file_path": "src/app.tsx",
                "modified_content": (
                    "async function loadData() {\n"
                    "  const [a, b] = await Promise.all([fetchA(), fetchB()]);\n"
                    "}\n"
                ),
            }
        ]
    }
    mock_response = MagicMock()
    mock_response.content = [mock_tool_use]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_cls.return_value = mock_client

    executor = RefactorExecutor(api_key="test-key")
    diffs = executor.execute(
        sample_task_with_rules, sample_repo_index, sample_context
    )

    # Verify API was called with prompt containing rule info
    call_args = mock_client.messages.create.call_args
    messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
    prompt_text = messages[0]["content"]
    assert "async-parallel" in prompt_text
    assert "Promise.all" in prompt_text


# --- _validate_diffs tests ---


def test_validate_diffs_marks_valid(executor):
    """Valid diffs get is_valid=True."""
    from refactor_bot.utils.diff_generator import generate_unified_diff

    diff = FileDiff(
        file_path="test.txt",
        original_content="hello\n",
        modified_content="world\n",
        diff_text=generate_unified_diff("test.txt", "hello\n", "world\n"),
        task_id="t1",
    )
    result = executor._validate_diffs([diff])
    assert result[0].is_valid is True
    assert result[0].validation_error is None


def test_validate_diffs_marks_invalid(executor):
    """Invalid diffs get is_valid=False with error message."""
    diff = FileDiff(
        file_path="noexist.txt",
        original_content="x\n",
        modified_content="y\n",
        diff_text=(
            "--- a/noexist.txt\n+++ b/noexist.txt\n"
            "@@ -1 +1 @@\n-wrong\n+content\n"
        ),
        task_id="t1",
    )
    result = executor._validate_diffs([diff])
    assert result[0].is_valid is False
    assert result[0].validation_error is not None


# --- Exception hierarchy tests ---


def test_exception_hierarchy():
    """Verify exception inheritance chain."""
    assert issubclass(ExecutionError, AgentError)
    assert issubclass(DiffGenerationError, ExecutionError)
    assert issubclass(DiffValidationError, ExecutionError)
    assert issubclass(SourceFileError, ExecutionError)
