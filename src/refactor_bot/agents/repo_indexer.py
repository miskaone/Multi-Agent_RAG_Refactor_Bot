"""Repository indexer agent for JavaScript/TypeScript codebases."""

import hashlib
import json
from pathlib import Path
from typing import Optional

from refactor_bot.models.schemas import FileInfo, ReactMetadata, RepoIndex
from refactor_bot.utils.ast_parser import (
    detect_barrel_file,
    detect_server_component,
    detect_suspense_boundary,
    extract_exports,
    extract_imports,
    extract_symbols,
    parse_file,
)


class RepoIndexer:
    """Repository indexer for JavaScript/TypeScript codebases."""

    def __init__(self, exclude_patterns: list[str] | None = None):
        """Initialize the repo indexer.

        Args:
            exclude_patterns: List of directory/file patterns to exclude
        """
        self.exclude_patterns = exclude_patterns or [
            "node_modules",
            "dist",
            ".git",
            "__pycache__",
        ]

    def index(self, repo_path: str) -> RepoIndex:
        """Index a repository and extract all symbols and dependencies.

        Args:
            repo_path: Path to the repository root

        Returns:
            RepoIndex with all extracted information
        """
        repo_path_obj = Path(repo_path)
        if not repo_path_obj.exists():
            raise FileNotFoundError(f"Repository path not found: {repo_path}")

        # Detect React project
        is_react, project_type, package_json_path = self._detect_react_project(repo_path)

        # Discover all supported files
        file_paths = self._discover_files(repo_path)

        # Index each file
        files: list[FileInfo] = []
        for file_path in file_paths:
            try:
                file_info = self._index_file(file_path, repo_path, is_react)
                files.append(file_info)
            except Exception as e:
                # If parsing fails, create FileInfo with error
                resolved_file = Path(file_path).resolve()
                resolved_repo = Path(repo_path).resolve()
                relative_path = str(resolved_file.relative_to(resolved_repo))
                files.append(FileInfo(
                    file_path=file_path,
                    relative_path=relative_path,
                    language="unknown",
                    hash="",
                    errors=[f"Failed to parse: {str(e)}"],
                ))

        # Build dependency graph
        dependency_graph = self._build_dependency_graph(files, repo_path)

        # Calculate totals
        total_files = len(files)
        total_symbols = sum(len(f.symbols) for f in files)

        return RepoIndex(
            repo_path=repo_path,
            files=files,
            dependency_graph=dependency_graph,
            is_react_project=is_react,
            project_type=project_type,
            package_json_path=package_json_path,
            total_files=total_files,
            total_symbols=total_symbols,
        )

    def _discover_files(self, repo_path: str) -> list[str]:
        """Walk directory and find all supported files.

        Args:
            repo_path: Path to the repository root

        Returns:
            List of absolute file paths
        """
        supported_extensions = {".js", ".ts", ".tsx", ".jsx"}
        file_paths = []

        repo_path_obj = Path(repo_path).resolve()

        for path in repo_path_obj.rglob("*"):
            # Skip symlinks to prevent path traversal attacks
            if path.is_symlink():
                continue

            # Skip excluded patterns (match on path components, not substrings)
            if any(pattern in path.parts for pattern in self.exclude_patterns):
                continue

            # Check if it's a supported file
            if path.is_file() and path.suffix in supported_extensions:
                resolved = path.resolve()
                # Verify resolved path stays within repo boundary
                if not str(resolved).startswith(str(repo_path_obj)):
                    continue
                file_paths.append(str(resolved))

        return file_paths

    def _detect_react_project(
        self, repo_path: str
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """Detect if this is a React/Next.js project by checking package.json.

        Args:
            repo_path: Path to the repository root

        Returns:
            Tuple of (is_react, project_type, package_json_path)
        """
        package_json_path = Path(repo_path) / "package.json"

        if not package_json_path.exists():
            return False, None, None

        try:
            with open(package_json_path) as f:
                package_data = json.load(f)

            dependencies = package_data.get("dependencies", {})
            dev_dependencies = package_data.get("devDependencies", {})
            all_deps = {**dependencies, **dev_dependencies}

            # Check for Next.js
            if "next" in all_deps:
                return True, "nextjs", str(package_json_path)

            # Check for React
            if "react" in all_deps:
                return True, "react", str(package_json_path)

            return False, None, str(package_json_path)

        except (json.JSONDecodeError, Exception):
            # If package.json is invalid, treat as non-React
            return False, None, None

    def _index_file(
        self, file_path: str, repo_path: str, is_react: bool
    ) -> FileInfo:
        """Parse a single file and extract symbols, imports, exports.

        Args:
            file_path: Absolute path to the file
            repo_path: Repository root path
            is_react: Whether this is a React project

        Returns:
            FileInfo with all extracted data
        """
        # Parse the file
        tree, language = parse_file(file_path)

        # Read source bytes for hash and other operations
        with open(file_path, "rb") as f:
            source_bytes = f.read()

        # Compute hash
        file_hash = hashlib.sha256(source_bytes).hexdigest()

        # Get relative path (resolve both paths to handle symlinks)
        relative_path = str(Path(file_path).resolve().relative_to(Path(repo_path).resolve()))

        # Determine language
        from refactor_bot.utils.ast_parser import get_language_for_file
        language_name = get_language_for_file(file_path)

        # Extract symbols
        symbols = extract_symbols(tree, language, file_path)

        # Extract imports and exports
        imports = extract_imports(tree, language)
        exports = extract_exports(tree, language)

        # Initialize FileInfo
        file_info = FileInfo(
            file_path=file_path,
            relative_path=relative_path,
            language=language_name,
            symbols=symbols,
            imports=imports,
            exports=exports,
            hash=file_hash,
        )

        # If React project and TSX/JSX file, populate react_metadata
        if is_react and language_name in ("tsx", "jsx"):
            react_metadata = ReactMetadata()

            # Check if barrel file
            react_metadata.is_barrel_file = detect_barrel_file(tree, language)

            # Check for Suspense
            react_metadata.has_suspense_boundary = detect_suspense_boundary(tree, language)

            # Detect server component (only for TSX)
            if language_name == "tsx":
                react_metadata.is_server_component = detect_server_component(source_bytes)

            # For each symbol, check if it's a React component and detect hooks
            from refactor_bot.utils.ast_parser import detect_hooks_usage, detect_react_component

            has_any_component = False
            all_hooks = set()  # Track all unique hooks used in the file
            for symbol in file_info.symbols:
                if symbol.type in ("function", "arrow_function"):
                    # Find the function node in the tree by byte position
                    def find_node_at_position(node, start_byte):  # type: ignore
                        if node.start_byte == start_byte:
                            return node
                        for child in node.children:
                            result = find_node_at_position(child, start_byte)
                            if result:
                                return result
                        return None

                    func_node = find_node_at_position(tree.root_node, symbol.start_byte)
                    if func_node:
                        # Check if it returns JSX (is a component)
                        symbol.is_component = detect_react_component(func_node, source_bytes)
                        if symbol.is_component:
                            has_any_component = True

                        # Detect hook usage
                        symbol.uses_hooks = detect_hooks_usage(func_node, source_bytes)
                        all_hooks.update(symbol.uses_hooks)

            # Set file-level flags
            react_metadata.is_component = has_any_component
            react_metadata.uses_hooks = sorted(list(all_hooks))

            file_info.react_metadata = react_metadata

        return file_info

    def _build_dependency_graph(
        self, files: list[FileInfo], repo_path: str
    ) -> dict[str, list[str]]:
        """Build adjacency list of file dependencies.

        Args:
            files: List of indexed files
            repo_path: Repository root path

        Returns:
            Dictionary mapping file_path -> list of dependency file paths
        """
        # Create index of files by path for quick lookup
        file_index = {f.file_path: f for f in files}

        dependency_graph: dict[str, list[str]] = {}

        for file_info in files:
            dependencies = []

            for import_path in file_info.imports:
                # Resolve the import path
                resolved = self._resolve_import_path(
                    file_info.file_path, import_path, repo_path, file_index
                )

                if resolved:
                    dependencies.append(resolved)

            dependency_graph[file_info.file_path] = dependencies
            file_info.dependencies = dependencies

        return dependency_graph

    def _resolve_import_path(
        self,
        from_file: str,
        import_path: str,
        repo_path: str,
        file_index: dict[str, FileInfo],
    ) -> Optional[str]:
        """Resolve a relative import path to an actual file path.

        Args:
            from_file: Source file making the import
            import_path: Import path string (e.g., "./utils", "../lib/helper")
            repo_path: Repository root path
            file_index: Dictionary of file_path -> FileInfo

        Returns:
            Resolved absolute file path, or None if not found
        """
        # Skip non-relative imports (node_modules)
        if not import_path.startswith("."):
            return None

        from_path = Path(from_file).parent
        import_path_obj = from_path / import_path

        # Try different extensions
        extensions = [".js", ".ts", ".jsx", ".tsx"]

        for ext in extensions:
            # Try direct path with extension
            candidate = str(import_path_obj.with_suffix(ext).resolve())
            if candidate in file_index:
                return candidate

            # Try path + ext if import already has extension
            if import_path_obj.suffix:
                continue

            # Try as-is
            candidate_as_is = str((from_path / f"{import_path}{ext}").resolve())
            if candidate_as_is in file_index:
                return candidate_as_is

        # Try index files
        for ext in extensions:
            index_path = str((import_path_obj / f"index{ext}").resolve())
            if index_path in file_index:
                return index_path

        return None
