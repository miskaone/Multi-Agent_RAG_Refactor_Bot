"""Tests for TaskNode and TaskStatus models."""

import pytest
from pydantic import ValidationError

from refactor_bot.models.task_models import TaskNode, TaskStatus


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_task_status_has_all_values(self):
        """Test that TaskStatus has all 5 expected values."""
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.IN_PROGRESS == "in_progress"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.SKIPPED == "skipped"

    def test_task_status_enum_count(self):
        """Test that TaskStatus has exactly 5 values."""
        assert len(TaskStatus) == 5


class TestTaskNode:
    """Tests for TaskNode model."""

    def test_task_node_creation_required_fields_only(self):
        """Test TaskNode creation with only required fields."""
        task = TaskNode(
            task_id="task-1",
            description="Refactor authentication logic",
            affected_files=["src/auth.ts"],
        )
        assert task.task_id == "task-1"
        assert task.description == "Refactor authentication logic"
        assert task.affected_files == ["src/auth.ts"]

    def test_task_node_creation_all_fields(self):
        """Test TaskNode creation with all fields."""
        task = TaskNode(
            task_id="task-2",
            description="Update component",
            affected_files=["src/Component.tsx", "src/utils.ts"],
            dependencies=["task-1"],
            status=TaskStatus.IN_PROGRESS,
            applicable_rules=["rule-1", "rule-2"],
            confidence_score=0.95,
        )
        assert task.task_id == "task-2"
        assert task.description == "Update component"
        assert task.affected_files == ["src/Component.tsx", "src/utils.ts"]
        assert task.dependencies == ["task-1"]
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.applicable_rules == ["rule-1", "rule-2"]
        assert task.confidence_score == 0.95

    def test_task_node_defaults(self):
        """Test TaskNode default values."""
        task = TaskNode(
            task_id="task-3",
            description="Test task",
            affected_files=["test.ts"],
        )
        assert task.status == TaskStatus.PENDING
        assert task.dependencies == []
        assert task.applicable_rules == []
        assert task.confidence_score is None

    def test_task_node_mutability(self):
        """Test that TaskNode is mutable (frozen=False)."""
        task = TaskNode(
            task_id="task-4",
            description="Mutable task",
            affected_files=["file.ts"],
        )
        assert task.status == TaskStatus.PENDING

        # Change status
        task.status = TaskStatus.COMPLETED
        assert task.status == TaskStatus.COMPLETED

        # Change other fields
        task.dependencies = ["task-1"]
        assert task.dependencies == ["task-1"]

        task.applicable_rules = ["rule-1"]
        assert task.applicable_rules == ["rule-1"]

        task.confidence_score = 0.88
        assert task.confidence_score == 0.88

    def test_task_node_missing_task_id_raises_validation_error(self):
        """Test that missing task_id raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TaskNode(
                description="Task without ID",
                affected_files=["file.ts"],
            )
        assert "task_id" in str(exc_info.value)

    def test_task_node_missing_description_raises_validation_error(self):
        """Test that missing description raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TaskNode(
                task_id="task-5",
                affected_files=["file.ts"],
            )
        assert "description" in str(exc_info.value)

    def test_task_node_missing_affected_files_raises_validation_error(self):
        """Test that missing affected_files raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TaskNode(
                task_id="task-6",
                description="Task without files",
            )
        assert "affected_files" in str(exc_info.value)

    def test_task_node_empty_affected_files_allowed(self):
        """Test that empty affected_files list is allowed."""
        task = TaskNode(
            task_id="task-7",
            description="Task with empty files",
            affected_files=[],
        )
        assert task.affected_files == []

    def test_task_node_multiple_dependencies(self):
        """Test TaskNode with multiple dependencies."""
        task = TaskNode(
            task_id="task-8",
            description="Task with multiple deps",
            affected_files=["file.ts"],
            dependencies=["task-1", "task-2", "task-3"],
        )
        assert len(task.dependencies) == 3
        assert "task-1" in task.dependencies
        assert "task-2" in task.dependencies
        assert "task-3" in task.dependencies

    def test_task_node_multiple_applicable_rules(self):
        """Test TaskNode with multiple applicable rules."""
        task = TaskNode(
            task_id="task-9",
            description="Task with multiple rules",
            affected_files=["file.tsx"],
            applicable_rules=["REACT001", "REACT002", "REACT003"],
        )
        assert len(task.applicable_rules) == 3
        assert "REACT001" in task.applicable_rules
        assert "REACT002" in task.applicable_rules
        assert "REACT003" in task.applicable_rules
