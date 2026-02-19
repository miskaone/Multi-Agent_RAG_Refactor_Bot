# Release Notes — Skills Architecture Delivery

## 2026-02-18 (Merged PR Batch + in-flight follow-up)

### Added
- Core Skills platform: `Skill` protocol, registry, manager, and model support.
- New first-party skill package: `vercel_react_best_practices` with metadata, `skill.py`, `SKILL.md`, and `AGENTS.md`.
- Pipeline context injection: Planner, Executor, and Consistency Auditor now consume active skill context and rules.
- CLI controls for skill selection (`--skills`) and no-runner safety policy (`--allow-no-runner-pass`).
- Test reporting enhancement: `TestReport.low_trust_pass` to indicate LLM fallback acceptance.

### Changed
- Merged PRs in sequence:
  - #1 `feat(skills): add Skills core models, registry, and docs baseline`
  - #2 `feat(skills): wire skill activation into CLI, planner, executor, auditor, and graph`
  - #3 `feat(testing): add allow-no-runner-pass path with low_trust_pass semantics`
- Behavior changed so no-runner test paths are conservative by default and marked as low-trust when explicitly enabled.
- Docs set expanded with architecture and handoff records:
  - `docs/SKILLS_ARCHITECTURE.md`
  - `docs/DECISIONS.md`
  - `docs/Skills Architecture.md`
  - `docs/Application_Design_and_Specification_for_Dev_Review.md`
  - `docs/Developer Handoff Plan Closing All Gaps for Multi-Agent RAG Refactor Bot v0.1.1.md`

### Known Risks / Follow-ups
- Downstream policy for strict automation (`low_trust_pass`) still requires final rollout guidance.
- Rule mapping depends on stable SKILL quick-reference IDs and parser tolerance for future Vercel updates.

### Current Follow-up Status
- `src/refactor_bot/skills/vercel_react_best_practices/rules.py` is now parser-backed (no placeholder behavior).
- Vercel `SKILL.md` and `AGENTS.md` are sourced from the canonical documentation.
