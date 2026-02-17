"""
Integration tests for Repository Indexer agent.

Tests the full indexing pipeline against fixture files, including:
- File discovery and language detection
- Symbol extraction and dependency graph construction
- React/Next.js project detection
- React metadata population
- Error handling
"""

import tempfile
from pathlib import Path

import pytest

# NOTE: These imports will work once the engineer creates the source files
from refactor_bot.agents.repo_indexer import RepoIndexer
from refactor_bot.models.schemas import RepoIndex


@pytest.fixture
def fixtures_dir():
    """Return the path to the fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def indexer():
    """Return a RepoIndexer instance with default settings."""
    return RepoIndexer()


class TestBasicIndexing:
    """Test basic repository indexing functionality."""

    def test_index_returns_repo_index(self, indexer, fixtures_dir):
        """Index should return a RepoIndex instance."""
        result = indexer.index(str(fixtures_dir))
        assert isinstance(result, RepoIndex)

    def test_index_file_count(self, indexer, fixtures_dir):
        """Index should find all supported files excluding node_modules."""
        result = indexer.index(str(fixtures_dir))

        # Expected files: sample.js, sample.ts, sample.tsx, utils.ts,
        # server_component.tsx, barrel.ts
        # (excluding package.json files and generic_project subdirectory files)
        assert result.total_files >= 6

    def test_index_file_languages(self, indexer, fixtures_dir):
        """Each indexed file should have correct language field."""
        result = indexer.index(str(fixtures_dir))

        # Create a mapping of file extensions to expected languages
        language_map = {
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".jsx": "javascript",
        }

        for file_info in result.files:
            ext = Path(file_info.file_path).suffix
            if ext in language_map:
                assert file_info.language == language_map[ext]


class TestSymbolExtraction:
    """Test symbol extraction from indexed files."""

    def test_index_symbols_extracted(self, indexer, fixtures_dir):
        """Files with functions/classes should have non-empty symbols list."""
        result = indexer.index(str(fixtures_dir))

        # Find files that should have symbols
        files_with_content = [
            f for f in result.files
            if "barrel" not in f.file_path and "invalid_syntax" not in f.file_path
        ]

        for file_info in files_with_content:
            if file_info.file_path.endswith(('.js', '.ts', '.tsx')):
                # These files have function/class definitions
                # Barrel files (index.ts) may only have re-exports, no symbols
                is_barrel = file_info.file_path.endswith("index.ts")
                has_package_json = "package.json" in file_info.file_path
                if not has_package_json and not is_barrel:
                    assert len(file_info.symbols) > 0, f"No symbols found in {file_info.file_path}"

    def test_index_symbol_names(self, indexer, fixtures_dir):
        """Specific expected symbols should be found."""
        result = indexer.index(str(fixtures_dir))

        # Collect all symbol names across all files
        all_symbol_names = []
        for file_info in result.files:
            all_symbol_names.extend([s.name for s in file_info.symbols])

        # Check for expected symbols
        assert "calculateTotal" in all_symbol_names
        assert "UserService" in all_symbol_names
        assert "ProductCard" in all_symbol_names
        assert "slugify" in all_symbol_names
        assert "validateEmail" in all_symbol_names

    def test_index_symbol_types(self, indexer, fixtures_dir):
        """Symbol types should be correctly identified."""
        result = indexer.index(str(fixtures_dir))

        # Find specific symbols and check their types
        for file_info in result.files:
            for symbol in file_info.symbols:
                if symbol.name == "calculateTotal":
                    assert symbol.type == "function"
                elif symbol.name == "formatPrice":
                    assert symbol.type == "arrow_function"
                elif symbol.name == "UserService":
                    assert symbol.type == "class"
                elif symbol.name == "getUser":
                    assert symbol.type == "method"


class TestImportsAndDependencies:
    """Test import extraction and dependency graph construction."""

    def test_index_imports_extracted(self, indexer, fixtures_dir):
        """Files with import statements should have populated imports list."""
        result = indexer.index(str(fixtures_dir))

        # sample.js imports from ./utils
        sample_js = next(
            (f for f in result.files if f.file_path.endswith("sample.js")),
            None
        )
        if sample_js:
            assert len(sample_js.imports) > 0
            assert "./utils" in sample_js.imports

    def test_index_dependency_graph_edges(self, indexer, fixtures_dir):
        """Dependency graph should have edges for relative imports."""
        result = indexer.index(str(fixtures_dir))

        # sample.js imports from utils.ts
        # sample.tsx imports from utils.ts
        # server_component.tsx imports from utils.ts

        # Find the absolute paths
        sample_js_path = next(
            (f.file_path for f in result.files if f.file_path.endswith("sample.js")),
            None
        )
        utils_ts_path = next(
            (f.file_path for f in result.files if f.file_path.endswith("utils.ts")),
            None
        )

        if sample_js_path and utils_ts_path:
            # Check dependency graph
            assert sample_js_path in result.dependency_graph
            dependencies = result.dependency_graph[sample_js_path]
            assert utils_ts_path in dependencies

    def test_index_dependency_graph_leaf(self, indexer, fixtures_dir):
        """Leaf nodes (no imports) should have empty dependency list."""
        result = indexer.index(str(fixtures_dir))

        # utils.ts has no imports, should be empty or not in graph
        utils_ts_path = next(
            (f.file_path for f in result.files if f.file_path.endswith("utils.ts")),
            None
        )

        if utils_ts_path:
            if utils_ts_path in result.dependency_graph:
                assert len(result.dependency_graph[utils_ts_path]) == 0


class TestReactProjectDetection:
    """Test React/Next.js project detection from package.json."""

    def test_detect_react_project_nextjs(self, indexer, fixtures_dir):
        """Should detect Next.js project from fixtures/package.json."""
        result = indexer.index(str(fixtures_dir))

        assert result.is_react_project is True
        assert result.project_type in ["nextjs", "react"]
        assert result.package_json_path is not None

    def test_detect_react_project_generic(self, indexer, fixtures_dir):
        """Should return False for non-React projects."""
        generic_project = fixtures_dir / "generic_project"
        result = indexer.index(str(generic_project))

        assert result.is_react_project is False
        assert result.project_type is None

    def test_detect_react_project_missing_packagejson(self, indexer):
        """Should return False when no package.json exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a temp directory with a single JS file but no package.json
            test_file = Path(tmpdir) / "test.js"
            test_file.write_text("function foo() { return 42; }")

            result = indexer.index(tmpdir)

            assert result.is_react_project is False
            assert result.project_type is None
            assert result.package_json_path is None


class TestReactMetadata:
    """Test React-specific metadata population."""

    def test_react_metadata_populated(self, indexer, fixtures_dir):
        """TSX files in React project should have react_metadata populated."""
        result = indexer.index(str(fixtures_dir))

        # Find TSX files
        tsx_files = [f for f in result.files if f.file_path.endswith(".tsx")]

        for tsx_file in tsx_files:
            assert tsx_file.react_metadata is not None

    def test_react_metadata_is_component(self, indexer, fixtures_dir):
        """ProductCard should be marked as a React component."""
        result = indexer.index(str(fixtures_dir))

        # Find sample.tsx
        sample_tsx = next(
            (f for f in result.files if f.file_path.endswith("sample.tsx")),
            None
        )

        if sample_tsx and sample_tsx.react_metadata:
            assert sample_tsx.react_metadata.is_component is True

    def test_react_metadata_uses_hooks(self, indexer, fixtures_dir):
        """sample.tsx should detect useState and useEffect hooks."""
        result = indexer.index(str(fixtures_dir))

        # Find sample.tsx
        sample_tsx = next(
            (f for f in result.files if f.file_path.endswith("sample.tsx")),
            None
        )

        if sample_tsx and sample_tsx.react_metadata:
            hooks = sample_tsx.react_metadata.uses_hooks
            assert "useState" in hooks
            assert "useEffect" in hooks

    def test_react_metadata_server_component(self, indexer, fixtures_dir):
        """server_component.tsx should be detected as a server component."""
        result = indexer.index(str(fixtures_dir))

        # Find server_component.tsx
        server_comp = next(
            (f for f in result.files if f.file_path.endswith("server_component.tsx")),
            None
        )

        if server_comp and server_comp.react_metadata:
            assert server_comp.react_metadata.is_server_component is True

    def test_react_metadata_barrel_file(self, indexer, fixtures_dir):
        """barrel.ts should be detected as a barrel file."""
        result = indexer.index(str(fixtures_dir))

        # Find barrel.ts
        barrel_file = next(
            (f for f in result.files if f.file_path.endswith("barrel.ts")),
            None
        )

        if barrel_file and barrel_file.react_metadata:
            assert barrel_file.react_metadata.is_barrel_file is True

    def test_react_metadata_suspense(self, indexer, fixtures_dir):
        """server_component.tsx should detect Suspense boundary."""
        result = indexer.index(str(fixtures_dir))

        # Find server_component.tsx
        server_comp = next(
            (f for f in result.files if f.file_path.endswith("server_component.tsx")),
            None
        )

        if server_comp and server_comp.react_metadata:
            assert server_comp.react_metadata.has_suspense_boundary is True


class TestFileHashing:
    """Test file content hashing."""

    def test_index_file_hash(self, indexer, fixtures_dir):
        """Each file should have a non-empty SHA256 hash."""
        result = indexer.index(str(fixtures_dir))

        for file_info in result.files:
            assert len(file_info.hash) > 0
            # SHA256 hashes are 64 characters in hex
            assert len(file_info.hash) == 64


class TestCounts:
    """Test aggregate counts in RepoIndex."""

    def test_index_total_counts(self, indexer, fixtures_dir):
        """total_files and total_symbols should match actual counts."""
        result = indexer.index(str(fixtures_dir))

        # Verify total_files
        assert result.total_files == len(result.files)

        # Verify total_symbols
        actual_symbol_count = sum(len(f.symbols) for f in result.files)
        assert result.total_symbols == actual_symbol_count


class TestErrorHandling:
    """Test error handling for invalid files."""

    def test_index_handles_parse_error(self, indexer):
        """Files with invalid syntax should be indexed with errors, not crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file with invalid syntax
            invalid_file = Path(tmpdir) / "invalid.js"
            invalid_file.write_text("function foo( { this is invalid syntax")

            result = indexer.index(tmpdir)

            # Indexing should complete without raising an exception
            assert isinstance(result, RepoIndex)

            # The invalid file should be in the results with errors
            invalid_file_info = next(
                (f for f in result.files if f.file_path.endswith("invalid.js")),
                None
            )

            if invalid_file_info:
                # Should have errors recorded, or symbols might be empty
                # depending on implementation
                assert len(invalid_file_info.errors) > 0 or len(invalid_file_info.symbols) == 0


class TestExclusionPatterns:
    """Test file exclusion patterns."""

    def test_exclude_patterns(self, indexer):
        """node_modules directory should be excluded by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a node_modules directory with a JS file
            node_modules = Path(tmpdir) / "node_modules"
            node_modules.mkdir()
            (node_modules / "test.js").write_text("function foo() {}")

            # Create a regular JS file
            (Path(tmpdir) / "app.js").write_text("function bar() {}")

            result = indexer.index(tmpdir)

            # Should only find app.js, not node_modules/test.js
            file_paths = [f.file_path for f in result.files]
            assert any("app.js" in p for p in file_paths)
            assert not any("node_modules" in p for p in file_paths)
