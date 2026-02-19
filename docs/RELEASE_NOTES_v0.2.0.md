# Multi-Agent RAG Refactor Bot — v0.2.0 Release Notes

## Release Date
2026-02-19

## Summary
v0.2.0 completes the Skills architecture rollout and productionizes rule-backed, prompt-injected behavior for React/Next.js refactoring guidance.

## Key Release Items
- Core Skills architecture implemented and integrated into CLI, planner, executor, auditor, and orchestrator.
- Vercel React Best Practices skill added with canonical `SKILL.md` + `AGENTS.md` and parser-backed rule extraction (all 57 rules represented).
- Registry activation now supports auto/explicit skill selection and context-aware prompt injection.
- Compatibility aliases and safety hardening completed for downstream callers.
- Environment configuration improved through `.env` loading and expanded `.gitignore` for local secret safety.
- Control repository regression path finalized with strict-mode checks.
- Documentation and design artifacts updated for release readiness and review handoff.

## Validation
- Closed-loop validation command:
  - `uv run pytest tests/test_cli.py tests/test_planner.py tests/test_refactor_executor.py tests/test_skills.py`
- Recorded result: **88 passed, 0 failed**.
- Skills rollout issue set (#6–#19) closed after merged PR sequence.

## Known Risks / Follow-ups
- `skip_node` remains non-blocking because it is documented but not wired into runtime graph.
- No-runner mode uses explicit low-trust handling and remains operator-gated.
- Rule-driven audit behavior should still be monitored as the upstream Vercel source evolves.

## Migration Notes
- No API keys are tracked in repository history from this release.
- `.env` remains intentionally ignored and should be managed per environment.
- No breaking interface changes were introduced for existing CLI execution semantics, except added `--skills` flag.

