# Codebase Map

Generated: 2026-02-17 (Cycle 7 complete — FINAL)

## Project Structure

```
Multi-Agent_RAG_Refactor_Bot/
├── docs/
│   └── Multi-Agent_RAG_Refactor_Bot_PRD.md   # Product requirements (v2.0)
├── knowledge/                                  # Workflow knowledge system
├── references/                                 # Codebase map, workflow references
├── .workflow/                                  # Transient workflow artifacts
├── src/refactor_bot/                           # Source code
│   ├── models/
│   │   ├── schemas.py                          # Pydantic schemas (71 LOC)
│   │   ├── task_models.py                      # TaskNode, TaskStatus (17 LOC)
│   │   ├── diff_models.py                      # FileDiff model (17 LOC) [Cycle 4]
│   │   └── report_models.py                    # Audit/test report models (63 LOC) [Cycle 5]
│   ├── utils/
│   │   ├── ast_parser.py                       # tree-sitter AST parser (179 LOC)
│   │   └── diff_generator.py                   # generate_unified_diff, validate_diff_with_git, detect_code_style (193 LOC) [Cycle 4]
│   ├── agents/
│   │   ├── repo_indexer.py                     # Repository indexing agent (135 LOC)
│   │   ├── planner.py                          # Planner agent (128 LOC)
│   │   ├── refactor_executor.py                # Refactor Execution Agent (455 LOC) [Cycle 4]
│   │   ├── consistency_auditor.py              # Consistency Auditor agent (AST-based, ~300 LOC) [Cycle 5]
│   │   ├── test_validator.py                   # Test Validator agent (subprocess + LLM fallback, ~250 LOC) [Cycle 5]
│   │   └── exceptions.py                       # Agent error hierarchy (42 LOC) [updated Cycle 5]
│   ├── rag/                                    # RAG pipeline (Cycle 2)
│   │   ├── embeddings.py                       # OpenAI embeddings wrapper (39 LOC)
│   │   ├── vector_store.py                     # ChromaDB integration (70 LOC)
│   │   ├── retriever.py                        # Semantic search (72 LOC)
│   │   └── exceptions.py                       # RAG error hierarchy (4 LOC)
│   ├── rules/                                  # React rule engine (Cycle 3)
│   │   ├── rule_engine.py                      # ReactRule model, select_applicable_rules (22 LOC)
│   │   └── react_rules.py                      # 17 MVP rules (2 LOC)
│   ├── orchestrator/                           # LangGraph pipeline orchestrator [Cycle 6]
│   │   ├── __init__.py                         # Public API: build_graph, make_initial_state, RefactorState (13 LOC)
│   │   ├── exceptions.py                       # OrchestratorError, GraphBuildError (12 LOC)
│   │   ├── state.py                            # RefactorState TypedDict, make_initial_state (80 LOC)
│   │   ├── recovery.py                         # DAG-aware helpers: get_next_pending_task, compute_test_pass_rate, etc. (113 LOC)
│   │   └── graph.py                            # 8 node functions, build_graph() (545 LOC)
│   └── cli/                                    # CLI entry point [Cycle 7]
│       ├── __init__.py                          # Package init with version (3 LOC)
│       ├── __main__.py                          # python -m refactor_bot.cli support (4 LOC)
│       └── main.py                              # argparse CLI, agent factory, dry-run, JSON/human output (~250 LOC)
├── tests/
│   ├── test_ast_parser.py                      # AST parser tests (40 tests)
│   ├── test_repo_indexer.py                    # Repo indexer tests (23 tests)
│   ├── test_embeddings.py                      # Embedding service tests (6 tests)
│   ├── test_retriever.py                       # Retriever tests (7 tests)
│   ├── test_task_models.py                     # TaskNode model tests (12 tests)
│   ├── test_agent_exceptions.py                # Agent exceptions tests (15 tests)
│   ├── test_rule_engine.py                     # Rule engine tests (18 tests)
│   ├── test_planner.py                         # Planner unit tests (27 tests)
│   ├── test_planner_integration.py             # Planner integration tests (10 tests)
│   ├── test_diff_models.py                     # FileDiff model tests (3 tests) [Cycle 4]
│   ├── test_diff_generator.py                  # Diff generator utility tests (10 tests) [Cycle 4]
│   ├── test_refactor_executor.py               # RefactorExecutor tests (18 tests) [Cycle 4]
│   ├── test_auditor.py                         # ConsistencyAuditor tests (8 tests) [Cycle 5]
│   ├── test_validator.py                       # TestValidator tests (12 tests) [Cycle 5]
│   ├── test_orchestrator_state.py              # RefactorState / make_initial_state tests (4 tests) [Cycle 6]
│   ├── test_orchestrator_recovery.py           # Recovery helper tests (10 tests) [Cycle 6]
│   ├── test_orchestrator_graph.py              # Node function unit tests (18 tests) [Cycle 6]
│   ├── test_orchestrator_e2e.py               # End-to-end pipeline tests (4 tests) [Cycle 6]
│   └── test_cli.py                            # CLI entry point tests (24 tests) [Cycle 7]
├── LEARNINGS.md                                # Knowledge index
└── policy-overrides.md                         # Agent policy injection
```

## Status

Cycle 7 complete (FINAL): ~2750 LOC (src only), 262/262 tests passing, 91% coverage.

## Key Decisions

- Python 3.12+ with uv
- Pydantic v2 for data models
- tree-sitter for AST parsing (JS/TS/TSX/JSX)
  - Using `tree-sitter-javascript` and `tree-sitter-typescript` packages
  - Query API: `Query(language, query_string)` + `QueryCursor`
- ChromaDB for vector storage (planned Cycle 2)
- LangGraph for orchestration (planned Cycle 3+)
- Claude Sonnet 4.5 for agents, Opus 4.6 for planner

## Module Boundaries

### Implemented (Cycle 1)

**`src/refactor_bot/models/schemas.py`** (89 LOC)
- `FileLanguage(Enum)`: Supported languages (JS, TS, JSX, TSX)
- `SymbolType(Enum)`: Symbol types (CLASS, FUNCTION, CONST, IMPORT, EXPORT, REACT_COMPONENT)
- `ReactMetadata(BaseModel)`: React-specific metadata (props, hooks, lifecycle methods)
- `Symbol(BaseModel)`: Extracted symbol with name, type, range, relationships
- `FileMetadata(BaseModel)`: File-level metadata (language, symbols, imports, exports)
- `EmbeddingRecord(BaseModel)`: Record for ChromaDB storage (id, content, metadata, embedding)

**`src/refactor_bot/utils/ast_parser.py`** (444 LOC)
- `JavaScriptASTParser`: tree-sitter wrapper for JS/TS/TSX/JSX parsing
  - `parse_file()`: Parse file and return tree-sitter Tree
  - `extract_symbols()`: Extract all symbols from AST
  - `extract_imports()`, `extract_exports()`: Dependency extraction
  - `extract_react_components()`: React component detection with metadata
  - Language-specific query handling (TS vs JS node type differences)

**`src/refactor_bot/agents/repo_indexer.py`** (344 LOC)
- `RepoIndexer`: Repository file discovery and indexing
  - `index_repository()`: Main entry point, returns `list[EmbeddingRecord]`
  - `_discover_files()`: Secure file discovery (skips symlinks, validates boundaries)
  - `_index_file()`: Parse file and create embedding records
  - `_create_embedding_records()`: Split symbols into records for vector DB

**Security**:
- SEC-001 fixed: Symlink attack vector mitigated by skipping symlinks in discovery
- Path validation: All resolved paths checked to be within repository boundary

### Implemented (Cycle 2)

**`src/refactor_bot/rag/exceptions.py`** (15 LOC)
- `RAGError`: Base exception for all RAG operations
- `EmbeddingError`: Embedding generation failures
- `VectorStoreError`: ChromaDB operations failures
- `RetrievalError`: Semantic search failures

**`src/refactor_bot/rag/embedding_service.py`** (80 LOC)
- `EmbeddingService`: OpenAI embeddings wrapper
  - `embed_text()`: Generate embedding for single text
  - `embed_batch()`: Generate embeddings for multiple texts
  - `embed_symbols()`: Generate embeddings for `EmbeddingRecord` list (mutates in-place)
  - Retry logic with exponential backoff (max 3 attempts)
  - Input validation (non-empty text, max batch size 100)

**`src/refactor_bot/rag/vector_store.py`** (120 LOC)
- `VectorStore`: ChromaDB integration
  - `upsert()`: Insert or update embeddings
  - `query()`: Similarity search with metadata filtering
  - `delete()`: Delete records by ID or metadata filter
  - `count()`: Get collection size
  - JSON serialization/deserialization for list metadata fields
  - Path traversal validation for file_path metadata
  - Supports persistent and in-memory collections

**`src/refactor_bot/rag/retriever.py`** (95 LOC)
- `Retriever`: Semantic search orchestration
  - `retrieve()`: End-to-end semantic search (embed query + search + deserialize)
  - `retrieve_with_metadata()`: Search with metadata filters
  - Input validation (query length, top_k bounds, similarity_threshold range)
  - Returns deserialized metadata (JSON lists converted back to Python lists)

**Security**:
- Path traversal validation in VectorStore (file_path metadata)
- Input validation on all public methods
- No hardcoded API keys (requires environment variable)

### Implemented (Cycle 3)

**`src/refactor_bot/models/task_models.py`** (17 LOC)
- `TaskStatus(str, Enum)`: Task execution states (PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED)
- `TaskNode(BaseModel)`: Single task in refactor plan
  - `task_id`: Unique identifier (e.g., "RF-001")
  - `description`: Natural language task description
  - `affected_files`: File paths from repo_index
  - `dependencies`: Other task_ids (for DAG ordering)
  - `status`: Current execution status
  - `applicable_rules`: Rule IDs (e.g., ["REACT-001"])
  - `confidence_score`: Optional 0.0-1.0 confidence (clamped)

**`src/refactor_bot/agents/exceptions.py`** (4 LOC)
- `AgentError`: Base exception for all agent operations
- `PlanningError`: Task decomposition/planning failures
- `DirectiveValidationError`: Invalid user directive (injection, length)
- `TaskDependencyError`: DAG validation failures (cycles, missing deps)

**`src/refactor_bot/agents/planner.py`** (128 LOC)
- `Planner`: Task decomposition agent using Claude Sonnet 4.5
  - `__init__(api_key, model)`: Initialize with Anthropic API key
  - `decompose(directive, repo_index, retriever)`: Main entry point
    - Validates directive (length, injection patterns)
    - Calls Claude with tool-use schema for structured output
    - Validates file paths against repo_index
    - Validates DAG structure (cycle detection via DFS)
    - Attaches applicable rules via select_applicable_rules()
    - Returns 3-6 TaskNodes
  - `_validate_directive()`: 17 substring + 7 regex injection patterns
  - `_validate_file_paths()`: Remove hallucinated paths, error if all invalid
  - `_validate_dag()`: Cycle detection and missing dependency checks
  - Module constants: MAX_DIRECTIVE_LENGTH=2000, MIN_TASKS=3, MAX_TASKS=6

**`src/refactor_bot/rules/rule_engine.py`** (22 LOC)
- `ReactRule(BaseModel)`: Single React refactoring rule
  - `rule_id`: Unique identifier (e.g., "REACT-001")
  - `category`: One of hooks, component_patterns, state_management
  - `priority`: CRITICAL or HIGH
  - `description`: What the rule enforces
  - `incorrect_pattern`: Anti-pattern example (code)
  - `correct_pattern`: Correct pattern example (code)
  - `keywords`: List of keywords for matching
- `select_applicable_rules(directive, is_react_project, all_rules)`: Rule selection
  - Returns [] for non-React projects
  - Keyword-matches directive against rule descriptions/keywords
  - Always includes CRITICAL rules for React projects
  - Returns list of rule_id strings

**`src/refactor_bot/rules/react_rules.py`** (2 LOC)
- `REACT_RULES`: List of 17 MVP rules
  - Categories: hooks (6), component_patterns (6), state_management (5)
  - All CRITICAL or HIGH priority
  - Rules include: avoid-useless-fragment, exhaustive-deps, consistent-function-component, server-component-props, etc.

**Security**:
- Prompt injection validation (17 substring + 7 regex patterns)
- Directive length limit (2000 chars)
- File path validation against repo_index
- Confidence score clamping to [0.0, 1.0]
- API key from environment variable only

### Implemented (Cycle 4)

**`src/refactor_bot/models/diff_models.py`** (17 LOC)
- `FileDiff(BaseModel)`: Unified diff for a single file
  - `file_path`: Relative path from repo root
  - `original_content`: Source content before refactor
  - `modified_content`: Source content after refactor
  - `diff_text`: Unified diff output (git-compatible, a/b prefix format)
  - `is_valid`: Defaults False; set True after git apply --check passes
  - `validation_error`: Error message if validation fails (None on success)
  - `task_id`: Which TaskNode generated this diff
  - Mutable (`frozen=False`) to allow post-creation status updates

**`src/refactor_bot/utils/diff_generator.py`** (193 LOC)
- `generate_unified_diff(file_path, original_content, modified_content) -> str`
  - Uses `difflib.unified_diff` with `a/`/`b/` prefixes for git compatibility
  - Returns empty string when content is identical
- `validate_diff_with_git(diff_text, original_files) -> tuple[bool, str]`
  - Creates temp git repo, writes original files, runs `git apply --check`
  - Returns `(True, "")` on success; `(False, stderr)` on failure
  - Path traversal protection: uses `is_relative_to()` not `startswith()` (L013)
- `detect_code_style(source_code) -> dict[str, str]`
  - Returns `{"indent": "2 spaces"|"4 spaces"|"tabs", "quotes": "single"|"double"}`
  - Defaults to `"4 spaces"` and `"double"` for empty source

**`src/refactor_bot/agents/refactor_executor.py`** (455 LOC)
- `RefactorExecutor`: Execution agent using Claude tool-use for code generation
  - `__init__(api_key, model)`: Validates API key, initializes Anthropic client
  - `execute(task, repo_index, context) -> list[FileDiff]`: Main entry point
    - Reads source files from `task.affected_files`
    - Looks up `ReactRule` objects from `task.applicable_rules`
    - Detects code style from source
    - Builds structured prompt with task + source + rules + context + style
    - Calls Claude with `generate_refactored_code` tool-use schema
    - Parses response into `FileDiff` objects via `difflib.unified_diff`
    - Validates each diff with `git apply --check`
    - Returns list of `FileDiff` with `is_valid` set
  - `_read_source_files(affected_files, repo_index) -> dict[str, str]`
  - `_get_applicable_rules(rule_ids) -> list[ReactRule]`
  - `_build_prompt(task, source_files, context, rules, style) -> str`
  - `_get_tool_schema() -> dict`
  - `_parse_tool_response(response, task_id, source_files) -> list[FileDiff]`
  - `_validate_diffs(diffs) -> list[FileDiff]` (mutates in-place)
  - Module constants: `MAX_FILE_SIZE=100_000`, `MAX_DIFFS_PER_TASK=20`, `MAX_CONTEXT_RESULTS=10`, `DEFAULT_CONTEXT_LINES=3`, `MAX_SOURCE_PREVIEW=500`, `MAX_API_TOKENS` (extracted from review finding CQ-C4-007)

**`src/refactor_bot/agents/exceptions.py`** (33 LOC, updated)
- Added (Cycle 4):
  - `ExecutionError(AgentError)`: Base exception for refactor execution operations
  - `DiffGenerationError(ExecutionError)`: Diff creation failures
  - `DiffValidationError(ExecutionError)`: git apply --check failures
  - `SourceFileError(ExecutionError)`: Source file read/parse failures

**Security** (Cycle 4):
- SEC-C4-002 fixed: Path traversal in `validate_diff_with_git` — added `.resolve()` + `is_relative_to()` check
- SEC-C4-003 fixed: Prompt injection via source code — added defense-in-depth prompt instructions
- Source file size limit (MAX_FILE_SIZE) prevents token exhaustion

### Implemented (Cycle 5)

**`src/refactor_bot/models/report_models.py`** (63 LOC)
- `FindingSeverity(str, Enum)`: `ERROR`, `WARNING`, `INFO` — ERROR blocks apply, WARNING is informational
- `AuditFinding(BaseModel)`: Single finding with `finding_id`, `file_path`, `finding_type`, `severity`, `description`, `line_number`, `rule_id`, `evidence`
- `AuditReport(BaseModel)`: Consolidated audit result — `passed`, `findings`, `error_count`, `warning_count`, `info_count`, `diffs_audited`, `audited_at`
- `TestRunResult(BaseModel)`: Single test runner invocation — `runner`, `exit_code`, `stdout`, `stderr`, `passed`, `failed`, `skipped`, `duration_seconds`
- `BreakingChange(BaseModel)`: Test that passed before diff but fails after — `test_name`, `file_path`, `failure_message`
- `TestReport(BaseModel)`: Full test run summary — `passed`, `pre_run`, `post_run`, `breaking_changes`, `runner_available`, `llm_analysis`, `tested_at`

**`src/refactor_bot/agents/consistency_auditor.py`** (~300 LOC)
- `ConsistencyAuditor`: Checks diffs for structural integrity using tree-sitter AST analysis
  - `__init__(react_rules)`: Initialize with optional rule override (defaults to REACT_RULES)
  - `audit(diffs, repo_index) -> AuditReport`: Orchestrates all 4 checks; collects findings; never raises on individual failures
  - `_check_orphaned_imports(diff) -> list[AuditFinding]`: Parses `modified_content` in memory; queries named/namespace/default import bindings; counts AST identifier nodes (both `identifier` and `type_identifier`) outside import statements
  - `_check_signature_mismatches(diffs, repo_index) -> list[AuditFinding]`: Builds exported-name map from diffs; compares against repo_index baseline; detects renames and removals that break callers
  - `_check_dependency_integrity(diffs, repo_index) -> list[AuditFinding]`: Verifies each import path resolves to a file in repo_index or is a package import (no `./` or `../` prefix)
  - `_check_react_anti_patterns(diff) -> list[AuditFinding]`: Matches `modified_content` against `ANTI_PATTERN_SIGNALS` dict; only called when `repo_index.is_react_project` is True; filtered by `self._rules`
  - `_parse_content(file_path, content) -> tuple[Tree, Language] | None`: In-memory tree-sitter parse (not disk I/O)
  - `_next_finding_id() -> str`: Increments `_finding_counter`; returns `"AF-NNN"` format
- `ANTI_PATTERN_SIGNALS: dict[str, list[str]]`: Maps rule_id → list of string signals to search for in `modified_content`

**`src/refactor_bot/agents/test_validator.py`** (~250 LOC)
- `TestValidator`: Runs test suite against post-diff repo state; falls back to LLM analysis
  - `__init__(api_key, model, timeout_seconds)`: Creates `Anthropic` client only if `api_key` available
  - `validate(repo_path, diffs) -> TestReport`: Main entry — validate path, detect runner, run pre/post tests, compute breaking changes; uses try/finally for temp dir cleanup (bare `except Exception`)
  - `_detect_runner(repo_path) -> str | None`: Reads `package.json`; returns `"vitest"` if vitest in test script, `"npm_test"` if any test script, `None` otherwise
  - `_run_tests(repo_path, runner) -> TestRunResult`: `subprocess.run` with `capture_output=True`; catches `TimeoutExpired` → `exit_code=TIMEOUT_EXIT_CODE (-1)`
  - `_apply_diffs_to_temp(repo_path, diffs) -> str`: `shutil.copytree(symlinks=False)`; writes `modified_content`; validates each target with `is_relative_to()` before write
  - `_parse_test_output(result) -> TestRunResult`: Applies `VITEST_SUMMARY_RE` and `JEST_SUMMARY_RE` to `stdout`; mutates and returns input
  - `_compute_breaking_changes(pre, post) -> list[BreakingChange]`: Extracts failed test names via `VITEST_FAIL_RE`; returns `post_failed - pre_failed`
  - `_llm_fallback(diffs) -> str`: Dual-layer injection defense (L014); validates `file_path` against `SAFE_PATH_RE`; plain-text prompt to Claude
- Module constants: `VITEST_SUMMARY_RE`, `JEST_SUMMARY_RE`, `VITEST_FAIL_RE`, `DEFAULT_TIMEOUT=120`, `SAFE_PATH_RE`, `TIMEOUT_EXIT_CODE=-1`

**`src/refactor_bot/agents/exceptions.py`** (42 LOC, updated)
- Added (Cycle 5):
  - `AuditError(AgentError)`: Raised on catastrophic audit failure (all diffs unparseable)
  - `TestValidationError(AgentError)`: Raised for missing repo_path or path traversal in diffs (renamed from `ValidationError` to avoid pydantic collision — L017)

**Security** (Cycle 5):
- SEC-C5-002 fixed: `shutil.copytree(symlinks=False)` prevents symlink escape in temp dir operations (L018)
- Path traversal: `_apply_diffs_to_temp()` validates every `diff.file_path` via `is_relative_to()` before write (L016)
- Dual-layer LLM injection defense in `_llm_fallback()`: `SAFE_PATH_RE` validation + "DATA to be reviewed" framing (L014)

### Implemented (Cycle 6)

**`src/refactor_bot/orchestrator/exceptions.py`** (12 LOC)
- `OrchestratorError(Exception)`: Base exception for orchestrator operations
- `GraphBuildError(OrchestratorError)`: Raised when StateGraph construction fails

**`src/refactor_bot/orchestrator/state.py`** (80 LOC)
- `RefactorState(TypedDict)`: Full pipeline state — 15 fields
  - `directive`, `repo_path`, `max_retries`: inputs
  - `repo_index`, `embedding_stats`, `is_react_project`: indexing output
  - `context_bundles`, `task_tree`, `active_rules`, `current_task_index`: planning/execution
  - `diffs`: `Annotated[list[FileDiff], operator.add]` — accumulating reducer
  - `audit_results`, `test_results`: validation outputs
  - `retry_counts`: per-task retry accounting
  - `errors`: `Annotated[list[str], operator.add]` — accumulating error log
- `make_initial_state(directive, repo_path, max_retries=3) -> RefactorState`
  - Clamps `max_retries` to [1, 10] via `MAX_RETRIES_LIMIT = 10`

**`src/refactor_bot/orchestrator/recovery.py`** (113 LOC)
- `find_task_index(task_tree, task_id) -> int`: Linear search; returns -1 if not found
- `get_next_pending_task(task_tree) -> TaskNode | None`: DAG-aware; only returns tasks whose all deps are COMPLETED
- `get_current_task(state) -> TaskNode | None`: Returns task at `current_task_index` or None
- `compute_test_pass_rate(report) -> float`: `passed/(passed+failed)` from `post_run`; 1.0 if no tests
- `get_task_diffs(diffs, task_id) -> list[FileDiff]`: Filters accumulated diffs to current task
- `next_task_or_end(state) -> str`: Router returning `"continue"` or `"done"`

**`src/refactor_bot/orchestrator/graph.py`** (545 LOC)
- `make_index_node(indexer, retriever)`: Closure — indexes repo, stores in state
- `make_plan_node(planner, retriever)`: Closure — decomposes directive into task_tree
- `make_execute_node(executor, retriever)`: Closure — runs next DAG-eligible PENDING task; always returns `diffs` as list (L025)
- `make_audit_node(auditor)`: Closure — audits current task's diffs; synthetic AuditReport on exception
- `make_validate_node(validator)`: Closure — runs tests against accumulated diffs; synthetic TestReport on exception
- `apply_node(state) -> dict`: Marks current task COMPLETED
- `retry_node(state) -> dict`: Increments retry count, marks task PENDING, appends feedback context; None-guards `post_run` (L023)
- `skip_node(state) -> dict`: Marks current task SKIPPED (reachable only from future router extensions)
- `abort_node(state) -> dict`: Writes diagnostic summary to errors list
- `make_decide_fn()`: Router for `validate_node` conditional edge — returns `"apply"`, `"retry"`, or `"abort"` (L022)
- `build_graph(indexer, retriever, planner, executor, auditor, validator)`: Closure factory pattern (L024); compiles StateGraph; raises `GraphBuildError` on failure

**Graph topology**:
```
START -> index_node -> plan_node -> execute_node -> audit_node -> validate_node
validate_node -> decide_fn -> {apply_node, retry_node, abort_node}
apply_node -> next_task_or_end -> {execute_node, END}
retry_node -> execute_node
abort_node -> END
```

**Module constants**:
- `TEST_PASS_RATE_ABORT_THRESHOLD = 0.85`
- `PLAN_NODE_TOP_K = 10`
- `EXECUTE_NODE_TOP_K = 5`

**Security** (Cycle 6):
- `max_retries` clamped to [1, 10] — prevents unbounded retry loops (SEC-C6-004)

### Implemented (Cycle 7)

**`src/refactor_bot/cli/__init__.py`** (3 LOC)
- Package marker with `__version__` string

**`src/refactor_bot/cli/__main__.py`** (4 LOC)
- `if __name__ == "__main__"` guard calling `main()` — enables `python -m refactor_bot.cli`

**`src/refactor_bot/cli/main.py`** (~250 LOC)
- `build_parser() -> argparse.ArgumentParser`: Defines CLI args (directive, repo_path, --dry-run, --json, --max-retries, --timeout, --model, --vector-store-dir)
- `create_agents(config) -> dict`: Lazy-imports all heavy deps (anthropic, chromadb, tree-sitter, langgraph) and constructs agent instances
- `main(argv=None) -> int`: Entry point — parses args, validates inputs, handles dry-run, invokes orchestrator pipeline, formats output
- `_handle_error(error, exit_code, output_json) -> int`: DRY helper for exception-to-exit-code mapping
- Exit codes: `EXIT_SUCCESS=0`, `EXIT_INVALID_INPUT=1`, `EXIT_AGENT_ERROR=2`, `EXIT_ORCHESTRATOR_ERROR=3`, `EXIT_GRAPH_ABORT=4`, `EXIT_UNEXPECTED=5`, `EXIT_KEYBOARD_INTERRUPT=130`
- `ABORT_PREFIX = "ABORT:"` — sentinel for abort detection via `startswith()` (not substring match)
- `_SAFE_CONFIG_KEYS` — allowlist preventing secret leakage in output

**Security** (Cycle 7):
- SEC-C7-001: No API key CLI arguments — env vars only (ps aux / shell history exposure)
- SEC-C7-002: `_SAFE_CONFIG_KEYS` allowlist prevents accidental secret leakage in dry-run/JSON output

## Known Technical Debt

### Deferred from Cycle 1 Review
- **ARCH-002**: `_index_file()` violates SRP — combines parsing, symbol extraction, and record creation
- **CQ-013**: DRY violation in `extract_symbols()` — repeated try-except blocks for each symbol type
- **CQ-017**: Missing I/O error handling in file read operations

### Deferred from Cycle 2 Review
- None (all Critical findings fixed)

### Deferred from Cycle 3 Review
- **ARCH-C3-001**: Planner decompose() has 8 responsibilities (SRP violation) — defer to future refactor
- **ARCH-C3-002**: Rule selection in data module instead of agents — acceptable for MVP
- **ARCH-C3-009**: Missing Retriever integration — planned for Cycle 4
- **CQ-C3-005**: Cycle detection duplication — minor, acceptable
- **CQ-C3-006**: Overly broad exception handling — acceptable for external API calls
- **SEC-C3-002**: API key exposure risk (env var pattern) — standard practice
- **SEC-C3-003**: File path traversal — already mitigated in _validate_file_paths

### Deferred from Cycle 4 Review
- **ARCH-C4-005**: execute() returns bare list with no execution metadata — defer to Cycle 5 wrapper
- **ARCH-C4-002**: FileDiff mutation in _validate_diffs — acceptable pattern, consistent with TaskNode
- **ARCH-C4-004**: detect_code_style in utils rather than agents — acceptable for now

### Deferred from Cycle 6 Review

- **ARCH-C6-004/007**: No error gate after index_node/plan_node — if these fail (errors populated), the graph cascades to execute_node with None repo_index rather than aborting early
- **ARCH-C6-005**: `get_current_task()` defined in recovery.py but never called in graph.py — future cleanup or use in Cycle 7
- **ARCH-C6-008**: `current_task_index` field name implies sequential indexing but pipeline uses DAG-based selection via `get_next_pending_task` — naming mismatch could confuse future maintainers
- **ARCH-C6-009**: `validate_node` passes all accumulated `state["diffs"]` to `validator.validate()`, not just the current task's diffs — intentional for test correctness but may revalidate prior tasks unnecessarily
- **ARCH-C6-010**: `TEST_PASS_RATE_ABORT_THRESHOLD` (0.85) is a module constant, not configurable at graph build time — acceptable for MVP
- **ARCH-C6-011**: No `pipeline_status` field in state — CLI/operator cannot observe pipeline phase without inspecting task_tree
- **ARCH-C6-014**: `get_next_pending_task` uses only `COMPLETED` in `completed_ids` — SKIPPED tasks are not in the set, so their dependents remain blocked even after skip
- **SEC-C6-001-003**: `directive` and `repo_path` inputs not validated at state initialization — deferred to CLI layer (Cycle 7)
- **SEC-C6-005-006**: No scanning of task descriptions or file paths for injection content in node functions — deferred
- **CQ-C6-005**: Bounds-check pattern (`if 0 <= current_idx < len(updated_tree)`) duplicated across 4 nodes — acceptable duplication for now
- **CQ-C6-011**: Test helper fixtures duplicated across 3 test files — acceptable for now

### Deferred from Cycle 5 Review
- **ARCH-C5-003**: ConsistencyAuditor.audit() has 5 responsibilities (SRP) — defer to future refactor
- **ARCH-C5-004**: _check_dependency_integrity uses O(N*M) brute-force — defer to future cycle
- **CQ-C5-005**: extract_failed_tests nested inside _compute_breaking_changes — minor, acceptable
- **ARCH-C5-007**: _parse_content called multiple times per diff (perf) — acceptable for MVP
- **ARCH-C5-008**: _llm_fallback prompt not configurable — acceptable for MVP
- **ARCH-C5-009**: TestValidator.__init__ creates Anthropic client eagerly — acceptable
- **ARCH-C5-010**: No retry logic on subprocess timeout — defer to future cycle
- **CQ-C5-006**: Regex patterns could use re.VERBOSE for readability — minor

## Test Coverage

- 262 tests across 19 test files
- 91% line coverage
- RAG tests use mocked OpenAI API and in-memory ChromaDB
- Planner and RefactorExecutor tests use mocked Anthropic API (no real network calls)
- diff_generator tests use real subprocess git calls in temp directories
- ConsistencyAuditor tests use tree-sitter on in-memory content (no disk I/O, no mocking)
- TestValidator tests use mocked subprocess.run and mocked Anthropic client
