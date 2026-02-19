"""Tests for TestValidator agent."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from refactor_bot.agents.test_validator import (
    DEFAULT_TIMEOUT,
    JEST_SUMMARY_RE,
    VITEST_SUMMARY_RE,
    TestValidator,
)
from refactor_bot.agents.exceptions import TestValidationError
from refactor_bot.models import FileDiff
from refactor_bot.models.report_models import BreakingChange, TestReport, TestRunResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_file_diff(
    file_path: str,
    modified_content: str = "export const x = 1;\n",
    original_content: str = "export const x = 0;\n",
    task_id: str = "task-1",
) -> FileDiff:
    return FileDiff(
        file_path=file_path,
        original_content=original_content,
        modified_content=modified_content,
        diff_text="",
        task_id=task_id,
    )


def _write_package_json(directory: Path, content: dict) -> None:
    (directory / "package.json").write_text(json.dumps(content))


def _make_test_run_result(
    runner: str = "vitest",
    exit_code: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> TestRunResult:
    return TestRunResult(
        runner=runner,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
    )


# ---------------------------------------------------------------------------
# Runner detection tests
# ---------------------------------------------------------------------------


def test_validator_detects_runner_vitest(tmp_path):
    """package.json with 'test': 'vitest' → _detect_runner returns 'vitest'."""
    _write_package_json(
        tmp_path,
        {"scripts": {"test": "vitest"}},
    )
    validator = TestValidator(api_key="test-key")
    result = validator._detect_runner(str(tmp_path))
    assert result == "vitest"


def test_validator_detects_runner_npm_test(tmp_path):
    """package.json with 'test': 'jest' → _detect_runner returns 'npm_test'."""
    _write_package_json(
        tmp_path,
        {"scripts": {"test": "jest"}},
    )
    validator = TestValidator(api_key="test-key")
    result = validator._detect_runner(str(tmp_path))
    assert result == "npm_test"


def test_validator_detects_no_runner(tmp_path):
    """package.json with no scripts key → _detect_runner returns None."""
    _write_package_json(tmp_path, {"name": "my-project"})
    validator = TestValidator(api_key="test-key")
    result = validator._detect_runner(str(tmp_path))
    assert result is None


def test_validator_no_package_json(tmp_path):
    """Empty directory (no package.json) → _detect_runner returns None."""
    validator = TestValidator(api_key="test-key")
    result = validator._detect_runner(str(tmp_path))
    assert result is None


@patch("refactor_bot.agents.test_validator.openai.OpenAI")
@patch("refactor_bot.agents.test_validator.Anthropic")
def test_validator_prefers_anthropic_in_auto_when_available(
    mock_anthropic, mock_openai, monkeypatch
):
    """Validator auto provider prefers Anthropic when ANTHROPIC_API_KEY is present."""
    mock_anthropic.return_value = object()
    mock_openai.return_value = object()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")

    validator = TestValidator(api_key=None)
    assert validator._primary_provider() == "anthropic"


@patch("refactor_bot.agents.test_validator.openai.OpenAI")
@patch("refactor_bot.agents.test_validator.Anthropic")
def test_validator_openai_provider_chain_with_fallback(mock_anthropic, mock_openai):
    """OpenAI primary with OpenAI fallback config should not duplicate provider."""
    mock_anthropic.return_value = None
    mock_openai.return_value = object()

    validator = TestValidator(
        api_key="openai-key",
        llm_provider="openai",
        llm_fallback_provider="openai",
        allow_fallback=True,
    )
    assert validator._provider_chain() == ["openai"]


# ---------------------------------------------------------------------------
# _run_tests tests
# ---------------------------------------------------------------------------


def test_validator_run_tests_success(tmp_path):
    """Mock subprocess.run returning exit code 0 → TestRunResult.exit_code == 0."""
    _write_package_json(tmp_path, {"scripts": {"test": "vitest"}})
    validator = TestValidator(api_key="test-key")

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "Tests  3 passed (3)\n"
    mock_proc.stderr = ""

    with patch("subprocess.run", return_value=mock_proc) as mock_run:
        result = validator._run_tests(str(tmp_path), "vitest")

    assert result.exit_code == 0
    assert result.runner == "vitest"
    assert result.stdout == "Tests  3 passed (3)\n"


# ---------------------------------------------------------------------------
# Output parsing tests
# ---------------------------------------------------------------------------


def test_validator_parse_vitest_output():
    """stdout 'Tests  1 failed | 3 passed (4)' → failed==1, passed==3."""
    validator = TestValidator(api_key="test-key")
    result = _make_test_run_result(
        runner="vitest",
        stdout="Tests  1 failed | 3 passed (4)\n",
    )
    parsed = validator._parse_test_output(result)
    assert parsed.failed == 1
    assert parsed.passed == 3


def test_validator_parse_jest_output():
    """stdout 'Tests: 1 failed, 5 passed, 6 total' → failed==1, passed==5."""
    validator = TestValidator(api_key="test-key")
    result = _make_test_run_result(
        runner="npm_test",
        stdout="Tests: 1 failed, 5 passed, 6 total\n",
    )
    parsed = validator._parse_test_output(result)
    assert parsed.failed == 1
    assert parsed.passed == 5


# ---------------------------------------------------------------------------
# Breaking changes tests
# ---------------------------------------------------------------------------


def test_validator_compute_breaking_changes():
    """Pre-run with 0 failures; post-run with 1 FAIL line → 1 BreakingChange."""
    validator = TestValidator(api_key="test-key")

    pre = _make_test_run_result(
        runner="vitest",
        exit_code=0,
        stdout="Tests  0 failed | 5 passed (5)\n",
    )
    post = _make_test_run_result(
        runner="vitest",
        exit_code=1,
        stdout="FAIL src/counter.test.ts\nTests  1 failed | 4 passed (5)\n",
    )

    breaking = validator._compute_breaking_changes(pre, post)

    assert len(breaking) == 1
    assert isinstance(breaking[0], BreakingChange)


# ---------------------------------------------------------------------------
# Path traversal & apply diffs tests
# ---------------------------------------------------------------------------


def test_validator_path_traversal_rejected(tmp_path):
    """file_path='../../etc/passwd' → TestValidationError raised by _apply_diffs_to_temp."""
    # Create a minimal source file so the repo dir is non-empty
    (tmp_path / "index.ts").write_text("export const x = 1;\n")

    validator = TestValidator(api_key="test-key")
    traversal_diff = _make_file_diff("../../etc/passwd", "malicious content\n")

    with pytest.raises(TestValidationError):
        validator._apply_diffs_to_temp(str(tmp_path), [traversal_diff])


def test_validator_apply_diffs_to_temp(tmp_path):
    """Valid diff with an in-repo file_path writes modified_content to temp dir."""
    # Put a real file in the source repo
    src_file = tmp_path / "src" / "counter.ts"
    src_file.parent.mkdir(parents=True)
    src_file.write_text("export const count = 0;\n")

    validator = TestValidator(api_key="test-key")
    diff = _make_file_diff(
        "src/counter.ts",
        "export const count = 1;\n",
        original_content="export const count = 0;\n",
    )

    temp_dir = validator._apply_diffs_to_temp(str(tmp_path), [diff])

    try:
        patched_file = Path(temp_dir) / "src" / "counter.ts"
        assert patched_file.exists()
        assert patched_file.read_text() == "export const count = 1;\n"
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# LLM fallback tests
# ---------------------------------------------------------------------------


@patch("refactor_bot.agents.test_validator.Anthropic")
def test_validator_llm_fallback_when_no_runner(mock_anthropic_cls, tmp_path):
    """No runner + mocked Anthropic → report.runner_available is False,
    report.llm_analysis is not None."""
    # No package.json → no runner
    _write_package_json(tmp_path, {"name": "no-test-project"})

    # Set up mock Anthropic client
    mock_message_content = MagicMock()
    mock_message_content.text = "LLM analysis: no obvious regressions detected."

    mock_response = MagicMock()
    mock_response.content = [mock_message_content]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_cls.return_value = mock_client

    validator = TestValidator(api_key="test-key")
    diff = _make_file_diff("src/helper.ts", "export function helper() { return 1; }\n")

    report = validator.validate(str(tmp_path), [diff])

    assert report.runner_available is False
    assert report.llm_analysis is not None
    assert len(report.llm_analysis) > 0


# ---------------------------------------------------------------------------
# validate() path-validation tests
# ---------------------------------------------------------------------------


def test_validator_validate_missing_repo_path():
    """validate() with a non-existent repo_path → raises TestValidationError."""
    validator = TestValidator(api_key="test-key")

    with pytest.raises(TestValidationError):
        validator.validate("/this/path/does/not/exist/at/all", [])


# ---------------------------------------------------------------------------
# Constant / regex sanity tests
# ---------------------------------------------------------------------------


def test_default_timeout_value():
    """DEFAULT_TIMEOUT must be 120 seconds."""
    assert DEFAULT_TIMEOUT == 120


def test_vitest_summary_re_matches():
    """VITEST_SUMMARY_RE correctly extracts failed and passed counts."""
    m = VITEST_SUMMARY_RE.search("Tests  2 failed | 8 passed (10)")
    assert m is not None
    assert m.group(1) == "2"
    assert m.group(2) == "8"


def test_jest_summary_re_matches():
    """JEST_SUMMARY_RE correctly extracts failed and passed counts."""
    m = JEST_SUMMARY_RE.search("Tests: 3 failed, 7 passed, 10 total")
    assert m is not None
    # Group 1 is the optional failed count
    assert m.group(1) == "3"
    assert m.group(2) == "7"
