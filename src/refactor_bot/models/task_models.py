"""Task-related models for the refactor bot."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(str, Enum):
    """Status of a task in the refactor pipeline."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskNode(BaseModel):
    """Represents a single refactor task with dependencies."""

    model_config = ConfigDict(frozen=False)
    task_id: str
    description: str
    affected_files: list[str]
    dependencies: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    applicable_rules: list[str] = Field(default_factory=list)
    confidence_score: float | None = None
