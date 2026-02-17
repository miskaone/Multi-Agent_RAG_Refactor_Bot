"""Exceptions for orchestrator operations.

Note: Names chosen to avoid collisions with stdlib and framework exceptions (L017).
"""


class OrchestratorError(Exception):
    """Base exception for all orchestrator operations."""


class GraphBuildError(OrchestratorError):
    """Raised when graph construction fails."""
