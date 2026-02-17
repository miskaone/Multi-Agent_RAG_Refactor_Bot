"""Tests for FileDiff model."""

import pytest

from refactor_bot.models.diff_models import FileDiff


def test_file_diff_creation():
    """FileDiff can be created with all required fields."""
    diff = FileDiff(
        file_path="src/app.tsx",
        original_content="const x = 1;\n",
        modified_content="const x = 2;\n",
        diff_text="--- a/src/app.tsx\n+++ b/src/app.tsx\n@@ ...",
        task_id="task-1",
    )
    assert diff.file_path == "src/app.tsx"
    assert diff.is_valid is False
    assert diff.validation_error is None


def test_file_diff_mutability():
    """FileDiff.is_valid and validation_error can be updated after creation."""
    diff = FileDiff(
        file_path="a.py",
        original_content="",
        modified_content="",
        diff_text="",
        task_id="t1",
    )
    diff.is_valid = True
    assert diff.is_valid is True
    diff.validation_error = "some error"
    assert diff.validation_error == "some error"


def test_file_diff_defaults():
    """is_valid defaults to False, validation_error defaults to None."""
    diff = FileDiff(
        file_path="a.py",
        original_content="x",
        modified_content="y",
        diff_text="d",
        task_id="t1",
    )
    assert diff.is_valid is False
    assert diff.validation_error is None
