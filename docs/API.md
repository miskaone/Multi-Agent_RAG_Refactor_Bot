# API Reference

## CLI

### `refactor_bot.cli.main`

#### `main(argv: list[str] | None = None) -> int`

Main CLI entry point. Parses arguments, validates inputs, constructs agents, builds the LangGraph pipeline, and invokes it.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `argv` | `list[str] \| None` | Command-line arguments. Defaults to `sys.argv[1:]`. |

**Returns:** Exit code integer (0-5, 130).

#### `build_parser() -> argparse.ArgumentParser`

Builds the argument parser with all positional and optional arguments.

#### `validate_repo_path(raw_path: str) -> str`

Resolves and validates the repository path.

**Raises:** `SystemExit(1)` if path is not a valid directory.

#### `create_agents(args: argparse.Namespace) -> dict`

Constructs all six agents from CLI arguments and environment variables. Uses lazy imports to defer heavy dependencies.

**Returns:** Dict with keys: `indexer`, `retriever`, `planner`, `executor`, `auditor`, `validator`.

#### `format_result_json(result: dict) -> str`

Serializes the pipeline result to JSON. Calls `.model_dump()` on Pydantic objects.

#### `determine_exit_code(result: dict) -> int`

Maps pipeline result to an exit code based on error contents.

---

## Orchestrator

### `refactor_bot.orchestrator.graph`

#### `build_graph(indexer, retriever, planner, executor, auditor, validator) -> CompiledStateGraph`

Constructs and compiles the LangGraph state machine.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `indexer` | `RepoIndexer` | File system indexer |
| `retriever` | `Retriever` | Semantic code retriever |
| `planner` | `Planner` | Task decomposition agent |
| `executor` | `RefactorExecutor` | Code generation agent |
| `auditor` | `ConsistencyAuditor` | AST-based auditor |
| `validator` | `TestValidator` | Test runner agent |

**Returns:** Compiled `StateGraph` ready for `.invoke(state)`.

**Raises:** `GraphBuildError` if graph construction fails.

#### Node Factories

| Factory | Returns | Purpose |
|---------|---------|---------|
| `make_index_node(indexer, retriever)` | closure | Indexes repo and embeds symbols |
| `make_plan_node(planner, retriever)` | closure | Decomposes directive into tasks |
| `make_execute_node(executor, retriever)` | closure | Generates code diffs for next task |
| `make_audit_node(auditor)` | closure | Audits diffs for structural issues |
| `make_validate_node(validator)` | closure | Runs test suite against diffs |
| `make_decide_fn()` | closure | Routes to apply/retry/abort |

#### Direct Nodes

| Function | Purpose |
|----------|---------|
| `apply_node(state)` | Marks current task as COMPLETED |
| `retry_node(state)` | Increments retry count, resets task to PENDING |
| `abort_node(state)` | Writes abort diagnostic to errors |

### `refactor_bot.orchestrator.state`

#### `RefactorState`

TypedDict defining the pipeline state. See [ARCHITECTURE.md](ARCHITECTURE.md#state-machine) for field descriptions.

#### `make_initial_state(directive: str, repo_path: str, max_retries: int = 3) -> RefactorState`

Creates the initial state dict with all fields initialized to defaults. Clamps `max_retries` to `[1, 10]`.

### `refactor_bot.orchestrator.recovery`

| Function | Signature | Description |
|----------|-----------|-------------|
| `find_task_index` | `(task_tree, task_id) -> int` | Index of task by ID, or -1 |
| `get_next_pending_task` | `(task_tree) -> TaskNode \| None` | First PENDING task with all deps COMPLETED |
| `get_current_task` | `(state) -> TaskNode \| None` | Task at `current_task_index` |
| `compute_test_pass_rate` | `(report) -> float` | `passed / (passed + failed)`, 1.0 if no tests |
| `get_task_diffs` | `(diffs, task_id) -> list[FileDiff]` | Filter diffs by task_id |
| `next_task_or_end` | `(state) -> str` | `"continue"` or `"done"` for conditional edge |

---

## Agents

### `refactor_bot.agents.planner.Planner`

```python
Planner(api_key: str | None = None, model: str = "claude-sonnet-4-5-20250929")
```

Decomposes a refactoring directive into a list of `TaskNode` objects via Claude.

#### `decompose(directive: str, retrieval_results: list[RetrievalResult], repo_index: RepoIndex | None = None) -> list[TaskNode]`

**Raises:** `PlanningError`, `DirectiveValidationError`

### `refactor_bot.agents.refactor_executor.RefactorExecutor`

```python
RefactorExecutor(api_key: str | None = None, model: str = "claude-sonnet-4-5-20250929")
```

Generates code modifications as `FileDiff` objects via Claude.

#### `execute(task: TaskNode, context: list[RetrievalResult], repo_index: RepoIndex) -> list[FileDiff]`

**Raises:** `ExecutionError`, `DiffGenerationError`, `DiffValidationError`

### `refactor_bot.agents.consistency_auditor.ConsistencyAuditor`

```python
ConsistencyAuditor(react_rules: list[RefactorRule] | None = None)
```

Validates diffs using tree-sitter AST parsing. Checks for broken imports/exports, anti-patterns, and structural integrity.

#### `audit(diffs: list[FileDiff], repo_index: RepoIndex, task: TaskNode) -> AuditReport`

**Raises:** `AuditError`

### `refactor_bot.agents.test_validator.TestValidator`

```python
TestValidator(api_key: str | None = None, model: str = "...", timeout_seconds: int = 120)
```

Runs the project's test suite in a temporary directory with diffs applied.

#### `validate(diffs: list[FileDiff], repo_path: str) -> TestReport`

**Raises:** `TestValidationError`

### `refactor_bot.agents.repo_indexer.RepoIndexer`

```python
RepoIndexer(exclude_patterns: list[str] | None = None)
```

Walks the filesystem to build a `RepoIndex` with file metadata.

#### `index(repo_path: str) -> RepoIndex`

---

## RAG Pipeline

### `refactor_bot.rag.embeddings.EmbeddingService`

```python
EmbeddingService(api_key: str | None = None)
```

#### `embed(texts: list[str]) -> list[list[float]]`

Generates embeddings via OpenAI's API.

### `refactor_bot.rag.vector_store.VectorStore`

```python
VectorStore(persist_dir: str = "./data/embeddings")
```

ChromaDB-backed vector store with path validation and metadata serialization.

#### `add(documents: list[dict]) -> None`
#### `query(embedding: list[float], top_k: int = 5) -> list[dict]`

### `refactor_bot.rag.retriever.Retriever`

```python
Retriever(embedding_service: EmbeddingService, vector_store: VectorStore)
```

#### `index_repo(repo_index: RepoIndex) -> dict`

Indexes all symbols from the repo into the vector store. Returns embedding statistics.

#### `query(text: str, top_k: int = 5) -> list[RetrievalResult]`

Semantic search for code symbols matching the query.

---

## Models

### `FileDiff`

| Field | Type | Description |
|-------|------|-------------|
| `file_path` | `str` | Relative path to file |
| `original_content` | `str` | Content before modification |
| `modified_content` | `str` | Content after modification |
| `diff_text` | `str` | Unified diff format |
| `task_id` | `str` | Associated task ID |

### `TaskNode`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task_id` | `str` | (required) | Unique task identifier |
| `description` | `str` | (required) | What this task does |
| `affected_files` | `list[str]` | (required) | Files to modify |
| `dependencies` | `list[str]` | `[]` | Task IDs that must complete first |
| `status` | `TaskStatus` | `PENDING` | Current status |
| `applicable_rules` | `list[str]` | `[]` | Rule IDs that apply |

### `TaskStatus` (enum)

`PENDING` | `IN_PROGRESS` | `COMPLETED` | `FAILED` | `SKIPPED`

### `AuditReport`

| Field | Type | Description |
|-------|------|-------------|
| `passed` | `bool` | Whether audit passed |
| `diffs_audited` | `int` | Number of diffs checked |
| `error_count` | `int` | Number of errors found |

### `TestReport`

| Field | Type | Description |
|-------|------|-------------|
| `passed` | `bool` | Whether tests passed |
| `pre_run` | `TestRunResult \| None` | Baseline test results |
| `post_run` | `TestRunResult \| None` | Post-modification results |
| `breaking_changes` | `list[str]` | Detected regressions |
| `runner_available` | `bool` | Whether test runner was found |

### `RepoIndex`

| Field | Type | Description |
|-------|------|-------------|
| `repo_path` | `str` | Absolute path to repo root |

### `RetrievalResult`

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique identifier |
| `file_path` | `str` | Source file path |
| `symbol` | `str` | Symbol name |
| `type` | `str` | Symbol type (function, class, etc.) |
| `source_code` | `str` | Code content |
| `distance` | `float` | Vector distance |
| `similarity` | `float` | Similarity score (1 - distance) |

---

## Exceptions

### Agent Exceptions (inherit from `AgentError`)

| Exception | Raised By | Meaning |
|-----------|-----------|---------|
| `PlanningError` | Planner | Task decomposition failed |
| `ExecutionError` | RefactorExecutor | Code generation failed |
| `AuditError` | ConsistencyAuditor | Audit process failed |
| `TestValidationError` | TestValidator | Test validation failed |
| `DirectiveValidationError` | Planner | Directive contains injection patterns |
| `DiffGenerationError` | RefactorExecutor | Diff creation failed |
| `DiffValidationError` | RefactorExecutor | Generated diff is invalid |
| `SourceFileError` | RefactorExecutor | Source file access failed |
| `TaskDependencyError` | Planner | Task dependency cycle detected |

### Orchestrator Exceptions (inherit from `OrchestratorError`)

| Exception | Meaning |
|-----------|---------|
| `GraphBuildError` | LangGraph construction failed |
