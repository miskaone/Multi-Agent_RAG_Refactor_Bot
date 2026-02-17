# Multi-Agent RAG Refactor Bot

## Product Requirements Document (PRD)

**Version:** 2.0\
**Date:** 2026-02-16\
**Execution Method:** Agent Team Dev Workflow (`/agent-team-dev-workflow`)

------------------------------------------------------------------------

# 1. Executive Summary

The **Multi-Agent RAG Refactor Bot** is an autonomous, multi-agent
system designed to:

-   Ingest a multi-file codebase
-   Build semantic embeddings across files
-   Identify architectural or performance issues
-   Propose and apply coordinated refactors
-   Validate changes via tests
-   Generate PR-ready outputs

Primary Goal:

> Validate whether multi-agent orchestration can safely perform
> large-scale, structured code refactors.

------------------------------------------------------------------------

# 2. Problem Statement

Modern AI coding agents perform well on single-file edits but struggle
with:

-   Cross-file architectural changes
-   Maintaining invariants across modules
-   Coordinated updates across implementation and tests
-   Avoiding cascading regressions

This system addresses those weaknesses through structured multi-agent
orchestration and repository-wide RAG.

------------------------------------------------------------------------

# 3. Objectives

## 3.1 Functional Objectives

1.  Parse and index a multi-file repository\
2.  Generate embeddings per file and function\
3.  Accept a refactor directive\
4.  Decompose directive into structured tasks\
5.  Execute coordinated edits\
6.  Validate correctness\
7.  Generate structured pull request output

## 3.2 Non-Functional Objectives

-   Reproducible outputs given the same model version and temperature=0\
-   Structured JSON tool communication\
-   No hallucinated file paths (all paths validated against indexed file list)\
-   Maintain test pass rate >= 95% post-refactor\
-   Avoid circular edit loops (max 3 retries per task before abort)

------------------------------------------------------------------------

# 4. Target Use Cases

## 4.1 Architectural Refactor

Input:\
Convert synchronous file operations to async across project.

Expected: - Modify multiple modules\
- Update function signatures\
- Adjust call chains\
- Update tests

## 4.2 Performance Refactor

Input:\
Replace naive O(n²) search with indexed lookup strategy.

Expected: - Identify hotspot\
- Introduce abstraction\
- Replace usages\
- Ensure behavioral equivalence

## 4.3 Security Hardening

Input:\
Replace raw SQL string interpolation with parameterized queries.

Expected: - Detect unsafe patterns\
- Replace with safe calls\
- Update tests

## 4.4 React / Next.js Performance Optimization

The system includes a built-in **React Best Practices Rule Engine** based on the Vercel React performance optimization guide (57 rules across 8 categories). This enables a dedicated class of refactor directives targeting React and Next.js codebases.

### Example Directives

**Waterfall elimination (CRITICAL)**\
Input: `Eliminate request waterfalls across the project.`\
Expected: - Identify sequential awaits on independent promises\
- Refactor to `Promise.all()` / parallel fetching\
- Add `<Suspense>` boundaries for streaming\
- Rules applied: `async-parallel`, `async-defer-await`, `async-suspense-boundaries`

**Bundle size optimization (CRITICAL)**\
Input: `Reduce bundle size by fixing barrel imports and lazy-loading heavy components.`\
Expected: - Replace barrel file imports with direct path imports\
- Convert heavy components to `next/dynamic`\
- Defer third-party scripts (analytics, logging) to post-hydration\
- Rules applied: `bundle-barrel-imports`, `bundle-dynamic-imports`, `bundle-defer-third-party`

**Re-render optimization (MEDIUM)**\
Input: `Fix unnecessary re-renders across components.`\
Expected: - Extract expensive work into memoized child components\
- Replace raw state subscriptions with derived booleans\
- Move effect logic to event handlers where appropriate\
- Hoist default non-primitive props\
- Rules applied: `rerender-memo`, `rerender-derived-state`, `rerender-move-effect-to-event`, `rerender-memo-with-default-value`

**Server-side performance (HIGH)**\
Input: `Optimize server component data fetching and serialization.`\
Expected: - Add `React.cache()` for per-request dedup\
- Minimize data passed to client components\
- Restructure component tree to parallelize fetches\
- Rules applied: `server-cache-react`, `server-serialization`, `server-parallel-fetching`

------------------------------------------------------------------------

# 5. System Architecture

## 5.1 Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **LLM** | Claude Sonnet 4.5 via Anthropic API | Best code reasoning; tool-use support |
| **Orchestration** | LangGraph (Python) | Native support for stateful multi-agent graphs with cycles and branching |
| **Embedding Model** | OpenAI `text-embedding-3-small` | Cost-effective, 1536-dim, strong code retrieval |
| **Vector Store** | ChromaDB (local, persistent) | Zero-infrastructure, file-backed, supports metadata filtering |
| **AST Parsing** | tree-sitter (JS/TS/TSX grammars) | Language-agnostic AST extraction, fast, battle-tested |
| **React Rule Engine** | Vercel React Best Practices (57 rules, 8 categories) | Prioritized performance rules for automated React/Next.js refactoring |
| **Diff Generation** | unified diff via `difflib` | Standard format, directly applicable via `git apply` |
| **Runtime** | Python 3.12+ | LangGraph ecosystem, async support |
| **Package Manager** | uv | Fast dependency resolution |

## 5.2 Agent Topology

### Planner Agent

-   Accepts directive\
-   Breaks into structured tasks\
-   Assigns specialist agents\
-   Tracks task state

### Repo Indexer Agent

-   Parses repository\
-   Builds embeddings\
-   Constructs dependency graph

### Context Retrieval Agent (RAG)

-   Retrieves relevant files\
-   Expands via dependency graph\
-   Returns structured context bundles

### Refactor Execution Agent

-   Produces file diffs\
-   Maintains formatting conventions\
-   Preserves public interfaces unless instructed\
-   When operating on React/Next.js code, applies relevant rules from the React Best Practices Rule Engine (see Section 5.5)

### Consistency Auditor Agent

-   Validates signatures\
-   Checks imports\
-   Verifies dependency integrity\
-   For React codebases: validates that refactored code does not introduce anti-patterns (e.g., barrel re-exports, missing Suspense boundaries, unnecessary re-renders)

### Test Validator Agent

-   Executes test suite via subprocess (`npm test` / `vitest run`)\
-   Falls back to LLM-based static analysis when no test runner is configured\
-   Compares pre- and post-refactor test results\
-   Detects breaking changes\
-   Produces validation report with pass/fail counts and failure details

### PR Generator Agent

Outputs: - PR title\
- Summary\
- Change list\
- Risk assessment\
- Rollback instructions

## 5.3 Inter-Agent Communication Protocol

Agents communicate via a **shared state graph** managed by LangGraph. Each agent reads from and writes to a typed state object passed through the graph edges.

### State Schema

``` python
class RefactorState(TypedDict):
    directive: str                    # Original user refactor directive
    repo_index: RepoIndex             # File list, AST data, dependency graph
    embeddings: list[EmbeddingRecord] # Vector embeddings with metadata
    task_tree: list[TaskNode]         # Decomposed tasks from planner
    context_bundles: dict[str, list]  # Task ID -> relevant file contents
    diffs: list[FileDiff]             # Produced diffs per file
    audit_results: AuditReport        # Consistency check results
    test_results: TestReport          # Test validation results
    pr_output: PROutput               # Final PR content
    errors: list[AgentError]          # Error log for recovery decisions
    retry_counts: dict[str, int]      # Task ID -> retry count
    active_rules: list[str]           # React best practice rule IDs active for this run
    is_react_project: bool            # Auto-detected during ingestion
```

### Communication Rules

-   Agents do **not** call each other directly; all routing is handled by the LangGraph state machine\
-   Each agent receives only the state fields it needs (scoped reads)\
-   Each agent returns only the state fields it modifies (scoped writes)\
-   Errors are appended to `errors` and the Planner Agent decides recovery action\
-   All agent inputs/outputs are validated against Pydantic schemas

## 5.4 Recovery and Rollback Strategy

When an agent produces invalid output or validation fails:

1.  **Retry with narrowed scope** — Planner re-issues the failed task with additional context from the error log (max 3 retries per task)\
2.  **Skip and continue** — If a sub-task is non-critical (e.g., updating a single test file), the Planner marks it as `skipped` and continues with remaining tasks\
3.  **Partial rollback** — If the Consistency Auditor detects cascading issues, all diffs from the current task subtree are discarded and the task is re-planned\
4.  **Full abort** — If retry count exceeds the limit or test pass rate drops below 85%, the system aborts, outputs a diagnostic report, and preserves the original codebase unchanged

All diffs are held in memory and only written to disk (via `git apply`) after full validation passes. The original repository is never modified in-place during execution.

## 5.5 React Best Practices Rule Engine

For React and Next.js codebases, the system includes an embedded rule engine derived from the Vercel React performance optimization guide. This provides structured, priority-ranked guidance to the Refactor Execution Agent and Consistency Auditor Agent.

### Rule Categories (by priority)

| Priority | Category | Impact | Rule Count |
|----------|----------|--------|------------|
| 1 | Eliminating Waterfalls | CRITICAL | 5 rules (`async-*`) |
| 2 | Bundle Size Optimization | CRITICAL | 5 rules (`bundle-*`) |
| 3 | Server-Side Performance | HIGH | 7 rules (`server-*`) |
| 4 | Client-Side Data Fetching | MEDIUM-HIGH | 4 rules (`client-*`) |
| 5 | Re-render Optimization | MEDIUM | 12 rules (`rerender-*`) |
| 6 | Rendering Performance | MEDIUM | 9 rules (`rendering-*`) |
| 7 | JavaScript Performance | LOW-MEDIUM | 12 rules (`js-*`) |
| 8 | Advanced Patterns | LOW | 3 rules (`advanced-*`) |

### How the Rule Engine Integrates

1.  **Detection** — During Phase 1 (Repository Ingestion), the Repo Indexer Agent detects whether the project is a React/Next.js codebase by checking for `react` / `next` in `package.json` dependencies and the presence of `.tsx`/`.jsx` files\
2.  **Rule selection** — The Planner Agent maps the user's directive to applicable rule categories. For example, a "fix performance" directive activates rules in priority order (waterfalls first, then bundle size, etc.)\
3.  **Context enrichment** — The Context Retrieval Agent includes the relevant rule definitions (incorrect pattern + correct pattern) in the context bundle alongside the source files\
4.  **Execution** — The Refactor Execution Agent receives both the source code and the applicable rules, producing diffs that transform anti-patterns into the correct patterns\
5.  **Audit** — The Consistency Auditor Agent validates that refactored code does not reintroduce any of the anti-patterns defined in the active rules

### Key Rules Applied by Directive Type

| Directive | Primary Rules |
|-----------|--------------|
| "Eliminate waterfalls" | `async-parallel`, `async-defer-await`, `async-suspense-boundaries`, `server-parallel-fetching` |
| "Reduce bundle size" | `bundle-barrel-imports`, `bundle-dynamic-imports`, `bundle-defer-third-party`, `bundle-conditional` |
| "Fix re-renders" | `rerender-memo`, `rerender-derived-state`, `rerender-move-effect-to-event`, `rerender-functional-setstate` |
| "Optimize server components" | `server-cache-react`, `server-serialization`, `server-dedup-props`, `server-after-nonblocking` |
| "General performance audit" | All rules applied in priority order (CRITICAL → HIGH → MEDIUM → LOW) |

------------------------------------------------------------------------

# 6. Data Models

## 6.1 Embedding Metadata Schema

``` json
{
  "file_path": "src/utils/math.ts",
  "symbol": "calculateInterest",
  "type": "function",
  "dependencies": ["finance.ts"],
  "imports": ["lodash"],
  "hash": "sha256",
  "embedding_vector": [],
  "react_metadata": {
    "is_component": false,
    "is_server_component": null,
    "uses_hooks": [],
    "has_suspense_boundary": false,
    "is_barrel_file": false
  }
}
```

Note: `react_metadata` is populated only when `is_react_project` is true. It enables the Rule Engine to quickly identify components that match anti-patterns (e.g., barrel files for `bundle-barrel-imports`, components missing Suspense for `async-suspense-boundaries`).

## 6.2 Task State Schema

``` json
{
  "task_id": "RF-001",
  "status": "in_progress",
  "affected_files": [],
  "validation_status": null,
  "confidence_score": null
}
```

------------------------------------------------------------------------

# 7. Runtime Workflow (Product Pipeline)

When the built system is **running against a target repository**, it executes this pipeline:

1.  **Ingest** — Scan directory, build AST per file, extract symbols, generate embeddings, construct call graph
2.  **Decompose** — Planner creates structured task tree from user directive
3.  **Retrieve** — Fetch relevant files per sub-task via RAG, expand via dependency graph
4.  **Execute** — Produce unified diffs, ensure formatting compliance
5.  **Re-index** — Incrementally re-parse modified files, regenerate embeddings for changed symbols, update dependency graph edges
6.  **Validate** — Run consistency checks (orphaned imports, signature mismatches, cyclic deps) and test suite (subprocess or LLM-based fallback)
7.  **Generate PR** — Output summary, code diffs, risk rating, validation results, confidence score

------------------------------------------------------------------------

# 8. Implementation Roadmap (Workflow Cycles)

This project is built using the **Agent Team Dev Workflow** (`/agent-team-dev-workflow`). Each cycle follows: **Discover → Plan → Work → Test → Review → Compound**.

The implementation is decomposed into **7 ordered cycles**. Each cycle produces a shippable increment. Later cycles depend on earlier ones via continuation contracts.

## Cycle 1: Project Scaffold & Repo Indexer

**Complexity**: Standard\
**Goal**: Set up the project structure and build the repository ingestion pipeline.

**Deliverables**:
-   Python project with `uv` + `pyproject.toml`
-   `src/` package structure: `agents/`, `models/`, `rag/`, `cli/`, `utils/`
-   Pydantic data models: `RepoIndex`, `EmbeddingRecord`, `SymbolInfo`
-   Repo Indexer module: tree-sitter AST parsing for JS/TS/TSX, symbol extraction, dependency graph construction
-   Unit tests for parsing and symbol extraction

**Files to create**:
-   `pyproject.toml`, `src/__init__.py`, `src/models/schemas.py`
-   `src/agents/repo_indexer.py`
-   `src/utils/ast_parser.py` (tree-sitter wrapper)
-   `tests/test_repo_indexer.py`, `tests/fixtures/` (sample JS/TS files)

**Acceptance criteria**:
-   `repo_indexer.index("./fixtures")` returns a `RepoIndex` with correct file list, symbols, and dependency edges
-   Handles `.js`, `.ts`, `.tsx`, `.jsx` files
-   Detects React projects via `package.json` inspection and populates `react_metadata`

**DoD verification**: Run `pytest tests/test_repo_indexer.py` — all pass

---

## Cycle 2: Embedding Pipeline & ChromaDB Integration

**Complexity**: Standard\
**Depends on**: Cycle 1 (uses `RepoIndex`, `SymbolInfo` models)

**Goal**: Generate and store embeddings per symbol, enable semantic retrieval.

**Deliverables**:
-   OpenAI embedding generation for each symbol's source code
-   ChromaDB collection creation and persistence
-   Retrieval function: query by natural language, return ranked file/symbol matches
-   Incremental re-indexing: update only changed files

**Files to create**:
-   `src/rag/embeddings.py`, `src/rag/vector_store.py`, `src/rag/retriever.py`
-   `tests/test_embeddings.py`, `tests/test_retriever.py`

**Acceptance criteria**:
-   Embeddings generated for all symbols in a test fixture repo
-   `retriever.query("async file operations")` returns relevant symbols with similarity scores
-   Re-index after file modification updates only changed embeddings
-   Retrieval precision >= 0.8 on test fixtures

**Continuation contract**:
-   `retriever.query(query: str, top_k: int) -> list[RetrievalResult]`
-   `vector_store.upsert(records: list[EmbeddingRecord])` for incremental updates

---

## Cycle 3: Planner Agent & Task Decomposition

**Complexity**: Standard\
**Depends on**: Cycle 2 (uses retriever for context)

**Goal**: Accept a natural language directive, decompose into an ordered task tree with affected files per task.

**Deliverables**:
-   Planner Agent: takes directive + `RepoIndex` + retrieval results, outputs `list[TaskNode]`
-   `TaskNode` model with: task_id, description, affected_files, dependencies, status
-   Claude API integration (Sonnet 4.5) with structured tool-use output
-   React Rule Engine integration: auto-select applicable rules when `is_react_project=True`

**Files to create**:
-   `src/agents/planner.py`, `src/models/task_models.py`
-   `src/rules/react_rules.py`, `src/rules/rule_engine.py`
-   `tests/test_planner.py`

**Acceptance criteria**:
-   Given directive "Convert sync file ops to async" + test repo, planner produces 3-6 ordered tasks
-   Each task has non-empty `affected_files` that exist in the repo index
-   Task dependency ordering is valid (no cycles)
-   React directive produces tasks tagged with applicable rule IDs

**Continuation contract**:
-   `planner.decompose(directive: str, repo_index: RepoIndex, context: list[RetrievalResult]) -> list[TaskNode]`

---

## Cycle 4: Refactor Execution Agent & Diff Generation

**Complexity**: Complex\
**Depends on**: Cycle 3 (uses `TaskNode` list and context bundles)

**Goal**: Execute each task by producing unified diffs that implement the planned changes.

**Deliverables**:
-   Refactor Execution Agent: takes a `TaskNode` + context bundle + source files, outputs `list[FileDiff]`
-   Diff generation in unified format (`git apply` compatible)
-   Convention preservation: reads existing code style from context
-   React rule application: when rules are active, includes incorrect/correct pattern in prompt

**Files to create**:
-   `src/agents/refactor_executor.py`, `src/models/diff_models.py`
-   `src/utils/diff_generator.py`
-   `tests/test_refactor_executor.py`

**Acceptance criteria**:
-   Given a "convert to async" task + source file, produces a valid unified diff
-   `git apply --check` succeeds on all generated diffs
-   Public interfaces preserved unless the directive explicitly modifies them
-   React rule-tagged tasks produce diffs matching the rule's correct pattern

---

## Cycle 5: Consistency Auditor & Test Validator

**Complexity**: Standard\
**Depends on**: Cycle 4 (validates diffs produced by executor)

**Goal**: Validate that generated diffs maintain structural integrity and tests pass.

**Deliverables**:
-   Consistency Auditor Agent: checks imports, signatures, dependency integrity across all diffs
-   Test Validator Agent: runs `npm test`/`vitest run` via subprocess, compares pre/post results
-   LLM-based static analysis fallback when no test runner is configured
-   `AuditReport` and `TestReport` models
-   React anti-pattern validation: auditor checks diffs against active rules

**Files to create**:
-   `src/agents/consistency_auditor.py`, `src/agents/test_validator.py`
-   `src/models/report_models.py`
-   `tests/test_auditor.py`, `tests/test_validator.py`

**Acceptance criteria**:
-   Auditor detects a deliberately introduced orphaned import in test fixture
-   Auditor detects a signature mismatch between caller and callee
-   Test validator runs tests and produces pass/fail report
-   Validator correctly identifies a breaking change in a pre-built failing fixture

**Continuation contract**:
-   `auditor.audit(diffs: list[FileDiff], repo_index: RepoIndex) -> AuditReport`
-   `validator.validate(repo_path: str, diffs: list[FileDiff]) -> TestReport`

---

## Cycle 6: Pipeline Orchestration & State Machine

**Complexity**: Complex\
**Depends on**: Cycles 1-5 (integrates all agents)

**Goal**: Wire all agents into the LangGraph state machine with the full `RefactorState`, recovery logic, and retry handling.

**Deliverables**:
-   LangGraph graph definition connecting all agents in the pipeline order
-   `RefactorState` TypedDict as the shared state object
-   Recovery and rollback logic: retry → skip → partial rollback → abort
-   Scoped state reads/writes per agent node
-   End-to-end pipeline: directive in → diffs + reports out

**Files to create**:
-   `src/orchestrator/graph.py`, `src/orchestrator/state.py`
-   `src/orchestrator/recovery.py`
-   `tests/test_orchestrator_e2e.py`

**Acceptance criteria**:
-   End-to-end: given a 5-file test repo + directive, pipeline produces valid diffs and reports
-   Recovery: a deliberately broken executor triggers retry, then skip, without crashing
-   State isolation: each agent only sees its scoped fields
-   Full abort triggers when test pass rate < 85%

---

## Cycle 7: CLI, PR Generator & Output Artifacts

**Complexity**: Standard\
**Depends on**: Cycle 6 (wraps the full pipeline)

**Goal**: Build the CLI interface and PR generation output.

**Deliverables**:
-   CLI via `click` or `typer`: `refactor-bot run --repo --directive --output`
-   PR Generator Agent: produces `pr-summary.md` with title, summary, change list, risk assessment, rollback instructions
-   Output directory structure: `diffs/`, `pr-summary.md`, `validation-report.json`, `agent-log.json`
-   `--dry-run`, `--include`, `--exclude`, `--verbose`, `--max-retries` flags

**Files to create**:
-   `src/cli/main.py`, `src/agents/pr_generator.py`
-   `src/utils/output_writer.py`
-   `tests/test_cli.py`, `tests/test_pr_generator.py`

**Acceptance criteria**:
-   `refactor-bot run --repo ./fixtures --directive "..." --output ./out` completes and populates all output artifacts
-   `--dry-run` produces diffs without applying them
-   PR summary includes all required sections
-   `--verbose` produces `agent-log.json` with full state transitions

------------------------------------------------------------------------

# 9. Evaluation Metrics

## Structural Integrity

| Metric | Target |
|--------|--------|
| Test pass rate post-refactor | >= 95% |
| Unresolved imports | 0 |
| Orphaned functions | 0 |

## Agent Coordination

| Metric | Target |
|--------|--------|
| Redundant edits (same line edited by multiple tasks) | 0 |
| Contradictory changes | 0 |
| Planner loop cycles | 0 (max 3 retries per task) |

## Semantic Coherence

| Metric | Target |
|--------|--------|
| Behavioral equivalence (test output match) | 100% for unchanged tests |
| Abstraction layer consistency | No cross-layer imports introduced |

## Efficiency Metrics

| Metric | Target |
|--------|--------|
| Token consumption per file | < 8,000 tokens average |
| Retrieval precision (relevant files / retrieved files) | >= 0.8 |
| Agent iteration count per task | <= 3 |
| Total pipeline runtime (20-file repo) | < 5 minutes |

------------------------------------------------------------------------

# 10. Constraints

-   MVP: Maximum 20 files; post-MVP: up to 50 files\
-   Requires Anthropic API key and OpenAI API key (for embeddings)\
-   Operates on local repository (cloned to a working directory)\
-   All agent tool calls use validated Pydantic schemas

------------------------------------------------------------------------

# 11. User Interface and Input Format

The system is invoked via CLI. The user provides:

``` bash
refactor-bot run \
  --repo ./path/to/repo \
  --directive "Convert all synchronous file operations to async" \
  --output ./output
```

### Required Inputs

| Parameter | Description |
|-----------|-------------|
| `--repo` | Path to the local repository to refactor |
| `--directive` | Natural language refactor instruction |
| `--output` | Directory for generated diffs, PR summary, and reports |

### Optional Inputs

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--include` | `**/*.ts,**/*.js` | Glob patterns for files to include |
| `--exclude` | `node_modules,dist` | Glob patterns for files to exclude |
| `--dry-run` | `false` | Generate diffs without applying them |
| `--max-retries` | `3` | Max retry attempts per task |
| `--verbose` | `false` | Enable detailed agent logging |

### Output Artifacts

The `--output` directory will contain:

-   `diffs/` — One `.patch` file per modified source file\
-   `pr-summary.md` — PR title, summary, change list, risk assessment, rollback instructions\
-   `validation-report.json` — Test results, consistency audit, confidence scores\
-   `agent-log.json` — Full trace of agent actions and state transitions

------------------------------------------------------------------------

# 12. Failure Conditions

System is unstable if:

-   Agents enter retry loops\
-   Planner contradicts execution agent\
-   Refactor breaks more than 10% of tests\
-   Embedding retrieval pulls unrelated modules\
-   Hallucinates file paths

------------------------------------------------------------------------

# 13. MVP Scope

-   JavaScript / TypeScript / React (JSX/TSX) only\
-   Single refactor directive\
-   Maximum 20 files\
-   Mock test validation\
-   Git diff generation only\
-   React Rule Engine: CRITICAL and HIGH priority rules (categories 1-3) enabled\
-   Auto-detect React/Next.js projects and activate rule engine accordingly

------------------------------------------------------------------------

# 14. Stretch Goals

-   Cross-language support\
-   Real test execution in Docker sandbox\
-   Reinforcement scoring\
-   Diff confidence ranking\
-   Human-in-the-loop approval gate\
-   Full React Rule Engine (all 57 rules across 8 categories, including MEDIUM and LOW priority)\
-   Custom rule authoring — allow users to define project-specific React patterns\
-   Lighthouse / bundle analyzer integration to measure before/after impact of React optimizations

------------------------------------------------------------------------

# 15. Definition of Done

System successfully:

-   Refactors multi-file project\
-   Maintains structural correctness\
-   Generates coherent pull request\
-   Passes simulated tests\
-   Does not loop or contradict itself

------------------------------------------------------------------------

# 16. Workflow Execution Notes

This PRD is designed for implementation via `/agent-team-dev-workflow`. The following notes guide the workflow coordinator and agents.

## Cycle Dependency Chain

```
Cycle 1 (Scaffold + Indexer)
  └→ Cycle 2 (Embeddings + ChromaDB)
       └→ Cycle 3 (Planner + Task Decomposition)
            └→ Cycle 4 (Refactor Executor + Diffs)
                 └→ Cycle 5 (Auditor + Test Validator)
                      └→ Cycle 6 (Orchestrator + State Machine)
                           └→ Cycle 7 (CLI + PR Generator)
```

Each cycle is a single workflow invocation. The continuation contract in each cycle's deliverables defines the interface the next cycle inherits.

## Workflow Phase Mapping per Cycle

| Workflow Phase | What it does for this project |
|----------------|-------------------------------|
| **Discover** | Read this PRD (Section 8 for the current cycle), scan existing `src/` for prior cycle outputs, check `LEARNINGS.md` for pitfalls from earlier cycles |
| **Plan** | Produce implementation plan from the cycle's deliverables, files, and acceptance criteria listed above |
| **Work** | Engineer builds modules; test-writer writes tests per the cycle's acceptance criteria |
| **Test** | Run `pytest` on new + existing tests; verify acceptance criteria |
| **Review** | Security reviewer checks API key handling, architecture reviewer checks module boundaries, code quality reviewer checks patterns |
| **Compound** | Capture learnings into `knowledge/category/agents.md`, `knowledge/category/rag.md`, etc. |

## Knowledge Categories to Bootstrap

When running bootstrap for this project, create these category files:

-   `knowledge/category/ast-parsing.md` — tree-sitter patterns, symbol extraction edge cases
-   `knowledge/category/rag.md` — embedding strategies, retrieval precision findings
-   `knowledge/category/agents.md` — LLM agent patterns, prompt structures, tool-use schemas
-   `knowledge/category/react-rules.md` — React best practices rule engine integration findings
-   `knowledge/category/orchestration.md` — LangGraph state machine, recovery logic patterns
-   `knowledge/category/cli.md` — CLI conventions, output formatting

## Review Focus Areas per Cycle

| Cycle | Security Focus | Architecture Focus | Code Quality Focus |
|-------|---------------|-------------------|-------------------|
| 1 | File path traversal in indexer | Module boundary: `models/` vs `agents/` | Pydantic model design |
| 2 | API key handling for OpenAI | ChromaDB persistence strategy | Embedding batch size / error handling |
| 3 | Prompt injection in directives | Planner ↔ retriever interface | Task dependency validation |
| 4 | LLM output sanitization in diffs | Diff format compatibility | Convention preservation accuracy |
| 5 | Test execution sandboxing | Auditor ↔ validator separation | False positive rate in auditor |
| 6 | State isolation between agents | Graph topology correctness | Recovery logic edge cases |
| 7 | CLI input sanitization | Output artifact completeness | Error messaging UX |

## Complexity Estimates

| Cycle | Complexity | Planner Model | Notes |
|-------|-----------|---------------|-------|
| 1 | Standard | Opus 4.6 | Foundational — models and parsing |
| 2 | Standard | Opus 4.6 | External API integration (OpenAI) |
| 3 | Standard | Opus 4.6 | LLM integration (Claude API) |
| 4 | Complex | Opus 4.6 | Core value — diff generation quality is critical |
| 5 | Standard | Opus 4.6 | Validation logic |
| 6 | Complex | Opus 4.6 | Integration of all prior cycles |
| 7 | Standard | Opus 4.6 | CLI wrapper + output formatting |

------------------------------------------------------------------------

End of Document
