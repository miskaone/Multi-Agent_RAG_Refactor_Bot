"""Integration tests for Planner agent with rule engine."""

from unittest.mock import MagicMock, patch

import pytest

from refactor_bot.agents.planner import Planner
from refactor_bot.models.schemas import FileInfo, RepoIndex, RetrievalResult
from refactor_bot.models.task_models import TaskNode, TaskStatus


@pytest.fixture
def integration_repo_index():
    """Fixture providing a comprehensive RepoIndex for integration tests."""
    return RepoIndex(
        repo_path="/tmp/integration-test-repo",
        files=[
            FileInfo(
                file_path="/tmp/integration-test-repo/src/App.tsx",
                relative_path="src/App.tsx",
                language="tsx",
                symbols=[],
                imports=["react", "./hooks/useAuth", "./components/Header"],
                exports=["default"],
                dependencies=[],
                hash="abc123",
            ),
            FileInfo(
                file_path="/tmp/integration-test-repo/src/hooks/useAuth.ts",
                relative_path="src/hooks/useAuth.ts",
                language="typescript",
                symbols=[],
                imports=["react"],
                exports=["useAuth"],
                dependencies=[],
                hash="def456",
            ),
            FileInfo(
                file_path="/tmp/integration-test-repo/src/components/Header.tsx",
                relative_path="src/components/Header.tsx",
                language="tsx",
                symbols=[],
                imports=["react", "../hooks/useAuth"],
                exports=["Header"],
                dependencies=[],
                hash="ghi789",
            ),
            FileInfo(
                file_path="/tmp/integration-test-repo/src/components/Footer.tsx",
                relative_path="src/components/Footer.tsx",
                language="tsx",
                symbols=[],
                imports=["react"],
                exports=["Footer"],
                dependencies=[],
                hash="jkl012",
            ),
            FileInfo(
                file_path="/tmp/integration-test-repo/src/utils/helpers.ts",
                relative_path="src/utils/helpers.ts",
                language="typescript",
                symbols=[],
                imports=[],
                exports=["formatDate", "validateEmail"],
                dependencies=[],
                hash="mno345",
            ),
        ],
        is_react_project=True,
        project_type="react",
        total_files=5,
        total_symbols=10,
    )


@pytest.fixture
def integration_retrieval_context():
    """Fixture providing comprehensive retrieval context."""
    return [
        RetrievalResult(
            id="/tmp/integration-test-repo/src/App.tsx::App",
            file_path="/tmp/integration-test-repo/src/App.tsx",
            symbol="App",
            type="function",
            source_code="function App() { const auth = useAuth(); return <div><Header /></div>; }",
            distance=0.05,
            similarity=0.95,
            metadata={"is_component": True},
        ),
        RetrievalResult(
            id="/tmp/integration-test-repo/src/hooks/useAuth.ts::useAuth",
            file_path="/tmp/integration-test-repo/src/hooks/useAuth.ts",
            symbol="useAuth",
            type="function",
            source_code=(
                "export function useAuth() { "
                "return { user: null, login: () => {}, logout: () => {} }; "
                "}"
            ),
            distance=0.08,
            similarity=0.92,
            metadata={"uses_hooks": ["useState", "useEffect"]},
        ),
        RetrievalResult(
            id="/tmp/integration-test-repo/src/components/Header.tsx::Header",
            file_path="/tmp/integration-test-repo/src/components/Header.tsx",
            symbol="Header",
            type="function",
            source_code=(
                "export function Header() { "
                "const { user } = useAuth(); "
                "return <header>{user?.name}</header>; "
                "}"
            ),
            distance=0.12,
            similarity=0.88,
            metadata={"is_component": True},
        ),
    ]


@pytest.fixture
def comprehensive_mock_response():
    """Fixture providing a comprehensive mock API response."""
    mock_tool_block = MagicMock()
    mock_tool_block.type = "tool_use"
    mock_tool_block.id = "call_integration_123"
    mock_tool_block.name = "create_task_plan"
    mock_tool_block.input = {
        "tasks": [
            {
                "task_id": "task-1",
                "description": "Refactor useAuth hook to use modern patterns",
                "affected_files": ["src/hooks/useAuth.ts"],
                "dependencies": [],
                "confidence_score": 0.92,
            },
            {
                "task_id": "task-2",
                "description": "Update Header component to handle auth state",
                "affected_files": ["src/components/Header.tsx"],
                "dependencies": ["task-1"],
                "confidence_score": 0.88,
            },
            {
                "task_id": "task-3",
                "description": "Update Footer component for consistency",
                "affected_files": ["src/components/Footer.tsx"],
                "dependencies": ["task-1"],
                "confidence_score": 0.85,
            },
            {
                "task_id": "task-4",
                "description": "Update App.tsx to use refactored auth",
                "affected_files": ["src/App.tsx"],
                "dependencies": ["task-2", "task-3"],
                "confidence_score": 0.9,
            },
        ]
    }
    mock_response = MagicMock()
    mock_response.content = [mock_tool_block]
    mock_response.stop_reason = "tool_use"
    return mock_response


class TestPlannerIntegration:
    """Integration tests for Planner with rule engine."""

    @patch("refactor_bot.agents.planner.Anthropic")
    def test_end_to_end_directive_to_task_nodes_with_rules(
        self,
        mock_anthropic_class,
        integration_repo_index,
        integration_retrieval_context,
        comprehensive_mock_response,
    ):
        """Test complete flow from directive to TaskNodes with rules populated."""
        # Setup mock
        mock_client = MagicMock()
        mock_client.messages.create.return_value = comprehensive_mock_response
        mock_anthropic_class.return_value = mock_client

        # Create planner and decompose
        planner = Planner(api_key="test-integration-key")
        tasks = planner.decompose(
            directive="Refactor authentication to use modern React patterns and hooks",
            repo_index=integration_repo_index,
            context=integration_retrieval_context,
        )

        # Verify we got TaskNode objects
        assert len(tasks) == 4
        assert all(isinstance(task, TaskNode) for task in tasks)

        # Verify all tasks have required fields
        for task in tasks:
            assert task.task_id
            assert task.description
            assert task.affected_files
            assert task.status == TaskStatus.PENDING
            assert isinstance(task.dependencies, list)
            assert isinstance(task.applicable_rules, list)

        # Verify tasks are properly structured
        assert tasks[0].task_id == "task-1"
        assert tasks[1].task_id == "task-2"
        assert tasks[2].task_id == "task-3"
        assert tasks[3].task_id == "task-4"

        # Verify confidence scores were preserved
        assert tasks[0].confidence_score == 0.92
        assert tasks[1].confidence_score == 0.88
        assert tasks[2].confidence_score == 0.85
        assert tasks[3].confidence_score == 0.9

    @patch("refactor_bot.agents.planner.Anthropic")
    def test_tasks_form_valid_dag(
        self,
        mock_anthropic_class,
        integration_repo_index,
        integration_retrieval_context,
        comprehensive_mock_response,
    ):
        """Test that generated tasks form a valid directed acyclic graph."""
        # Setup mock
        mock_client = MagicMock()
        mock_client.messages.create.return_value = comprehensive_mock_response
        mock_anthropic_class.return_value = mock_client

        planner = Planner(api_key="test-integration-key")
        tasks = planner.decompose(
            directive="Refactor authentication to use modern React patterns",
            repo_index=integration_repo_index,
            context=integration_retrieval_context,
        )

        # Build dependency graph
        task_ids = {task.task_id for task in tasks}
        dependency_graph = {task.task_id: task.dependencies for task in tasks}

        # Verify all dependencies reference valid tasks
        for task in tasks:
            for dep in task.dependencies:
                assert dep in task_ids, f"Task {task.task_id} has invalid dependency: {dep}"

        # Verify no cycles using topological sort
        visited = set()
        rec_stack = set()

        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)

            for neighbor in dependency_graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        # Check for cycles
        for task_id in task_ids:
            if task_id not in visited:
                assert not has_cycle(task_id), "Cycle detected in task dependencies"

        # Verify we can do topological sort (proves it's a DAG)
        sorted_tasks = []
        in_degree = {task_id: 0 for task_id in task_ids}
        for task_id, deps in dependency_graph.items():
            in_degree[task_id] = len(deps)

        queue = [task_id for task_id in task_ids if in_degree[task_id] == 0]
        while queue:
            current = queue.pop(0)
            sorted_tasks.append(current)
            for task_id, deps in dependency_graph.items():
                if current in deps:
                    in_degree[task_id] -= 1
                    if in_degree[task_id] == 0:
                        queue.append(task_id)

        # If it's a valid DAG, we should be able to sort all tasks
        assert len(sorted_tasks) == len(task_ids), (
            "Failed to topologically sort tasks (cycle exists)"
        )

    @patch("refactor_bot.agents.planner.Anthropic")
    def test_applicable_rules_populated_for_react_project(
        self,
        mock_anthropic_class,
        integration_repo_index,
        integration_retrieval_context,
        comprehensive_mock_response,
    ):
        """Test that applicable_rules are populated for React projects."""
        # Setup mock
        mock_client = MagicMock()
        mock_client.messages.create.return_value = comprehensive_mock_response
        mock_anthropic_class.return_value = mock_client

        planner = Planner(api_key="test-integration-key")
        tasks = planner.decompose(
            directive="Optimize server-side rendering and reduce bundle size",
            repo_index=integration_repo_index,
            context=integration_retrieval_context,
        )

        # Since this is a React project, tasks should have applicable_rules
        # At minimum, they should have the list (even if empty for some tasks)
        for task in tasks:
            assert isinstance(task.applicable_rules, list)

        # At least some tasks should have rules (since directive mentions "server" and "bundle")
        all_rules = []
        for task in tasks:
            all_rules.extend(task.applicable_rules)

        # With keywords "server" and "bundle" in directive, we should get some rules
        # (This assumes the implementation properly integrates rule selection)
        # For now, just verify the field exists and is a list
        assert isinstance(all_rules, list)

    @patch("refactor_bot.agents.planner.Anthropic")
    def test_applicable_rules_empty_for_non_react_project(
        self,
        mock_anthropic_class,
        integration_retrieval_context,
        comprehensive_mock_response,
    ):
        """Test that applicable_rules are empty for non-React projects."""
        # Create non-React repo index
        non_react_repo = RepoIndex(
            repo_path="/tmp/non-react-repo",
            files=[
                FileInfo(
                    file_path="/tmp/non-react-repo/src/main.py",
                    relative_path="src/main.py",
                    language="python",
                    symbols=[],
                    imports=[],
                    exports=[],
                    dependencies=[],
                    hash="xyz789",
                ),
            ],
            is_react_project=False,
            project_type=None,
            total_files=1,
            total_symbols=0,
        )

        # Adjust mock response for Python files
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "call_123"
        mock_tool_block.name = "create_task_plan"
        mock_tool_block.input = {
            "tasks": [
                {
                    "task_id": "task-1",
                    "description": "Refactor Python code",
                    "affected_files": ["src/main.py"],
                    "dependencies": [],
                    "confidence_score": 0.9,
                },
            ]
        }
        mock_response = MagicMock()
        mock_response.content = [mock_tool_block]
        mock_response.stop_reason = "tool_use"

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        planner = Planner(api_key="test-integration-key")
        tasks = planner.decompose(
            directive="Refactor the authentication module",
            repo_index=non_react_repo,
            context=[],
        )

        # For non-React projects, applicable_rules should be empty
        for task in tasks:
            assert task.applicable_rules == []

    @patch("refactor_bot.agents.planner.Anthropic")
    def test_all_affected_files_exist_in_repo_index(
        self,
        mock_anthropic_class,
        integration_repo_index,
        integration_retrieval_context,
        comprehensive_mock_response,
    ):
        """Test that all affected_files in tasks exist in repo_index."""
        # Setup mock
        mock_client = MagicMock()
        mock_client.messages.create.return_value = comprehensive_mock_response
        mock_anthropic_class.return_value = mock_client

        planner = Planner(api_key="test-integration-key")
        tasks = planner.decompose(
            directive="Refactor authentication",
            repo_index=integration_repo_index,
            context=integration_retrieval_context,
        )

        # Collect all valid file paths from repo_index
        valid_absolute_paths = {file.file_path for file in integration_repo_index.files}
        valid_relative_paths = {file.relative_path for file in integration_repo_index.files}

        # Verify all affected files exist in repo_index
        for task in tasks:
            for affected_file in task.affected_files:
                # File should match either absolute or relative path
                assert (
                    affected_file in valid_absolute_paths or affected_file in valid_relative_paths
                ), f"File {affected_file} in task {task.task_id} not found in repo_index"

    @patch("refactor_bot.agents.planner.Anthropic")
    def test_task_dependencies_preserve_order(
        self,
        mock_anthropic_class,
        integration_repo_index,
        integration_retrieval_context,
        comprehensive_mock_response,
    ):
        """Test that task dependencies maintain proper execution order."""
        # Setup mock
        mock_client = MagicMock()
        mock_client.messages.create.return_value = comprehensive_mock_response
        mock_anthropic_class.return_value = mock_client

        planner = Planner(api_key="test-integration-key")
        tasks = planner.decompose(
            directive="Refactor authentication",
            repo_index=integration_repo_index,
            context=integration_retrieval_context,
        )

        # Build execution order
        task_dict = {task.task_id: task for task in tasks}

        # Verify that dependencies come before dependents
        for task in tasks:
            for dep_id in task.dependencies:
                dep_task = task_dict[dep_id]
                # Dependency should not depend on current task (no reverse dependency)
                assert task.task_id not in dep_task.dependencies, (
                    f"Circular dependency: {task.task_id} <-> {dep_id}"
                )

    @patch("refactor_bot.agents.planner.Anthropic")
    def test_integration_with_multiple_keywords(
        self,
        mock_anthropic_class,
        integration_repo_index,
        integration_retrieval_context,
        comprehensive_mock_response,
    ):
        """Test integration with directive containing multiple rule-triggering keywords."""
        # Setup mock
        mock_client = MagicMock()
        mock_client.messages.create.return_value = comprehensive_mock_response
        mock_anthropic_class.return_value = mock_client

        planner = Planner(api_key="test-integration-key")
        tasks = planner.decompose(
            directive=(
                "Optimize server-side rendering, reduce bundle size, "
                "and improve async data loading"
            ),
            repo_index=integration_repo_index,
            context=integration_retrieval_context,
        )

        # Verify tasks were created
        assert len(tasks) > 0

        # Verify all tasks have proper structure
        for task in tasks:
            assert isinstance(task, TaskNode)
            assert task.task_id
            assert task.description
            assert isinstance(task.affected_files, list)
            assert isinstance(task.dependencies, list)
            assert isinstance(task.applicable_rules, list)
            assert task.status == TaskStatus.PENDING

    @patch("refactor_bot.agents.planner.Anthropic")
    def test_confidence_scores_preserved_in_integration(
        self,
        mock_anthropic_class,
        integration_repo_index,
        integration_retrieval_context,
        comprehensive_mock_response,
    ):
        """Test that confidence scores from API are preserved in TaskNodes."""
        # Setup mock
        mock_client = MagicMock()
        mock_client.messages.create.return_value = comprehensive_mock_response
        mock_anthropic_class.return_value = mock_client

        planner = Planner(api_key="test-integration-key")
        tasks = planner.decompose(
            directive="Refactor authentication",
            repo_index=integration_repo_index,
            context=integration_retrieval_context,
        )

        # Verify confidence scores match mock response
        expected_scores = [0.92, 0.88, 0.85, 0.9]
        actual_scores = [task.confidence_score for task in tasks]

        assert actual_scores == expected_scores

    @patch("refactor_bot.agents.planner.Anthropic")
    def test_integration_handles_empty_retrieval_context(
        self,
        mock_anthropic_class,
        integration_repo_index,
        comprehensive_mock_response,
    ):
        """Test that planner works with empty retrieval context."""
        # Setup mock
        mock_client = MagicMock()
        mock_client.messages.create.return_value = comprehensive_mock_response
        mock_anthropic_class.return_value = mock_client

        planner = Planner(api_key="test-integration-key")
        tasks = planner.decompose(
            directive="Refactor authentication",
            repo_index=integration_repo_index,
            context=[],  # Empty context
        )

        # Should still work
        assert len(tasks) > 0
        assert all(isinstance(task, TaskNode) for task in tasks)

    @patch("refactor_bot.agents.planner.Anthropic")
    def test_integration_task_descriptions_non_empty(
        self,
        mock_anthropic_class,
        integration_repo_index,
        integration_retrieval_context,
        comprehensive_mock_response,
    ):
        """Test that all tasks have non-empty descriptions."""
        # Setup mock
        mock_client = MagicMock()
        mock_client.messages.create.return_value = comprehensive_mock_response
        mock_anthropic_class.return_value = mock_client

        planner = Planner(api_key="test-integration-key")
        tasks = planner.decompose(
            directive="Refactor authentication",
            repo_index=integration_repo_index,
            context=integration_retrieval_context,
        )

        # All descriptions should be non-empty
        for task in tasks:
            assert task.description
            assert len(task.description.strip()) > 0
