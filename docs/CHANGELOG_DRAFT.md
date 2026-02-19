# Changelog (Draft)

## 2026-02-19 (v0.2.0 Released)

- Release finalized in `docs/RELEASE_NOTES_v0.2.0.md`.
- Core changes in this release:
  - Skills architecture rollout completion and parser-backed Vercel React best-practices integration.
  - Final compatibility safety and control-repo hardening.
  - Documentation updates for spec/readiness and provider/env behavior.

## 2026-02-19 (Skills rollout closeout)

- Added consolidated Skills release and risk artifacts:
  - `docs/SKILLS_ROLLOUT_RELEASE_NOTES_v0.2.0.md`
  - `docs/POST_RELEASE_RISKS_AND_FOLLOWUPS.md`
  - `docs/PR_BODY_SKILLS_ROLLOUT_FINAL.md`
- Marked full Skills rollout readiness as complete after merged PR sequence:
  - #1, #2, #4, #5, #16, #21, #22, #24, #27
- Closed all rollout and readiness issues (#6–#19 where applicable) after final verification.
- Added this changelog consolidation to support docs-first handoff.

## 2026-02-19

### Environment Security and Configuration

- Added `.env` loading to the CLI startup path using `python-dotenv`.
- Added `.env` and `.env.local` to `.gitignore`.
- Added environment file templates and handling guidance:
  - `.env.example` (tracked) for onboarding.
  - `.env` remains ignored and stores real secrets locally.
- Added `python-dotenv` to project dependencies.

### LLM Provider/Execution Improvements

- Documented and stabilized provider selection and fallback behavior in `docs/LLM_PROVIDER_OPTIONS.md`.
- Control-run validations now support a stricter mode for deterministic signal checks.

### Test Control Repo / Regression Safety

- Hardened `/Users/michaellydick/dev/test-repo1/scripts/check-control-repo.sh`:
  - supports `--strict` mode,
  - supports `--help`,
  - rejects unknown arguments.
- Updated `test-repo1/EXPECTED_RESULTS.md` with merge-readiness guidance recommending strict mode.
- Improved `.gitignore` to include additional transient and environment artifacts.

### Notes

- No secret keys are tracked in the repository.
- `.env` should only exist locally and remain uncommitted.
