# AST Parsing

Learnings related to tree-sitter, symbol extraction, and dependency graph construction.

---

## L001: tree-sitter-languages Package Incompatibility

**Date**: 2026-02-16 (Cycle 1)

**Problem**: The `tree-sitter-languages` package is incompatible with tree-sitter 0.22+. Using `language.query()` API fails at runtime.

**Solution**: Use individual language packages (`tree-sitter-javascript`, `tree-sitter-typescript`) and the `Query(language, query_string)` + `QueryCursor` API instead.

**Code Pattern**:
```python
from tree_sitter import Language, Parser, Query
from tree_sitter_javascript import language as js_lang
from tree_sitter_typescript import language_typescript as ts_lang

# Initialize parser
parser = Parser(Language(js_lang()))

# Query pattern
query = Query(Language(js_lang()), """
  (function_declaration
    name: (identifier) @func.name)
""")
cursor = query_cursor()
matches = cursor.matches(tree.root_node, tree.text)
```

**Rationale**: tree-sitter ecosystem has fragmented package support. Always check package compatibility with latest tree-sitter version.

---

## L002: TypeScript vs JavaScript AST Node Differences

**Date**: 2026-02-16 (Cycle 1)

**Problem**: Class name extraction queries fail for TypeScript files because TS uses `type_identifier` while JS uses `identifier`.

**Solution**: Use separate queries for TS/TSX and JS/JSX, or handle both node types in extraction logic.

**Code Pattern**:
```python
# TypeScript/TSX
(class_declaration name: (type_identifier) @class.name)

# JavaScript/JSX
(class_declaration name: (identifier) @class.name)
```

**Rationale**: Tree-sitter maintains separate grammars for TypeScript and JavaScript. Even structurally similar nodes may use different node types.

**Related**: React component extraction also requires language-specific queries due to JSX vs TSX differences.

---

## L020: TypeScript type_identifier Required for Import Orphan Detection

**Date**: 2026-02-17 (Cycle 5)

**Problem**: The `ConsistencyAuditor._check_orphaned_imports()` initially only searched for `identifier` nodes when counting usages of imported names. TypeScript type-only imports (e.g., `import type { Foo } from './types'` or `import { type Foo } from './types'`) use `type_identifier` nodes, not `identifier` nodes. Without including `type_identifier`, type imports were always reported as orphaned even when used in type annotations.

**Solution**: Extend AST node collection to include both `identifier` and `type_identifier` when counting usages of an imported name:

```python
# Collect all identifier-like nodes in the tree
ALL_IDENTIFIER_TYPES = {"identifier", "type_identifier", "shorthand_property_identifier"}

def _count_usages(node, name: str, skip_node=None) -> int:
    if node is skip_node:
        return 0
    count = 0
    if node.type in ALL_IDENTIFIER_TYPES:
        if node.text and node.text.decode("utf-8") == name:
            count += 1
    for child in node.children:
        count += _count_usages(child, name, skip_node)
    return count
```

**Rationale**: TypeScript extends the JS grammar with type-level constructs. Type annotations, interface references, and generic type parameters use `type_identifier` in the tree-sitter TypeScript grammar. An orphan-import check that only queries `identifier` will produce false positives for any type-only import usage.

**Related**: L002 (TS vs JS AST node differences for class names), L015 (false positive rate on import analysis).

---
