# Contributing

We welcome contributions! This guide covers how to set up your development environment and submit changes.

## Development Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended)

### Setup

```bash
# Clone the repository
git clone https://github.com/miskaone/Multi-Agent_RAG_Refactor_Bot.git
cd Multi-Agent_RAG_Refactor_Bot

# Install with dev dependencies
uv sync

# Or with pip
pip install -e ".[dev]"
```

### Verify Setup

```bash
uv run pytest --tb=short -q
```

You should see `262 passed` with 91% coverage.

## Making Changes

### Workflow

1. Create a branch: `git checkout -b feature/your-feature`
2. Make your changes
3. Run tests: `uv run pytest`
4. Run linting: `uv run ruff check src/ tests/`
5. Commit with a clear message
6. Open a Pull Request

### Code Style

- **Line length**: 100 characters (configured in `pyproject.toml`)
- **Linter**: Ruff with `E`, `F`, `I` rules
- **Type checker**: mypy (optional, not strict)
- **Docstrings**: Google style
- **Imports**: Sorted by ruff (isort-compatible)

### Testing Guidelines

- All new code must have tests
- Mock external dependencies (API calls, filesystem, subprocesses)
- Use `tmp_path` fixture for filesystem tests
- Use `MagicMock()` for agent dependencies — the closure factory pattern makes this trivial
- Target: maintain 90%+ coverage

### Project Conventions

- **Pydantic v2**: Use `model_config = ConfigDict(...)` and `model_copy(update=...)`
- **Exception naming**: Avoid collisions with stdlib (e.g., `TestValidationError` not `ValidationError`)
- **Path validation**: Use `Path.resolve().is_relative_to()` for containment checks
- **Constants**: Extract magic numbers to named module-level constants
- **API keys**: Environment variables only, never CLI arguments

## Architecture Notes

- **Closure factory pattern**: Graph nodes are created by factory functions that capture agent instances. This is the core testability pattern — don't break it.
- **Annotated reducers**: `diffs` and `errors` fields in `RefactorState` use `operator.add` to accumulate across nodes. Always return lists, never `None`.
- **Lazy imports**: The CLI module defers heavy imports (anthropic, chromadb, tree-sitter) to keep `--help` and `--dry-run` fast.

## Reporting Issues

Please include:
- Python version (`python --version`)
- Package versions (`uv pip list` or `pip list`)
- Steps to reproduce
- Expected vs actual behavior
- Error messages or tracebacks
