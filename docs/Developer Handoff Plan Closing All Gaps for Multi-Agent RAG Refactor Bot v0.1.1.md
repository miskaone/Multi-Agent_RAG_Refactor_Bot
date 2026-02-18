# Developer Handoff Plan: Closing All Gaps for Multi-Agent RAG Refactor Bot v0.1.1

**Prepared by:** Grok (project reviewer)  
**Date:** February 18, 2026  
**Target branch:** `main` → create `feature/close-all-gaps-v0.1.1`  
**Goal:** Close every Critical/Warning/Suggestion item, every Open Item, and the full Remediation Backlog from `Application_Design_and_Specification_for_Dev_Review.md` so the project reaches **safe end-to-end testing** (75-80% readiness) and **public beta release** (v0.1.1 with clear safety warnings).

## Success Definition
- All Acceptance Criteria in the design spec are met.
- Pipeline runs end-to-end on 2+ fixture repos without silent failures or permissive safety bypasses.
- Docs exactly match implemented behavior.
- Exit codes, error objects, and recovery paths are deterministic.

## Pre-Work Decisions (30–60 min – do these first)
Create a 1-page `docs/DECISIONS.md` and record:

1. **Skip behavior**  
   - Remove `skip_node` entirely (recommended for MVP – clean dead code)  
   OR  
   - Wire it with explicit criteria (e.g., audit passes but `--allow-skip` flag).

2. **No-test-runner mode**  
   - Default: conservative `passed=False` + `runner_available=False` (forces ABORT unless `--allow-no-runner-pass`).  
   - LLM fallback only enabled via the flag (and logged as “low-trust pass”).

3. **Partial rollback**  
   - Remove all references (PRD, comments, helpers) or implement simple subtree rollback in `apply_node`.

4. **Abort threshold**  
   - Lock to exactly `0.85` everywhere; update any 95% mentions.

Commit this file before starting code changes.

## Phase 1: P0 – Safety & Recovery (Must be done before any real testing)
**Estimated effort:** 1.5–2 days

### Task P0.1 – Recovery Control Plane Alignment
**Files:** `src/refactor_bot/orchestrator/graph.py`, `recovery.py`, `state.py`, `DECISIONS.md`  

**Steps:**
- Decide on skip (record in `DECISIONS.md`).
- If removing: delete `skip_node`, all references in `make_decide_fn`, `next_task_or_end`, and docs.
- If keeping: add conditional edge from `decide_fn` → `skip_node`.
- Add missing partial-rollback path or remove references.
- Update `build_graph` to include every node that exists.

**Acceptance Criteria:**
- Graph visualization (add temporary `graph.get_graph().draw_png()` helper) shows all intended paths.
- New test in `tests/test_orchestrator_recovery.py` asserts correct transitions for skip/remove case.
- No dead code warnings from ruff/mypy.

### Task P0.2 – Validation Safety Before Success
**Files:** `src/refactor_bot/agents/test_validator.py`, `cli/main.py`, `orchestrator/graph.py`

**Steps:**
- Add `--allow-no-runner-pass` flag (default=False).
- When no runner and flag=False → return `passed=False`.
- When flag=True and Anthropic key present → use LLM fallback but set `low_trust_pass=True` in report.
- Update `decide_fn` to ABORT on `low_trust_pass` unless explicitly allowed.
- Auto-detect cheap static fallback (`tsc --noEmit` or `eslint`) if present.

**Acceptance Criteria:**
- Unit tests cover all 4 combinations (runner/no-runner × flag on/off).
- Integration test forces no-runner + flag=False → exit code 4 (ABORT).

## Phase 2: P1 – Documentation & Observability (1–1.5 days)

### Task P1.1 – Implementation Contract Stabilization
**Files:** `docs/Multi-Agent_RAG_Refactor_Bot_PRD.md`, `Application_Design_and_Specification_for_Dev_Review.md`, `README.md`

**Steps:**
- Add “Implementation Status Matrix” table at top of both docs (columns: PRD Claim, Implemented, Status).
- Update all threshold references to 0.85.
- Remove mentions of PR generator, full 57-rule set, skip (if removed), full rollback.
- Add **Limitations** section to README: “Always commit before running; LLM refactors can introduce subtle bugs; backup recommended.”

**Acceptance Criteria:**
- A new reader can determine exact runtime behavior from README + one doc without ambiguity.

### Task P1.2 – Error Path Observability
**Files:** `src/refactor_bot/cli/main.py`, `orchestrator/graph.py`, `state.py`

**Steps:**
- Every non-success branch appends a dict to `errors` with keys: `task_id`, `stage`, `reason`, `timestamp`, `retry_count`.
- Update exit-code mapping to reflect new error objects.
- Print structured summary on `--output-json` and human-readable on normal run.

**Acceptance Criteria:**
- Abort, retry-exhaustion, and validation-failure paths all produce deterministic, machine-readable `errors` entries.

## Phase 3: P2 – Polish & Determinism (1 day)

### Task P2.1 – Diff & Audit Hardening
**Files:** `src/refactor_bot/utils/diff_generator.py`, `agents/consistency_auditor.py`

**Steps:**
- Convert silent unsafe-path skips → explicit `ValidationError` with full trace.
- Make every anti-pattern check driven by `rules/rule_engine.py` (add config toggle).
- Add regression tests with unsafe paths and minified syntax fixtures.

**Acceptance Criteria:**
- Unsafe diff paths now raise early with clear message.
- Auditor passes config-driven rule tests.

### Task P2.2 – Minor Contract & Suggestion Items
- `state.py`: make `is_react_project` part of validated optional contract.
- `rag/vector_store.py`: strengthen Unicode/path normalization.
- Update model name default to stable `claude-3-5-sonnet-20241022` (keep override).
- Add LICENSE (MIT).

### Task P2.3 – Contract Tests & Docs Cleanup
- Add `tests/test_state_contracts.py` exercising all error branches.
- Remove stale architecture artifacts from all docs.

## Testing & Validation Plan
1. **Unit** – run full suite after every P0/P1 task (`uv run pytest --cov`).
2. **Integration** – add 3 new fixture repos in `tests/fixtures/` (small React class-components, TS migration, no-test-runner).
3. **End-to-end smoke** – run CLI on each fixture with `--dry-run` then full run.
4. **Manual dogfood** – run on one of your own small JS/TS repos with backup.
5. **Coverage** – must stay ≥90%.

## Suggested Timeline (Solo Developer)
- **Day 1**: Decisions + P0.1 + P0.2
- **Day 2**: P1.1 + P1.2 + basic integration tests
- **Day 3**: P2 + full smoke tests + docs
- **Day 4 (buffer)**: Fix any test failures, bump version, create GitHub release

**Total estimated effort:** 4 developer-days (realistic 3–5 depending on decisions).

## Release Checklist (v0.1.1)
- [ ] All tasks above complete & merged
- [ ] Version bumped in `pyproject.toml` and `__init__.py`
- [ ] `uv sync && uv run pytest` passes 100%
- [ ] GitHub release with:
  - Clear safety warning in description
  - Limitations section copy
  - Example fixture repos linked
- [ ] Update badges in README if coverage changes

## Branch & PR Guidance
- Work in `feature/close-all-gaps-v0.1.1`
- One PR per Phase (or atomic commits with clear messages)
- PR template: include “Closes P0.1, P0.2…” and link to this plan.

---

**You now have everything needed to hand this off to any developer (or execute it yourself).**  
Once P0 is complete, you can immediately start safe testing on real repos.

If you need the `DECISIONS.md` template, any specific test code, or a PR diff review, just ask.