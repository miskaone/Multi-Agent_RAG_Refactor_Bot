"""AST parser utility for JavaScript/TypeScript using tree-sitter."""

import re
from pathlib import Path

import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser, Query, QueryCursor, Tree

from refactor_bot.models.schemas import SymbolInfo

# Initialize language objects
JS_LANGUAGE = Language(tsjs.language())
TS_LANGUAGE = Language(tsts.language_typescript())
TSX_LANGUAGE = Language(tsts.language_tsx())


def get_language_for_file(file_path: str) -> str:
    """Map file extension to tree-sitter language name.

    Args:
        file_path: Path to the file

    Returns:
        Language name ("javascript", "typescript", "tsx")

    Raises:
        ValueError: If file extension is not supported
    """
    ext = Path(file_path).suffix
    mapping = {
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".jsx": "javascript",
    }
    if ext not in mapping:
        raise ValueError(f"Unsupported file extension: {ext}")
    return mapping[ext]


def get_parser(language: str) -> Parser:
    """Return a tree-sitter Parser for the given language name.

    Args:
        language: Language name ("javascript", "typescript", "tsx")

    Returns:
        Configured Parser instance
    """
    parser = Parser()
    if language == "javascript":
        parser.language = JS_LANGUAGE
    elif language == "typescript":
        parser.language = TS_LANGUAGE
    elif language == "tsx":
        parser.language = TSX_LANGUAGE
    else:
        raise ValueError(f"Unsupported language: {language}")
    return parser


def parse_file(file_path: str) -> tuple[Tree, Language]:
    """Read file as bytes, determine language, parse with tree-sitter.

    Args:
        file_path: Path to the file to parse

    Returns:
        Tuple of (tree, language)

    Raises:
        FileNotFoundError: If file does not exist
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    language_name = get_language_for_file(file_path)
    parser = get_parser(language_name)

    # Get the appropriate Language object
    if language_name == "javascript":
        language = JS_LANGUAGE
    elif language_name == "typescript":
        language = TS_LANGUAGE
    elif language_name == "tsx":
        language = TSX_LANGUAGE
    else:
        raise ValueError(f"Unsupported language: {language_name}")

    with open(file_path, "rb") as f:
        source_bytes = f.read()

    tree = parser.parse(source_bytes)
    return tree, language


def extract_symbols(tree: Tree, language: Language, file_path: str) -> list[SymbolInfo]:
    """Extract symbols (functions, classes, methods, arrow functions) from the AST.

    Args:
        tree: Parsed tree-sitter Tree
        language: Language object
        file_path: Path to the source file

    Returns:
        List of SymbolInfo objects
    """
    symbols: list[SymbolInfo] = []
    source_bytes = tree.root_node.text
    if not source_bytes:
        return symbols  # Empty file or parsing error

    # Query for function declarations
    func_query = Query(language, """
        (function_declaration
            name: (identifier) @name) @func
    """)
    func_cursor = QueryCursor(func_query)

    for match in func_cursor.matches(tree.root_node):
        # match is a tuple: (pattern_index, captures_dict)
        # captures_dict maps capture names to lists of nodes
        _, captures = match
        if "name" in captures and "func" in captures:
            func_node = captures["func"][0]  # Get first node from list
            name_node = captures["name"][0]  # Get first node from list

            name_text = name_node.text
            func_text = func_node.text
            if name_text and func_text:
                symbols.append(SymbolInfo(
                    name=name_text.decode("utf-8"),
                    type="function",
                    file_path=file_path,
                    start_line=func_node.start_point[0] + 1,
                    end_line=func_node.end_point[0] + 1,
                    start_byte=func_node.start_byte,
                    end_byte=func_node.end_byte,
                    source_code=source_bytes[func_node.start_byte:func_node.end_byte].decode("utf-8"),
                ))

    # Query for arrow functions assigned to variables
    arrow_query = Query(language, """
        (variable_declarator
            name: (identifier) @name
            value: (arrow_function) @arrow) @decl
    """)
    arrow_cursor = QueryCursor(arrow_query)

    for match in arrow_cursor.matches(tree.root_node):
        _, captures = match
        if "name" in captures and "decl" in captures:
            decl_node = captures["decl"][0]  # Use the entire declarator
            name_node = captures["name"][0]

            name_text = name_node.text
            decl_text = decl_node.text
            if name_text and decl_text:
                symbols.append(SymbolInfo(
                    name=name_text.decode("utf-8"),
                    type="arrow_function",
                    file_path=file_path,
                    start_line=decl_node.start_point[0] + 1,
                    end_line=decl_node.end_point[0] + 1,
                    start_byte=decl_node.start_byte,
                    end_byte=decl_node.end_byte,
                    source_code=source_bytes[decl_node.start_byte:decl_node.end_byte].decode("utf-8"),
                ))

    # Query for class declarations
    # Note: JavaScript uses 'identifier' while TypeScript/TSX uses 'type_identifier'
    # Determine which to use based on the language
    if language == TS_LANGUAGE or language == TSX_LANGUAGE:
        class_query_str = """
            (class_declaration
                name: (type_identifier) @name) @class
        """
    else:
        class_query_str = """
            (class_declaration
                name: (identifier) @name) @class
        """
    class_query = Query(language, class_query_str)
    class_cursor = QueryCursor(class_query)

    for match in class_cursor.matches(tree.root_node):
        _, captures = match
        if "name" in captures and "class" in captures:
            class_node = captures["class"][0]
            name_node = captures["name"][0]

            name_text = name_node.text
            class_text = class_node.text
            if name_text and class_text:
                symbols.append(SymbolInfo(
                    name=name_text.decode("utf-8"),
                    type="class",
                    file_path=file_path,
                    start_line=class_node.start_point[0] + 1,
                    end_line=class_node.end_point[0] + 1,
                    start_byte=class_node.start_byte,
                    end_byte=class_node.end_byte,
                    source_code=source_bytes[class_node.start_byte:class_node.end_byte].decode("utf-8"),
                ))

    # Query for method definitions
    method_query = Query(language, """
        (method_definition
            name: (property_identifier) @name) @method
    """)
    method_cursor = QueryCursor(method_query)

    for match in method_cursor.matches(tree.root_node):
        _, captures = match
        if "name" in captures and "method" in captures:
            method_node = captures["method"][0]
            name_node = captures["name"][0]

            name_text = name_node.text
            method_text = method_node.text
            if name_text and method_text:
                symbols.append(SymbolInfo(
                    name=name_text.decode("utf-8"),
                    type="method",
                    file_path=file_path,
                    start_line=method_node.start_point[0] + 1,
                    end_line=method_node.end_point[0] + 1,
                    start_byte=method_node.start_byte,
                    end_byte=method_node.end_byte,
                    source_code=source_bytes[method_node.start_byte:method_node.end_byte].decode("utf-8"),
                ))

    return symbols


def extract_imports(tree: Tree, language: Language) -> list[str]:
    """Extract import paths from import statements.

    Args:
        tree: Parsed tree-sitter Tree
        language: Language object

    Returns:
        List of import path strings
    """
    imports = []

    # Query for import statements
    import_query = Query(language, """
        (import_statement
            source: (string) @source)
    """)
    import_cursor = QueryCursor(import_query)

    for match in import_cursor.matches(tree.root_node):
        _, captures = match
        if "source" in captures:
            source_node = captures["source"][0]
            source_text = source_node.text
            if source_text:
                # Remove quotes from string literal
                import_path = source_text.decode("utf-8").strip("'\"")
                imports.append(import_path)

    return imports


def extract_exports(tree: Tree, language: Language) -> list[str]:
    """Extract export names from export statements.

    Args:
        tree: Parsed tree-sitter Tree
        language: Language object

    Returns:
        List of exported symbol names
    """
    exports = []

    # Query for named exports
    export_query = Query(language, """
        (export_statement) @export
    """)
    export_cursor = QueryCursor(export_query)

    for match in export_cursor.matches(tree.root_node):
        _, captures = match
        if "export" in captures:
            export_node = captures["export"][0]
            # Extract identifiers from the export statement
            # Look for export_specifier nodes which contain identifiers
            def extract_identifiers(node):  # type: ignore
                if node.type == "export_specifier":
                    # Get the identifier from the export_specifier
                    for child in node.children:
                        if child.type == "identifier":
                            exports.append(child.text.decode("utf-8"))
                            break  # Take first identifier (the exported name)
                elif node.type == "identifier":
                    # Direct identifier export
                    exports.append(node.text.decode("utf-8"))
                else:
                    # Recurse into children
                    for child in node.children:
                        extract_identifiers(child)

            extract_identifiers(export_node)

    return exports


def detect_react_component(node, source_bytes: bytes) -> bool:  # type: ignore
    """Return True if a function/arrow function returns JSX.

    Args:
        node: Tree-sitter node to check
        source_bytes: Source code as bytes

    Returns:
        True if the node returns JSX elements
    """
    # Check for jsx_element or jsx_self_closing_element in the node
    def has_jsx(n) -> bool:  # type: ignore
        if n.type in ("jsx_element", "jsx_self_closing_element"):
            return True
        for child in n.children:
            if has_jsx(child):
                return True
        return False

    return bool(has_jsx(node))


def detect_hooks_usage(node, source_bytes: bytes) -> list[str]:  # type: ignore
    """Find hook calls matching use[A-Z]* pattern within a function body.

    Args:
        node: Tree-sitter node to check
        source_bytes: Source code as bytes

    Returns:
        List of hook names found
    """
    hooks = []

    def find_hooks(n):
        # Look for call_expression with identifier matching use[A-Z]*
        if n.type == "call_expression":
            for child in n.children:
                if child.type == "identifier":
                    name = child.text.decode("utf-8")
                    if re.match(r"use[A-Z]", name):
                        hooks.append(name)

        for child in n.children:
            find_hooks(child)

    find_hooks(node)
    return hooks


def detect_suspense_boundary(tree: Tree, language: Language) -> bool:
    """Check if file contains <Suspense JSX usage.

    Args:
        tree: Parsed tree-sitter Tree
        language: Language object

    Returns:
        True if Suspense boundary is found
    """
    # Look for jsx elements with Suspense identifier
    def has_suspense(node) -> bool:  # type: ignore
        if node.type in ("jsx_opening_element", "jsx_self_closing_element"):
            for child in node.children:
                if child.type == "identifier" and child.text.decode("utf-8") == "Suspense":
                    return True

        for child in node.children:
            if has_suspense(child):
                return True

        return False

    return bool(has_suspense(tree.root_node))


def detect_barrel_file(tree: Tree, language: Language) -> bool:
    """Return True if file consists only of export/re-export statements.

    Args:
        tree: Parsed tree-sitter Tree
        language: Language object

    Returns:
        True if the file is a barrel file
    """
    # Count function/class declarations and export statements
    has_definitions = False
    has_exports = False

    for child in tree.root_node.children:
        if child.type in (
            "function_declaration",
            "class_declaration",
            "lexical_declaration",
            "variable_declaration",
        ):
            # Check if it's not just an export
            if child.type in ("lexical_declaration", "variable_declaration"):
                # These might be part of exports, check context
                pass
            else:
                has_definitions = True

        if child.type in ("export_statement",):
            has_exports = True

    # Barrel file has exports but no definitions
    return has_exports and not has_definitions


def detect_server_component(source_bytes: bytes) -> bool:
    """Return True if file does NOT contain "use client" directive.

    In Next.js 13+, files without "use client" are server components.

    Args:
        source_bytes: Source code as bytes

    Returns:
        True if this is a server component (no "use client")
    """
    # Check first few lines for "use client" directive
    source_str = source_bytes.decode("utf-8")
    lines = source_str.split("\n")[:10]  # Check first 10 lines

    for line in lines:
        if '"use client"' in line or "'use client'" in line:
            return False

    return True
