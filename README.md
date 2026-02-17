# Multi-Agent RAG Refactor Bot

![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)
![Tests](https://img.shields.io/badge/tests-262%20passing-brightgreen.svg)
![Coverage](https://img.shields.io/badge/coverage-91%25-brightgreen.svg)

Legacy JS/TS codebases are hard to refactor safely at scale. This bot uses a multi-agent pipeline to analyze, plan, execute, and validate refactoring tasks with RAG-grounded context.

An AI-powered refactoring pipeline for JavaScript and TypeScript codebases. Uses multiple specialized agents orchestrated via LangGraph to analyze, plan, execute, audit, and validate code refactoring tasks with retrieval-augmented generation (RAG) for context-aware transformations.

## How It Works

```
                    ┌─────────┐
                    │  START   │
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │  Index   │  RepoIndexer + Retriever
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │   Plan   │  Planner (Claude) + RAG context
                    └────┬─────┘
                         │
                 ┌───────▼────────┐
            ┌───►│    Execute     │  RefactorExecutor (Claude)
            │    └───────┬────────┘
            │            │
            │    ┌───────▼────────┐
            │    │     Audit      │  ConsistencyAuditor (AST)
            │    └───────┬────────┘
            │            │
            │    ┌───────▼────────┐
            │    │   Validate     │  TestValidator (test runner)
            │    └───────┬────────┘
            │            │
            │    ┌───────▼────────┐
            │    │    Decide      │  Route: apply / retry / abort
            │    └──┬────┬────┬───┘
            │       │    │    │
            │  ┌────▼┐ ┌▼──┐ ┌▼────┐
            │  │Apply│ │Re-│ │Abort│
            │  │     │ │try│ │     │
            │  └──┬──┘ └─┬─┘ └──┬──┘
            │     │      │      │
            │     ▼      │      ▼
            │  next task─┘     END
            └─────┘
```

## Features

- **RAG-powered context**: Embeds and retrieves relevant code symbols via ChromaDB for context-aware refactoring
- **Tree-sitter AST analysis**: Parses JS/TS/TSX for import/export validation, anti-pattern detection, and structural auditing
- **Multi-agent pipeline**: Six specialized agents with dependency injection and closure-based factory pattern
- **LangGraph orchestration**: State machine with conditional routing, retry logic, and abort safety nets
- **DAG-aware task scheduling**: Respects task dependencies for correct execution order
- **React-specific rules**: Detects anti-patterns like direct DOM manipulation, class components, and missing key props
- **Dry-run mode**: Validate configuration without invoking agents or APIs

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- API keys:
  - `ANTHROPIC_API_KEY` for Claude (planner, executor, validator)
  - `OPENAI_API_KEY` for embeddings (retriever)

### Installation

```bash
git clone https://github.com/miskaone/Multi-Agent_RAG_Refactor_Bot.git
cd Multi-Agent_RAG_Refactor_Bot

# Install with uv
uv sync

# Or with pip
pip install -e ".[dev]"
```

### Configuration

Set your API keys as environment variables:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

### Usage

```bash
# Dry run — validate inputs and print config
python -m refactor_bot.cli "Convert class components to hooks" ./my-react-app --dry-run

# Full run
python -m refactor_bot.cli "Convert class components to hooks" ./my-react-app

# With options
python -m refactor_bot.cli "Migrate to TypeScript" ./my-project \
  --max-retries 5 \
  --timeout 300 \
  --model claude-sonnet-4-5-20250929 \
  --output-json \
  --verbose
```

### CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `directive` | (required) | Refactoring directive to execute |
| `repo_path` | (required) | Path to the repository root |
| `--max-retries` | 3 | Max retry attempts per task (clamped 1-10) |
| `--timeout` | 120 | Test runner timeout in seconds |
| `--model` | `claude-sonnet-4-5-20250929` | Anthropic model ID |
| `--vector-store-dir` | `./data/embeddings` | ChromaDB persistence directory |
| `--dry-run` | false | Print config and exit |
| `--output-json` | false | Output results as JSON |
| `--verbose` | false | Show stack traces on error |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Invalid input (bad path, bad arguments) |
| 2 | Agent error (construction or runtime failure) |
| 3 | Orchestrator error (graph build or pipeline failure) |
| 4 | Pipeline aborted (low test pass rate, retries exhausted) |
| 5 | Unexpected error |
| 130 | Interrupted (Ctrl+C) |

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system design.

### Package Structure

```
src/refactor_bot/
├── agents/              # 6 agent implementations
│   ├── planner.py           # Task decomposition via Claude
│   ├── refactor_executor.py # Code generation via Claude
│   ├── consistency_auditor.py # AST-based structural validation
│   ├── test_validator.py    # Subprocess test runner
│   ├── repo_indexer.py      # File system indexer
│   └── exceptions.py       # Agent exception hierarchy
├── cli/                 # CLI entry point (argparse)
│   ├── main.py              # Parser, agent factory, main()
│   └── __main__.py          # python -m support
├── models/              # Pydantic v2 domain models
│   ├── schemas.py           # RepoIndex, RetrievalResult, RefactorRule
│   ├── diff_models.py       # FileDiff
│   ├── task_models.py       # TaskNode, TaskStatus
│   └── report_models.py     # AuditReport, TestReport
├── orchestrator/        # LangGraph state machine
│   ├── graph.py             # build_graph() + node factories
│   ├── state.py             # RefactorState TypedDict
│   └── recovery.py          # DAG-aware task routing helpers
├── rag/                 # Retrieval-augmented generation
│   ├── embeddings.py        # OpenAI embedding service
│   ├── vector_store.py      # ChromaDB vector store
│   └── retriever.py         # Semantic code retriever
├── rules/               # React refactoring rules
│   └── rule_engine.py       # Rule matching engine
└── utils/               # Shared utilities
    ├── ast_parser.py        # Tree-sitter JS/TS/TSX parser
    └── diff_generator.py    # Unified diff generation
```

## Development

### Running Tests

```bash
# Full suite with coverage
uv run pytest

# Specific test file
uv run pytest tests/test_cli.py -v

# With short traceback
uv run pytest --tb=short -q
```

### Linting

```bash
uv run ruff check src/ tests/
uv run mypy src/refactor_bot/
```

## Dependencies

| Package | Purpose |
|---------|---------|
| [anthropic](https://github.com/anthropics/anthropic-sdk-python) | Claude API for planning, execution, validation |
| [openai](https://github.com/openai/openai-python) | Embedding generation for RAG |
| [chromadb](https://github.com/chroma-core/chroma) | Vector store for semantic code search |
| [langgraph](https://github.com/langchain-ai/langgraph) | State machine orchestration |
| [pydantic](https://github.com/pydantic/pydantic) | Domain model validation |
| [tree-sitter](https://github.com/tree-sitter/py-tree-sitter) | AST parsing for JS/TS/TSX |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## API Reference

See [docs/API.md](docs/API.md) for the full API reference.
