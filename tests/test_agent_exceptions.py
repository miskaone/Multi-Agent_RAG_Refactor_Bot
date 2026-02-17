"""Tests for agent exception classes."""

import pytest

from refactor_bot.agents.exceptions import (
    AgentError,
    DirectiveValidationError,
    PlanningError,
    TaskDependencyError,
)


class TestAgentExceptions:
    """Tests for agent exception hierarchy."""

    def test_agent_error_exists(self):
        """Test that AgentError base exception exists."""
        exc = AgentError("Base error")
        assert isinstance(exc, Exception)
        assert str(exc) == "Base error"

    def test_planning_error_exists(self):
        """Test that PlanningError exists."""
        exc = PlanningError("Planning failed")
        assert isinstance(exc, Exception)
        assert str(exc) == "Planning failed"

    def test_directive_validation_error_exists(self):
        """Test that DirectiveValidationError exists."""
        exc = DirectiveValidationError("Invalid directive")
        assert isinstance(exc, Exception)
        assert str(exc) == "Invalid directive"

    def test_task_dependency_error_exists(self):
        """Test that TaskDependencyError exists."""
        exc = TaskDependencyError("Cyclic dependency")
        assert isinstance(exc, Exception)
        assert str(exc) == "Cyclic dependency"

    def test_planning_error_inherits_from_agent_error(self):
        """Test that PlanningError inherits from AgentError."""
        exc = PlanningError("Planning failed")
        assert isinstance(exc, AgentError)
        assert isinstance(exc, Exception)

    def test_directive_validation_error_inherits_from_agent_error(self):
        """Test that DirectiveValidationError inherits from AgentError."""
        exc = DirectiveValidationError("Invalid directive")
        assert isinstance(exc, AgentError)
        assert isinstance(exc, Exception)

    def test_task_dependency_error_inherits_from_agent_error(self):
        """Test that TaskDependencyError inherits from AgentError."""
        exc = TaskDependencyError("Cyclic dependency")
        assert isinstance(exc, AgentError)
        assert isinstance(exc, Exception)

    def test_exception_message_propagation_agent_error(self):
        """Test that AgentError message propagates correctly."""
        message = "Something went wrong in agent"
        exc = AgentError(message)
        assert str(exc) == message

    def test_exception_message_propagation_planning_error(self):
        """Test that PlanningError message propagates correctly."""
        message = "Failed to decompose tasks"
        exc = PlanningError(message)
        assert str(exc) == message

    def test_exception_message_propagation_directive_validation_error(self):
        """Test that DirectiveValidationError message propagates correctly."""
        message = "Directive contains malicious content"
        exc = DirectiveValidationError(message)
        assert str(exc) == message

    def test_exception_message_propagation_task_dependency_error(self):
        """Test that TaskDependencyError message propagates correctly."""
        message = "Task dependency cycle detected: task-1 -> task-2 -> task-1"
        exc = TaskDependencyError(message)
        assert str(exc) == message

    def test_exceptions_can_be_raised_and_caught(self):
        """Test that exceptions can be raised and caught."""
        with pytest.raises(AgentError) as exc_info:
            raise AgentError("Test error")
        assert str(exc_info.value) == "Test error"

        with pytest.raises(PlanningError) as exc_info:
            raise PlanningError("Planning test error")
        assert str(exc_info.value) == "Planning test error"

        with pytest.raises(DirectiveValidationError) as exc_info:
            raise DirectiveValidationError("Validation test error")
        assert str(exc_info.value) == "Validation test error"

        with pytest.raises(TaskDependencyError) as exc_info:
            raise TaskDependencyError("Dependency test error")
        assert str(exc_info.value) == "Dependency test error"

    def test_catch_planning_error_as_agent_error(self):
        """Test that PlanningError can be caught as AgentError."""
        with pytest.raises(AgentError):
            raise PlanningError("Planning failed")

    def test_catch_directive_validation_error_as_agent_error(self):
        """Test that DirectiveValidationError can be caught as AgentError."""
        with pytest.raises(AgentError):
            raise DirectiveValidationError("Invalid directive")

    def test_catch_task_dependency_error_as_agent_error(self):
        """Test that TaskDependencyError can be caught as AgentError."""
        with pytest.raises(AgentError):
            raise TaskDependencyError("Cyclic dependency")
