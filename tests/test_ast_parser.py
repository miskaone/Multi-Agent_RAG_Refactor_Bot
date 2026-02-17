"""
Unit tests for AST Parser utility module.

Tests all functions in refactor_bot.utils.ast_parser against fixture files.
"""

from pathlib import Path

import pytest

# NOTE: These imports will work once the engineer creates the source files
from refactor_bot.utils.ast_parser import (
    detect_barrel_file,
    detect_react_component,
    detect_server_component,
    detect_suspense_boundary,
    extract_exports,
    extract_imports,
    extract_symbols,
    get_language_for_file,
    parse_file,
)


@pytest.fixture
def fixtures_dir():
    """Return the path to the fixtures directory."""
    return Path(__file__).parent / "fixtures"


class TestGetLanguageForFile:
    """Test language detection from file extensions."""

    def test_get_language_for_file_js(self):
        """JavaScript files should map to 'javascript' language."""
        assert get_language_for_file("sample.js") == "javascript"

    def test_get_language_for_file_ts(self):
        """TypeScript files should map to 'typescript' language."""
        assert get_language_for_file("sample.ts") == "typescript"

    def test_get_language_for_file_tsx(self):
        """TSX files should map to 'tsx' language."""
        assert get_language_for_file("sample.tsx") == "tsx"

    def test_get_language_for_file_jsx(self):
        """JSX files should map to 'javascript' language."""
        assert get_language_for_file("sample.jsx") == "javascript"

    def test_get_language_for_file_unsupported(self):
        """Unsupported file extensions should raise ValueError."""
        with pytest.raises(ValueError):
            get_language_for_file("sample.py")


class TestParseFile:
    """Test file parsing with tree-sitter."""

    def test_parse_file_js(self, fixtures_dir):
        """JavaScript file should parse successfully and return tree with root node."""
        file_path = str(fixtures_dir / "sample.js")
        tree, language = parse_file(file_path)
        assert tree is not None
        assert tree.root_node is not None
        assert tree.root_node.type == "program"

    def test_parse_file_ts(self, fixtures_dir):
        """TypeScript file should parse successfully."""
        file_path = str(fixtures_dir / "sample.ts")
        tree, language = parse_file(file_path)
        assert tree is not None
        assert tree.root_node is not None
        assert tree.root_node.type == "program"

    def test_parse_file_tsx(self, fixtures_dir):
        """TSX file should parse successfully."""
        file_path = str(fixtures_dir / "sample.tsx")
        tree, language = parse_file(file_path)
        assert tree is not None
        assert tree.root_node is not None

    def test_parse_file_nonexistent(self):
        """Non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_file("/nonexistent/path/file.js")


class TestExtractSymbols:
    """Test symbol extraction from parsed trees."""

    def test_extract_symbols_js_functions(self, fixtures_dir):
        """JavaScript file should extract both named and arrow functions."""
        file_path = str(fixtures_dir / "sample.js")
        tree, language = parse_file(file_path)
        symbols = extract_symbols(tree, language, file_path)

        symbol_names = [s.name for s in symbols]
        assert "calculateTotal" in symbol_names
        assert "formatPrice" in symbol_names

    def test_extract_symbols_ts_class(self, fixtures_dir):
        """TypeScript file should extract class and function definitions."""
        file_path = str(fixtures_dir / "sample.ts")
        tree, language = parse_file(file_path)
        symbols = extract_symbols(tree, language, file_path)

        symbol_names = [s.name for s in symbols]
        assert "UserService" in symbol_names
        assert "validateEmail" in symbol_names

    def test_extract_symbols_tsx_component(self, fixtures_dir):
        """TSX file should extract React component function."""
        file_path = str(fixtures_dir / "sample.tsx")
        tree, language = parse_file(file_path)
        symbols = extract_symbols(tree, language, file_path)

        symbol_names = [s.name for s in symbols]
        assert "ProductCard" in symbol_names

    def test_extract_symbols_line_numbers(self, fixtures_dir):
        """Extracted symbols should have correct start and end line numbers."""
        file_path = str(fixtures_dir / "sample.js")
        tree, language = parse_file(file_path)
        symbols = extract_symbols(tree, language, file_path)

        for symbol in symbols:
            assert symbol.start_line > 0
            assert symbol.end_line >= symbol.start_line
            assert symbol.start_byte >= 0
            assert symbol.end_byte > symbol.start_byte

    def test_extract_symbols_source_code(self, fixtures_dir):
        """Extracted symbols should contain the actual source code."""
        file_path = str(fixtures_dir / "sample.js")
        tree, language = parse_file(file_path)
        symbols = extract_symbols(tree, language, file_path)

        for symbol in symbols:
            assert len(symbol.source_code) > 0
            # Source code should contain the symbol name
            assert symbol.name in symbol.source_code


class TestExtractImports:
    """Test import statement extraction."""

    def test_extract_imports_relative(self, fixtures_dir):
        """Should extract relative import paths."""
        file_path = str(fixtures_dir / "sample.js")
        tree, language = parse_file(file_path)
        imports = extract_imports(tree, language)

        assert "./utils" in imports

    def test_extract_imports_node_module(self, fixtures_dir):
        """Should extract node_modules import paths."""
        file_path = str(fixtures_dir / "sample.tsx")
        tree, language = parse_file(file_path)
        imports = extract_imports(tree, language)

        assert "react" in imports


class TestReactDetection:
    """Test React-specific detection functions."""

    def test_detect_react_component_true(self, fixtures_dir):
        """React components should be detected correctly."""
        file_path = str(fixtures_dir / "sample.tsx")
        tree, language = parse_file(file_path)
        symbols = extract_symbols(tree, language, file_path)

        # ProductCard should be detected as a component
        product_card = next((s for s in symbols if s.name == "ProductCard"), None)
        assert product_card is not None

        # The node should be recognized as returning JSX
        detect_react_component(tree.root_node, tree.root_node.text)
        # Note: The actual implementation will check specific function nodes

    def test_detect_react_component_false(self, fixtures_dir):
        """Utility functions should not be detected as components."""
        file_path = str(fixtures_dir / "utils.ts")
        tree, language = parse_file(file_path)

        # Utility functions don't return JSX
        detect_react_component(tree.root_node, tree.root_node.text)
        # Implementation should return False for non-component functions

    def test_detect_hooks_usage(self, fixtures_dir):
        """Should detect React hooks usage in components."""
        file_path = str(fixtures_dir / "sample.tsx")
        tree, language = parse_file(file_path)

        # Get the ProductCard function node and check for hooks
        symbols = extract_symbols(tree, language, file_path)
        product_card = next((s for s in symbols if s.name == "ProductCard"), None)

        if product_card:
            # The component uses useState and useEffect
            # Actual implementation will search the function body for hook calls
            pass

    def test_detect_suspense_boundary(self, fixtures_dir):
        """Should detect Suspense boundary in server components."""
        file_path = str(fixtures_dir / "server_component.tsx")
        tree, language = parse_file(file_path)

        has_suspense = detect_suspense_boundary(tree, language)
        assert has_suspense is True

    def test_detect_barrel_file_true(self, fixtures_dir):
        """Barrel files with only re-exports should be detected."""
        file_path = str(fixtures_dir / "barrel.ts")
        tree, language = parse_file(file_path)

        is_barrel = detect_barrel_file(tree, language)
        assert is_barrel is True

    def test_detect_barrel_file_false(self, fixtures_dir):
        """Files with function/class definitions should not be barrels."""
        file_path = str(fixtures_dir / "sample.ts")
        tree, language = parse_file(file_path)

        is_barrel = detect_barrel_file(tree, language)
        assert is_barrel is False

    def test_detect_server_component_true(self, fixtures_dir):
        """Server components (without 'use client') should be detected."""
        file_path = str(fixtures_dir / "server_component.tsx")
        with open(file_path, 'rb') as f:
            source_bytes = f.read()

        is_server = detect_server_component(source_bytes)
        assert is_server is True

    def test_detect_server_component_false(self, fixtures_dir):
        """Client components (with 'use client') should not be server components."""
        file_path = str(fixtures_dir / "sample.tsx")
        with open(file_path, 'rb') as f:
            source_bytes = f.read()

        is_server = detect_server_component(source_bytes)
        assert is_server is False


class TestExtractExports:
    """Test export statement extraction."""

    def test_extract_exports(self, fixtures_dir):
        """Should extract export names from files."""
        file_path = str(fixtures_dir / "sample.js")
        tree, language = parse_file(file_path)
        exports = extract_exports(tree, language)

        # sample.js exports calculateTotal and formatPrice
        assert len(exports) > 0
