"""Tests for diff_generator utility functions."""

import pytest

from refactor_bot.utils.diff_generator import (
    detect_code_style,
    generate_unified_diff,
    validate_diff_with_git,
)


def test_generate_unified_diff_basic():
    """Basic diff has --- a/ and +++ b/ headers and changed lines."""
    diff = generate_unified_diff(
        "src/app.py",
        "def sync_func():\n    pass\n",
        "async def async_func():\n    pass\n",
    )
    assert diff.startswith("--- a/src/app.py")
    assert "+++ b/src/app.py" in diff
    assert "-def sync_func():" in diff
    assert "+async def async_func():" in diff


def test_generate_unified_diff_no_changes():
    """Identical content returns empty string."""
    diff = generate_unified_diff("a.py", "hello\n", "hello\n")
    assert diff == ""


def test_generate_unified_diff_multiline():
    """Diff with multiple changed lines."""
    original = "line1\nline2\nline3\n"
    modified = "line1\nchanged\nline3\n"
    diff = generate_unified_diff("f.py", original, modified)
    assert "-line2" in diff
    assert "+changed" in diff


def test_validate_diff_with_git_success():
    """Valid diff passes git apply --check."""
    original = "hello\n"
    modified = "world\n"
    diff = generate_unified_diff("test.txt", original, modified)
    is_valid, error = validate_diff_with_git(diff, {"test.txt": original})
    assert is_valid is True
    assert error == ""


def test_validate_diff_with_git_invalid():
    """Invalid diff fails git apply --check."""
    # Create a diff that doesn't match the actual file content
    bad_diff = "--- a/test.txt\n+++ b/test.txt\n@@ -1 +1 @@\n-wrong\n+content\n"
    is_valid, error = validate_diff_with_git(bad_diff, {"test.txt": "hello\n"})
    assert is_valid is False
    assert error != ""


def test_detect_code_style_two_space_indent():
    """Detects 2-space indentation."""
    code = "function f() {\n  const x = 1;\n  return x;\n}\n"
    style = detect_code_style(code)
    assert style["indent"] == "2 spaces"


def test_detect_code_style_four_space_indent():
    """Detects 4-space indentation."""
    code = "def f():\n    x = 1\n    return x\n"
    style = detect_code_style(code)
    assert style["indent"] == "4 spaces"


def test_detect_code_style_single_quotes():
    """Detects single quote preference."""
    code = "const x = 'hello';\nconst y = 'world';\n"
    style = detect_code_style(code)
    assert style["quotes"] == "single"


def test_detect_code_style_double_quotes():
    """Detects double quote preference."""
    code = 'const x = "hello";\nconst y = "world";\n'
    style = detect_code_style(code)
    assert style["quotes"] == "double"


def test_detect_code_style_empty_source():
    """Empty source returns defaults."""
    style = detect_code_style("")
    assert "indent" in style
    assert "quotes" in style
