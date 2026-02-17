"""Exceptions for agent operations."""


class AgentError(Exception):
    """Base exception for all agent operations."""


class PlanningError(AgentError):
    """Raised when task decomposition fails."""


class DirectiveValidationError(AgentError):
    """Raised when the input directive is invalid or potentially malicious."""


class TaskDependencyError(AgentError):
    """Raised when task dependencies form a cycle or reference missing tasks."""


class ExecutionError(AgentError):
    """Base exception for refactor execution operations."""


class DiffGenerationError(ExecutionError):
    """Raised when diff generation fails."""


class DiffValidationError(ExecutionError):
    """Raised when git apply --check fails."""


class SourceFileError(ExecutionError):
    """Raised when source file cannot be read or parsed."""


class AuditError(AgentError):
    """Raised when consistency audit fails to complete."""


class TestValidationError(AgentError):
    """Raised when test validation fails to complete."""
