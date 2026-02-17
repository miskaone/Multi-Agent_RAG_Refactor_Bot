# General Patterns

Universal conventions and principles for this project. Always loaded by the research-scout.

## Project Conventions

- **Language**: Python 3.12+
- **Package Manager**: uv
- **Data Validation**: Pydantic v2
- **Orchestration**: LangGraph
- **Testing**: pytest
- **Code Style**: Follow existing conventions; no unnecessary abstractions

## Naming Conventions

- Snake case for all Python identifiers
- Pydantic models use PascalCase class names
- Test files: `test_{module_name}.py`
- Test functions: `test_{behavior_description}`

## Error Handling

- Use structured error types (Pydantic models) for agent errors
- Never swallow exceptions silently
- Log errors to the state's error list for recovery decisions
- **Define exception hierarchy from day one**: Create a base exception class for each major module (e.g., `RAGError`, `ParsingError`) before implementation. Retrofitting consistent error handling is more expensive than designing it upfront. (L008, Cycle 2)

## Module Boundaries

- `src/models/` — Pydantic schemas only, no business logic
- `src/agents/` — Agent implementations, one file per agent
- `src/rag/` — Embedding and retrieval logic
- `src/orchestrator/` — LangGraph graph and state management
- `src/cli/` — CLI entry points
- `src/utils/` — Shared utilities (AST parsing, diff generation)
- `src/rules/` — React best practices rule engine
