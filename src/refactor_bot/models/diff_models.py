"""Models for representing file diffs."""

from pydantic import BaseModel, ConfigDict


class FileDiff(BaseModel):
    """Represents a unified diff for a single file."""

    model_config = ConfigDict(frozen=False)

    file_path: str  # Relative path from repo root
    original_content: str  # Source content before refactor
    modified_content: str  # Source content after refactor
    diff_text: str  # Unified diff output (git-compatible)
    is_valid: bool = False  # Set True after git apply --check passes
    validation_error: str | None = None  # Error message if validation fails
    task_id: str  # Which TaskNode generated this diff
