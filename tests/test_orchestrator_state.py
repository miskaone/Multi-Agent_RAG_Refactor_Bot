"""Tests for orchestrator state module (Task 8)."""
import pytest

from refactor_bot.orchestrator.state import RefactorState, make_initial_state


class TestMakeInitialState:
    """Tests for the make_initial_state factory function."""

    def test_make_initial_state_defaults(self):
        """All 15 keys present with correct defaults."""
        state = make_initial_state("Refactor hooks", "/tmp/repo")

        assert state["directive"] == "Refactor hooks"
        assert state["repo_path"] == "/tmp/repo"
        assert state["max_retries"] == 3
        assert state["repo_index"] is None
        assert state["embedding_stats"] is None
        assert state["context_bundles"] == {}
        assert state["task_tree"] == []
        assert state["active_rules"] == []
        assert state["current_task_index"] == 0
        assert state["diffs"] == []
        assert state["audit_results"] is None
        assert state["test_results"] is None
        assert state["retry_counts"] == {}
        assert state["errors"] == []
        assert state["is_react_project"] is False

        # Verify all 15 keys are present
        assert len(state) == 15

    def test_make_initial_state_custom_retries(self):
        """max_retries can be overridden."""
        state = make_initial_state("Fix types", "/repo", max_retries=5)
        assert state["max_retries"] == 5

    def test_initial_state_diffs_empty_list(self):
        """diffs starts as an empty list (not None)."""
        state = make_initial_state("Refactor", "/tmp")
        assert state["diffs"] == []
        assert isinstance(state["diffs"], list)

    def test_initial_state_errors_empty_list(self):
        """errors starts as an empty list (not None)."""
        state = make_initial_state("Refactor", "/tmp")
        assert state["errors"] == []
        assert isinstance(state["errors"], list)
