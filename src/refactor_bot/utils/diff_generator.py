"""Utilities for generating and validating code diffs."""

import difflib
import subprocess
import tempfile
from pathlib import Path


def generate_unified_diff(
    file_path: str,
    original_content: str,
    modified_content: str,
) -> str:
    """Generate a git-compatible unified diff.

    Args:
        file_path: Relative path from repo root (e.g. "src/app.tsx").
        original_content: File content before refactor.
        modified_content: File content after refactor.

    Returns:
        Unified diff string with a/ b/ prefixes. Empty string if no changes.
    """
    # Return empty string if content is identical
    if original_content == modified_content:
        return ""

    # Split into lines, preserving line endings
    original_lines = original_content.splitlines(keepends=True)
    modified_lines = modified_content.splitlines(keepends=True)

    # Generate unified diff with lineterm="" to avoid adding extra newlines
    diff_gen = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm="",
    )

    # Convert generator to list and join
    # Each line from diff already has its newline from keepends=True
    # So we need to strip the trailing newlines before joining with \n
    diff_lines = []
    for line in diff_gen:
        # Remove trailing newline if present (from keepends=True)
        if line.endswith('\n'):
            diff_lines.append(line[:-1])
        else:
            diff_lines.append(line)

    return "\n".join(diff_lines)


def validate_diff_with_git(
    diff_text: str,
    original_files: dict[str, str],
) -> tuple[bool, str]:
    """Validate a diff by running git apply --check in a temp repo.

    Args:
        diff_text: The unified diff to validate.
        original_files: Mapping of {relative_path: content} for files
            referenced in the diff. These are written into a temp git repo.

    Returns:
        Tuple of (is_valid, error_message). error_message is empty on success.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Write original files (validate paths to prevent traversal)
        resolved_tmp = tmp_path.resolve()
        for relative_path, content in original_files.items():
            # Reject paths with traversal sequences
            if ".." in Path(relative_path).parts:
                continue
            file_path = (tmp_path / relative_path).resolve()
            # Ensure resolved path is within tmpdir
            if not file_path.is_relative_to(resolved_tmp):
                continue
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)

        # Initialize git repo
        subprocess.run(
            ["git", "init"],
            cwd=tmpdir,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmpdir,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmpdir,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=tmpdir,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=tmpdir,
            capture_output=True,
            check=True,
        )

        # Run git apply --check
        # Ensure diff ends with newline for git apply
        diff_input = diff_text if diff_text.endswith('\n') else diff_text + '\n'
        result = subprocess.run(
            ["git", "apply", "--check"],
            input=diff_input.encode("utf-8"),
            cwd=tmpdir,
            capture_output=True,
        )

        is_valid = result.returncode == 0
        error_message = result.stderr.decode("utf-8") if not is_valid else ""

        return is_valid, error_message


def detect_code_style(source_code: str) -> dict[str, str]:
    """Detect code style conventions from source code.

    Args:
        source_code: The source code to analyse.

    Returns:
        Dict with keys:
            "indent": e.g. "2 spaces", "4 spaces", "tabs"
            "quotes": "single" or "double"
    """
    # Default values
    indent_style = "4 spaces"
    quote_style = "double"

    # Return defaults for empty source
    if not source_code:
        return {"indent": indent_style, "quotes": quote_style}

    # Detect indentation
    indent_counts: dict[int, int] = {}
    lines = source_code.splitlines()

    for line in lines:
        if not line or not line[0].isspace():
            continue

        # Count leading spaces
        spaces = 0
        for char in line:
            if char == " ":
                spaces += 1
            elif char == "\t":
                # Found a tab - assume tabs
                indent_style = "tabs"
                break
            else:
                break

        if indent_style == "tabs":
            break

        if spaces > 0:
            indent_counts[spaces] = indent_counts.get(spaces, 0) + 1

    # If we didn't find tabs, determine most common space indent
    if indent_style != "tabs" and indent_counts:
        # Find the smallest non-zero indent level (likely the base indent)
        base_indent = min(indent_counts.keys())
        indent_style = f"{base_indent} spaces"

    # Detect quotes
    single_quote_count = source_code.count("'")
    double_quote_count = source_code.count('"')

    if single_quote_count > double_quote_count:
        quote_style = "single"
    else:
        quote_style = "double"

    return {"indent": indent_style, "quotes": quote_style}
