# Learnings Index

Persistent knowledge captured from workflow cycles. Each entry links to a detailed learning in the appropriate category file.

## Index

<!-- Entries added by knowledge-compounder after each cycle -->
<!-- Format: | ID | Category | Summary | File | Date | Times Applied | -->

| ID | Category | Summary | File | Date | Times Applied |
|----|----------|---------|------|------|---------------|
| L001 | AST | tree-sitter-languages incompatible with tree-sitter 0.22+ | category/ast-parsing.md | 2026-02-16 | 1 |
| L002 | AST | TypeScript vs JavaScript AST node differences for class names | category/ast-parsing.md | 2026-02-16 | 1 |
| L003 | Security | Symlink attack vector in file discovery | known-pitfalls.md | 2026-02-16 | 1 |
| L004 | Testing | macOS path symlinks cause test failures | known-pitfalls.md | 2026-02-16 | 1 |
| L005 | Planning | Parallel agent work requires explicit interface contracts | known-pitfalls.md | 2026-02-16 | 1 |
| L006 | RAG | ChromaDB metadata requires JSON serialization for lists | known-pitfalls.md | 2026-02-16 | 1 |
| L007 | Testing | Barrel files have no symbols, invalidating blanket assertions | known-pitfalls.md | 2026-02-16 | 1 |
| L008 | Architecture | Exception hierarchies should be designed upfront | known-pitfalls.md | 2026-02-16 | 1 |
| L009 | Security | Prompt injection validation needs defense-in-depth | known-pitfalls.md | 2026-02-16 | 1 |
| L010 | Code Quality | Magic numbers in agent code should be module constants | known-pitfalls.md | 2026-02-16 | 1 |
| L011 | Architecture | Pydantic models work well for both data and rule definitions | known-pitfalls.md | 2026-02-16 | 1 |
| L012 | LLM Integration | Claude tool-use provides reliable structured output | known-pitfalls.md | 2026-02-16 | 1 |
| L013 | Testing | macOS Path.resolve() on temp dirs adds /private prefix — use is_relative_to() not startswith() | known-pitfalls.md | 2026-02-16 | 1 |
| L014 | Security | Prompt injection defense needs dual layer: input validation (reject patterns) + prompt instructions (tell LLM source is data) | known-pitfalls.md | 2026-02-16 | 1 |
| L015 | Process | Review false positive rate ~5% — always verify findings before fixing (CQ-C4-021 was false positive for unused import) | known-pitfalls.md | 2026-02-16 | 1 |
| L016 | Security | subprocess calls in temp dirs need path traversal validation on ALL user-provided paths before writing | known-pitfalls.md | 2026-02-16 | 1 |
| L017 | Architecture | Name custom exceptions to avoid collisions with stdlib/framework names (renamed ValidationError → TestValidationError to avoid pydantic collision) | known-pitfalls.md | 2026-02-17 | 1 |
| L018 | Security | shutil.copytree copies symlinks by default — always pass symlinks=False in temp dir operations to prevent path-traversal via symlink escape | known-pitfalls.md | 2026-02-17 | 1 |
| L019 | Code Quality | When writing fallback/error branches, verify the condition can actually be reached — unreachable branches are dead code and should be removed | known-pitfalls.md | 2026-02-17 | 1 |
| L020 | AST | TypeScript import orphan detection must query both identifier and type_identifier nodes — type-only imports use type_identifier, not identifier | category/ast-parsing.md | 2026-02-17 | 1 |
| L021 | Resource Management | Temp dir cleanup must use bare except Exception in finally block — specific exception types (e.g., ValidationError) will skip cleanup when the exception propagates past the handler | known-pitfalls.md | 2026-02-17 | 1 |
| L022 | LangGraph | Conditional edge map keys must exactly match all possible return values of the router function — missing keys create unreachable nodes with no runtime error | knowledge/category/orchestration.md | 2026-02-17 | 1 |
| L023 | LangGraph | Optional model fields accessed in node functions need None guards even when synthetic fallbacks "always" populate them — the guard also documents the contract | knowledge/category/orchestration.md | 2026-02-17 | 1 |
| L024 | Architecture | Closure-based factory pattern for LangGraph nodes enables trivial mocking in tests — pass agent instances to build_graph() rather than importing agents inside nodes | knowledge/category/orchestration.md | 2026-02-17 | 1 |
| L025 | LangGraph | Annotated[list, operator.add] state reducers require every node to return the field as a list — returning None causes a TypeError at runtime that LangGraph does not surface clearly | known-pitfalls.md | 2026-02-17 | 1 |
| L026 | CLI | Lazy imports in CLI entry points avoid loading heavy deps (anthropic, chromadb, tree-sitter) for --help/--dry-run | category/orchestration.md | 2026-02-17 | 1 |
| L027 | Security | Never accept API keys as CLI arguments — process args visible via ps aux and stored in shell history. Use env vars only. | known-pitfalls.md | 2026-02-17 | 1 |
| L028 | Testing | When patching lazy imports in tests, patch at the source module (e.g., refactor_bot.rag.embeddings.EmbeddingService), not at the importing module | known-pitfalls.md | 2026-02-17 | 1 |
