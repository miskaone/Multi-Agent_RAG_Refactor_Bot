# Architecture

## Overview

The Multi-Agent RAG Refactor Bot is a pipeline of six specialized agents orchestrated by a LangGraph state machine. Each agent handles one phase of the refactoring process, communicating through a shared `RefactorState` TypedDict.

## System Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                         CLI Layer                            │
│  main.py: argparse → validate → create_agents → build_graph │
└──────────────────────┬───────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────┐
│                    Orchestrator Layer                         │
│  graph.py: StateGraph(RefactorState)                         │
│                                                              │
│  ┌─────────┐  ┌──────┐  ┌─────────┐  ┌───────┐  ┌────────┐│
│  │  Index  ├──► Plan ├──► Execute ├──► Audit ├──►Validate││
│  └─────────┘  └──────┘  └─────────┘  └───────┘  └───┬────┘│
│                              ▲                        │      │
│                              │    ┌──────────────────▼─┐    │
│                              ├────┤    decide_fn()     │    │
│                              │    └─┬────────┬────────┬┘    │
│                         retry │  apply│        │abort  │      │
│                              │      │        │        │      │
│                              │   ┌──▼──┐  ┌──▼───┐   │      │
│                              │   │next?│  │ END  │   │      │
│                              │   └──┬──┘  └──────┘   │      │
│                              └──────┘                 │      │
└──────────────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────┐
│                      Agent Layer                             │
│                                                              │
│  ┌─────────────┐  ┌─────────────────┐  ┌──────────────────┐ │
│  │ RepoIndexer │  │     Planner     │  │ RefactorExecutor │ │
│  │ (filesystem)│  │ (Claude + RAG)  │  │  (Claude + RAG)  │ │
│  └─────────────┘  └─────────────────┘  └──────────────────┘ │
│                                                              │
│  ┌───────────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ConsistencyAuditor │  │TestValidator  │  │  Retriever   │  │
│  │ (AST + rules)     │  │ (subprocess)  │  │  (ChromaDB)  │  │
│  └───────────────────┘  └──────────────┘  └──────────────┘  │
└──────────────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────┐
│                    Foundation Layer                           │
│                                                              │
│  ┌────────────┐  ┌───────────────┐  ┌─────────────────────┐ │
│  │ AST Parser │  │ Diff Generator│  │  Pydantic Models    │ │
│  │(tree-sitter)│  │ (unified diff)│  │  (domain types)     │ │
│  └────────────┘  └───────────────┘  └─────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## Components

### CLI (`cli/`)

The outermost layer. Parses arguments, validates inputs, constructs agents via dependency injection, and invokes the graph. Uses lazy imports to keep `--help` and `--dry-run` fast.

| Module | Purpose |
|--------|---------|
| `main.py` | `build_parser()`, `create_agents()`, `main()`, output formatters |
| `__main__.py` | `python -m refactor_bot.cli` entry point |

### Orchestrator (`orchestrator/`)

LangGraph state machine that wires agents into a pipeline with conditional routing.

| Module | Purpose |
|--------|---------|
| `graph.py` | Node factory functions, `build_graph()`, `make_decide_fn()` |
| `state.py` | `RefactorState` TypedDict with `Annotated` reducers for accumulating diffs/errors |
| `recovery.py` | Pure helpers: `get_next_pending_task()`, `compute_test_pass_rate()`, `next_task_or_end()` |

**Key design decisions:**

- **Closure-based factories**: `make_plan_node(planner, retriever)` returns a closure. This enables trivial mocking in tests — pass `MagicMock()` instead of real agents.
- **Annotated reducers**: `diffs: Annotated[list[FileDiff], operator.add]` accumulates diffs across nodes without overwriting.
- **DAG-aware scheduling**: `get_next_pending_task()` checks dependency status, not positional index.

### Agents (`agents/`)

Six specialized agents, each with a single responsibility:

| Agent | Input | Output | Backend |
|-------|-------|--------|---------|
| `RepoIndexer` | repo path | `RepoIndex` (file tree, metadata) | filesystem |
| `Planner` | directive + RAG context | `list[TaskNode]` | Claude API |
| `RefactorExecutor` | task + RAG context | `list[FileDiff]` | Claude API |
| `ConsistencyAuditor` | diffs + rules | `AuditReport` | tree-sitter AST |
| `TestValidator` | diffs + repo | `TestReport` | subprocess (vitest/jest) |
| `Retriever` | query | `list[RetrievalResult]` | ChromaDB + OpenAI |

### RAG Pipeline (`rag/`)

Three-layer retrieval system:

1. **EmbeddingService** — Wraps OpenAI's embedding API with batching
2. **VectorStore** — ChromaDB with path validation and metadata serialization
3. **Retriever** — Indexes repo symbols, queries by semantic similarity

### Models (`models/`)

Pydantic v2 domain types shared across all layers:

- `FileDiff` — Original/modified content with unified diff text
- `TaskNode` — Refactoring task with dependencies and status
- `AuditReport` / `TestReport` — Validation results
- `RepoIndex` / `RetrievalResult` — RAG data structures
- `RefactorRule` — React-specific refactoring rules

### Utilities (`utils/`)

- **AST Parser** — Tree-sitter wrapper for JS/TS/TSX. Extracts imports, exports, functions, classes, and type identifiers.
- **Diff Generator** — Creates unified diffs between original and modified content.

## Data Flow

1. **CLI** parses directive + repo path, constructs agents
2. **Index node** scans the repo filesystem, embeds symbols into ChromaDB
3. **Plan node** queries RAG for relevant context, sends to Claude for task decomposition
4. **Execute node** picks the next pending task (DAG-aware), generates code diffs via Claude
5. **Audit node** parses diffs with tree-sitter, checks structural integrity and React rules
6. **Validate node** copies repo to temp dir, applies diffs, runs test suite
7. **Decide function** routes: apply (tests pass) / retry (audit fail, retries left) / abort (pass rate < 85% or retries exhausted)
8. **Apply node** marks task completed, routes to next task or END

## State Machine

The `RefactorState` TypedDict carries all data through the pipeline:

```python
class RefactorState(TypedDict):
    directive: str                                    # Input
    repo_path: str
    max_retries: int
    repo_index: RepoIndex | None                     # Indexing
    embedding_stats: dict | None
    is_react_project: bool
    task_tree: list[TaskNode]                         # Planning
    context_bundles: dict[str, list]
    active_rules: list[str]
    current_task_index: int
    diffs: Annotated[list[FileDiff], operator.add]    # Execution (accumulating)
    audit_results: AuditReport | None                 # Validation
    test_results: TestReport | None
    retry_counts: dict[str, int]                      # Recovery
    errors: Annotated[list[str], operator.add]        # Errors (accumulating)
```

## Key Design Decisions

### Closure Factory Pattern for Graph Nodes

**Context**: LangGraph nodes need access to agent instances, but we want easy testability.

**Decision**: Each node is produced by a factory function that captures agents in a closure:
```python
def make_plan_node(planner, retriever):
    def plan_node(state):
        results = retriever.query(state["directive"])
        tasks = planner.decompose(state["directive"], results)
        return {"task_tree": tasks}
    return plan_node
```

**Consequence**: Tests pass `MagicMock()` instead of real agents. No patching needed.

### TypedDict Over Pydantic for State

**Context**: LangGraph requires TypedDict for state, not Pydantic BaseModel.

**Decision**: `RefactorState` is a TypedDict with `Annotated` reducers. Domain objects (TaskNode, FileDiff) remain Pydantic models.

**Consequence**: Clear separation between pipeline state (mutable dict) and domain data (validated models).

### Environment Variables Only for API Keys

**Context**: CLI args are visible in process lists (`ps aux`) and shell history.

**Decision**: Removed `--api-key` and `--openai-key` CLI flags. Keys are read from `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` environment variables only.

**Consequence**: No credential exposure through process arguments or command history.
