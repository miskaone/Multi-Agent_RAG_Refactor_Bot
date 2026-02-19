# Application Design & Specification (Developer Review)

## Scope

- Repository: `Multi-Agent_RAG_Refactor_Bot`
- Version reviewed: `v0.2.0+` (Skills architecture closeout completed and merged)
- Focus: current Python implementation (CLI + LangGraph orchestrator + 6-agent pipeline + JS/TS-specific tooling).
- Output requested: design + specification ready for engineering review.

## Purpose

- Enable safe, multi-file refactors for JavaScript/TypeScript codebases using a staged pipeline.
- Balance autonomy and safety via structured orchestration, semantic retrieval, static auditing, and automated validation.
- Preserve repository integrity unless post-task quality gates pass.

## Non-Goals

- Automatic deployment or runtime CI/CD integration.
- Automatic PR or artifact generation (not implemented in code despite PRD references to an explicit PR generator output).
- Cross-language codebase refactoring outside JS/TS/TSX/JSX.
- GitHub/GitLab diff comment publishing.

## Architecture Overview

- Presentation layer: `src/refactor_bot/cli/main.py`
- Orchestration layer: `src/refactor_bot/orchestrator/`
- Agent layer: `src/refactor_bot/agents/`
- Retrieval layer: `src/refactor_bot/rag/`
- Domain model layer: `src/refactor_bot/models/`
- Utility layer: `src/refactor_bot/utils/`
- Rules layer: `src/refactor_bot/rules/`
- Skills layer: `src/refactor_bot/skills/`

```text
CLI -> Orchestrator Graph -> Agents -> Reports/Exit
      -> Repo Indexer / Retriever / Planner / Executor / Auditor / Validator
```

## Update: Skills Architecture Rollout Status (Feb 2026)

- Skills framework is production-complete for v0.2.0+.
- Merged completion chain includes:
  - #1 Core skill models/registry/docs baseline
  - #2 CLI/planner/executor/auditor/graph wiring
  - #4 no-runner safety policy controls
  - #5 provider-selection regression coverage
  - #16 parser + initial skill integration scaffolding
  - #21 parser hardening for Vercel rule markdown
  - #22 canonical Vercel skill docs loaded in repository
  - #24 integration + activation tests and mixed-topology behavior
  - #27 downstream model compatibility aliases
  - #28 docs closeout + release notes
- Open issues and open PRs are currently clean; there are no remaining unresolved rollout tickets.
- Control/smoke check support exists via:
  - `test-repo1/scripts/check-control-repo.sh`
  - `test-repo1/EXPECTED_RESULTS.md`
- Validation command used for closure:
  - `uv run pytest tests/test_cli.py tests/test_planner.py tests/test_refactor_executor.py tests/test_skills.py`
  - observed result: **88 passed, 0 failed**.

## Runtime Pipeline

- CLI validates arguments and environment prerequisites.
- Pipeline starts in `START`.
- `index_node`: index repository and update vector store.
- `plan_node`: generate DAG tasks from user directive.
- `execute_node`: choose next runnable task and generate diffs.
- `audit_node`: run AST + semantic checks over diffs.
- `validate_node`: run tests or static fallback.
- `decide_fn` routes to:
  - `apply_node` on pass.
  - `retry_node` if budget remains.
  - `abort_node` on repeated failures or test pass-rate failure.
- End state returns cumulative state object with results.

## Orchestration Specification

- Graph builder: `build_graph(...)` in `src/refactor_bot/orchestrator/graph.py`.
- State schema: `RefactorState` in `src/refactor_bot/orchestrator/state.py`.
- Recovery helpers: `find_task_index`, `get_next_pending_task`, `compute_test_pass_rate`, `next_task_or_end` in `src/refactor_bot/orchestrator/recovery.py`.
- Deterministic retry budget:
  - User input `max_retries`.
  - Clamped to `[1, 10]` by `make_initial_state`.
  - Compare attempt count in `retry_counts` per `task_id`.
- Abort criterion:
  - `compute_test_pass_rate < 0.85` in `decide_fn` or retry budget exhaustion.
- Routing defaults:
  - Task execution continues while any DAG-ready `PENDING` task remains (`next_task_or_end`).
- `abort` appends an `ABORT:` message into `errors`.
- For no runner available and `--allow-no-runner-pass` mode:
  - pipeline emits `TestReport.low_trust_pass=True` when LLM fallback is used.

## State Contract

- Mandatory input fields:
  - `directive`
  - `repo_path`
  - `max_retries`
- Mutable runtime state:
  - `repo_index`
  - `embedding_stats`
  - `is_react_project`
  - `context_bundles`
  - `task_tree`
  - `active_rules`
  - `current_task_index`
  - `diffs`
  - `audit_results`
  - `test_results`
  - `retry_counts`
  - `errors`
- `diffs` and `errors` are reducer fields (`operator.add`) so values accumulate across nodes.

## Component Specs

### CLI (`src/refactor_bot/cli/main.py`)

- Required flags:
  - `directive`
  - `repo_path`
- Optional flags:
  - `--max-retries` (`int`, default `3`)
  - `--timeout` (seconds, default `120`)
  - `--vector-store-dir` (`./data/embeddings`)
  - `--model` (`claude-sonnet-4-5-20250929`)
  - `--dry-run`
  - `--output-json`
  - `--verbose`
- Exit code mapping:
  - `0` success
  - `1` invalid input
  - `2` agent error
  - `3` orchestrator build/invoke error
  - `4` abort condition
  - `5` unexpected runtime error
  - `130` keyboard interrupt
- Lazy imports are used to keep startup lightweight for help/dry-run.

### Repo Indexer (`src/refactor_bot/agents/repo_indexer.py`)

- Inputs:
  - `repo_path`
- Outputs:
  - `RepoIndex` with file info, symbol metadata, dependency graph, React detection.
- Discovery:
  - Recursively include `.js`, `.ts`, `.tsx`, `.jsx`.
  - Skip symlinks, node_modules, dist, .git, and `__pycache__`.
- React detection:
  - Inspect `package.json` `dependencies` and `devDependencies` for `react` or `next`.
- Dependency resolution:
  - Relative import resolution uses common extensions plus index-file fallback.

### Planner (`src/refactor_bot/agents/planner.py`)

- Inputs:
  - `directive`, `repo_index`, `context`
- Outputs:
  - `list[TaskNode]`
- Responsibilities:
  - Validate directive for length and injection-like patterns.
  - Generate tool-use prompt and parse typed task output.
  - Validate file paths against indexed paths.
  - Validate dependency graph integrity and acyclicity.
- Task semantics:
  - `TaskNode` has `status`, `dependencies`, and `confidence_score`.
  - Planner propagates applicable rule ids from rule engine.

### Refactor Executor (`src/refactor_bot/agents/refactor_executor.py`)

- Inputs:
  - `TaskNode`, `RepoIndex`, RAG `context`
- Outputs:
  - `list[FileDiff]`
- Responsibilities:
  - Read source for allowed files.
- Detect style from first source file.
- Build Claude prompt with context and rules.
- Parse tool output with `generate_refactored_code`.
- Validate each diff with git apply check.
- Diff objects include `is_valid` and optional `validation_error`.

### Consistency Auditor (`src/refactor_bot/agents/consistency_auditor.py`)

- Inputs:
  - `diffs`, `repo_index`
- Outputs:
  - `AuditReport`
- Checks implemented:
  - Orphaned imports by AST symbol usage.
  - Signature mismatch risk (export removal and parameter count change heuristic).
  - Dependency integrity for imports in modified files.
  - React anti-pattern scanning based on rule signal strings when React project.
- Severity model:
  - `ERROR`, `WARNING`, `INFO`.

### Test Validator (`src/refactor_bot/agents/test_validator.py`)

- Inputs:
  - `repo_path`, `diffs`
- Outputs:
  - `TestReport`
- Behavior:
  - Detect runner from `package.json` (`vitest` or fallback `npm test`).
- If runner exists:
  - Run baseline tests.
  - Apply diffs into temporary copy.
  - Re-run tests and compute breaking changes.
- If no runner:
  - Use LLM fallback when Anthropic key available; otherwise mark runner unavailable.

### RAG (`src/refactor_bot/rag/`)

- `EmbeddingService` (`src/refactor_bot/rag/embeddings.py`)
  - Uses OpenAI `text-embedding-3-small`.
  - Batches + retry with exponential backoff for transient failures.
- `VectorStore` (`src/refactor_bot/rag/vector_store.py`)
  - ChromaDB persistent client.
  - Upsert/delete/query/get by file/hash utilities.
- `Retriever` (`src/refactor_bot/rag/retriever.py`)
  - `query()` validates length/top_k/threshold.
  - `index_repo()` supports incremental update by file hash diff.

## Model Contracts

- `RepoIndex`: repository summary, symbol list, dependency graph.
- `EmbeddingRecord`: persistent embedding unit keyed by `{file_path}::{symbol_name}`.
- `TaskNode`: planned unit with `dependencies` and `status`.
- `FileDiff`: unified diff payload plus `is_valid`/`validation_error`.
- `AuditReport`: findings and counts (`passed`, `error_count`).
- `TestReport`: `pre_run`, `post_run`, `breaking_changes`, `runner_available`.

## External Dependencies

- Python 3.12+.
- Anthropic Python SDK.
- OpenAI Python SDK.
- LangGraph.
- tree-sitter (+ JS/TS grammars).
- ChromaDB.
- Pytest + Ruff + Mypy in dev configuration.

## Security & Compliance Notes

- Secret handling:
  - No API keys on CLI args in this code path.
  - Secrets sourced from environment only in agent constructors.
- Path handling:
  - Repository traversal checks in indexer and diff validation apply.
  - Temporary execution path checks in test validator prevent outside-tree writes.
- Injection handling:
  - Directive blocked for known prompt-injection patterns.
  - Prompt text warns model not to obey in-band source instructions.

## API/CLI Interface Contracts

- Public CLI function:
  - `main(argv=None) -> int`
- Graph builder:
  - `build_graph(indexer, retriever, planner, executor, auditor, validator)`
- Deterministic initial state:
  - `make_initial_state(directive, repo_path, max_retries)`
- Recovery helpers:
  - `next_task_or_end`
  - `compute_test_pass_rate`

## Reviewed Gaps vs PRD/Docs

- PRD claims full PR output and artifact generation features (title, summary, risk, rollback files), but current code contains no PR generator.
- PRD references up to 57 rules across all React categories; implementation includes the first set in `react_rules.py` and a smaller selection (`CRITICAL` + `HIGH` coverage behavior through `select_applicable_rules`).
- PRD claims "skip/retry/abort" branching, while graph currently includes retry and abort, but no active skip-edge in the built graph.
- Abort threshold is `0.85` in code and docs state mixed target thresholds (`85%`, `95%` in different sections).

## Dev Review Findings

## Critical

- `src/refactor_bot/orchestrator/graph.py`: `skip_node` remains defined but not wired into the built graph. PRD-style skip semantics are documented but not implemented as runtime edge behavior.

## Warning

- `src/refactor_bot/agents/test_validator.py`: In no-runner mode with LLM fallback, `low_trust_pass` is intentionally allowed only via explicit approval path. Operations should treat this as non-standard trust posture.
- `src/refactor_bot/rag/retriever.py`: similarity threshold defaults to `0.7`; low-confidence retrieval can still influence planning and execution if malformed retrieval returns empty or noisy results.
- `src/refactor_bot/utils/diff_generator.py`: git validation paths silently skip unsafe relative entries rather than failing hard, which can hide malformed diff-file mapping.
- `src/refactor_bot/agents/consistency_auditor.py`: anti-pattern and dependency checks are heavily string/rule heuristic based, increasing false positives/negatives under minified or non-standard syntax.

## Final Readiness Summary (for reviewer sign-off)

- Architecture: `READY` with one known non-blocking behavior gap (`skip_node` path).
- Skill system: `READY` with parser-backed rules, canonical Vercel context, activation controls, and compatibility aliases.
- Regression confidence: `PASS` with the documented closure command and all known rollout checks passing.
- Security posture: `MODERATE` due to no-runner fallback requiring explicit operator approval flag.

## Suggestion

- `src/refactor_bot/orchestrator/state.py`: `is_react_project` is set during graph build by index node but not part of a validated optional contract in every error path.
- `src/refactor_bot/rag/vector_store.py`: path traversal check rejects `".."` components, but normalization edge cases can still bypass in unusual Unicode/OS-specific path encoding paths.
- `docs/Multi-Agent_RAG_Refactor_Bot_PRD.md`: several sections are now out of date; consider adding a "current-implementation" contract table.

## Acceptance Criteria for the Current Revision

- CLI executes end-to-end on a valid JS/TS repo with both API keys present.
- Planner returns at least one valid task for a non-trivial directive and all task files resolve in index.
- Executor returns `FileDiff` objects with parseable `diff_text`.
- Auditor returns `AuditReport`; `ValidationError` and invalid diffs remain surfaced in report and do not silently pass unknown checks.
- Validator returns deterministic `TestReport` and abort path is exercised with low pass-rate conditions.
- All errors are added to `errors` and reflected in final exit code.
- Recovery budget and abort behavior are deterministic and tested with mocked failures.

## Open Items for Implementation Alignment

- Decide on one canonical behavior for "no test runner" mode.
- Decide whether skip recovery should be fully implemented or removed from docs and helper functions.
- Decide whether low-trust test-fallback results may mark a pipeline pass.
- Expand docs and code comments to remove stale architecture artifacts (PRD claims vs implemented state).
- Add explicit contract tests for `RefactorState` transitions across error branches.

## Remediation Backlog (Dev Execution Plan)

### Priority P0 — Recovery Control Plane Alignment

- `src/refactor_bot/orchestrator/graph.py`
- Owner: Orchestrator maintainer
- Remediation:
  - Decide desired behavior for skip path and implement it end-to-end.
  - Either:
    - wire `skip_node` into a conditional route from `validate_node`/`make_decide_fn`, or
    - remove skip references from docs and code if unsupported.
- Acceptance criteria:
  - If skip is supported, there is an executable graph path to `skip_node` with deterministic criteria.
  - If skip is not supported, `skip_node` and related docs are removed/renamed to avoid dead code.
- Test updates:
  - Add `tests/test_orchestrator_recovery.py` case asserting the graph includes configured skip transition.
  - Add a failure-path integration test that exercises non-recoverable task behavior and verifies route decision.

### Priority P0 — Validation Safety Before Success

- `src/refactor_bot/agents/test_validator.py`
- Owner: Test validation owner
- Remediation:
  - Define and enforce explicit policy for no-runner mode.
  - In no-runner mode, do not return `passed=True` without explicit quality evidence unless intentionally configured.
  - Add policy toggle/flag so behavior is explicit (`allow_no_runner_pass` default false in MVP).
- Acceptance criteria:
  - No-runner path defaults to conservative failure when no static evidence exists.
  - Orchestrator decision logic reflects conservative status (`ABORT` or manual-review path).
- Test updates:
  - Add unit test for `validate(...` with no runner + no Anthropic key returning explicit non-pass.
  - Add unit test for no runner + key present and policy toggle behavior.

### Priority P1 — Documentation/Implementation Contract Stabilization

- `docs/Multi-Agent_RAG_Refactor_Bot_PRD.md`
- `docs/Application_Design_and_Specification_for_Dev_Review.md`
- Owner: Product + technical documentation owner
- Remediation:
  - Add an implementation-compatibility matrix (Planned vs Implemented).
  - Correct threshold language to the actual runtime `0.85` abort threshold.
- Acceptance criteria:
  - PRD references match implemented features for this release (no PR generator, partial rollback, skip semantics, rule coverage).
  - A reader can derive exact runtime behavior from one section without ambiguity.
- Test updates:
  - Add a docs review checklist to CI or PR template for contract drift.

### Priority P1 — Error Path Observability

- `src/refactor_bot/cli/main.py`
- `src/refactor_bot/orchestrator/graph.py`
- Owner: Reliability owner
- Remediation:
  - Ensure all graph error branches append machine-readable diagnostics.
- Acceptance criteria:
  - Every non-success branch contributes a stable error object or string with task context and decision reason.
- Test updates:
  - Add tests to confirm abort and non-pass branches produce deterministic `errors` entries and exit codes.

### Priority P2 — Diff and Audit Determinism

- `src/refactor_bot/utils/diff_generator.py`
- `src/refactor_bot/agents/consistency_auditor.py`
- Owner: Quality owner
- Remediation:
  - Convert silent skip behavior on unsafe diff paths into explicit validation errors where safe.
  - Make anti-pattern checks rule-driven and configurable to reduce false positives.
- Acceptance criteria:
 - Unsafe paths are rejected early with traceable validation message.
 - Auditor configuration supports explicit rule sets in tests.
- Test updates:
  - Add regression tests for unsafe relative path diff inputs.
  - Add targeted anti-pattern fixture tests with clear expected/disabled rule outcomes.
