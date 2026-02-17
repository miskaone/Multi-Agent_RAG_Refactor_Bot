# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-17

### Added

- **Models** (Cycle 1): Pydantic v2 domain models — `FileDiff`, `TaskNode`, `TaskStatus`, `AuditReport`, `TestReport`, `RepoIndex`, `RetrievalResult`, `RefactorRule`
- **AST Parser** (Cycle 2): Tree-sitter wrapper for JS/TS/TSX with import/export/symbol extraction and unified diff generator
- **RAG Pipeline** (Cycle 3): OpenAI embedding service, ChromaDB vector store with path validation, semantic code retriever with `index_repo` and `query`
- **Agents** (Cycle 4): Five agent implementations — `Planner` (Claude task decomposition), `RefactorExecutor` (Claude code generation), `ConsistencyAuditor` (AST structural validation), `TestValidator` (subprocess test runner), `RepoIndexer` (filesystem indexer)
- **Hardening** (Cycle 5): `type_identifier` AST support, rule-filtered anti-pattern checks, `symlinks=False` in temp dir copies, `TIMEOUT_EXIT_CODE` constant, renamed `ValidationError` to `TestValidationError`
- **Orchestrator** (Cycle 6): LangGraph `StateGraph` with `RefactorState` TypedDict, node factories with closure pattern, conditional routing (apply/retry/abort), DAG-aware task scheduling, recovery helpers
- **CLI** (Cycle 7): argparse-based entry point with dry-run mode, lazy imports, env-var-only API keys, JSON/human output, 6 exit codes, `_handle_error` DRY helper

### Security

- API keys accepted via environment variables only (not CLI arguments)
- `_SAFE_CONFIG_KEYS` allowlist prevents secret leakage in dry-run output
- Path validation with `Path.resolve()` for repo path
- `symlinks=False` in `shutil.copytree` prevents symlink escape
- Directive injection defense via substring + regex patterns in Planner

[0.1.0]: https://github.com/miskaone/Multi-Agent_RAG_Refactor_Bot/releases/tag/v0.1.0
