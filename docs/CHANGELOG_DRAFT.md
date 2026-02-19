# Changelog (Draft)

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
