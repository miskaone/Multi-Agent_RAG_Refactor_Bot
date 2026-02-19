# Post-Release Risks and Follow-ups (Skills v0.2.0+)

## Status: Post-rollout, monitored

## Open Risks

1. **Rule completeness vs source drift (Medium)**
   - The parser is resilient to markdown variation, but Vercel skill content can shift over time.
   - Follow-up: add a lightweight golden fixture hash test and update cadence for rule source updates.

2. **Fallback rule patterns (Low)**
   - Some generated rules may still be based on compatibility fallback metadata when the markdown source format is nonstandard.
   - Follow-up: expand `SKILL.md` parser fixtures by section/profile combinations from canonical source.

3. **Execution trust signaling (Low)**
   - `low_trust_pass` behavior is useful but still operator-dependent in no-runner mode.
   - Follow-up: document threshold exceptions and approval criteria in runbooks.

4. **Placeholder text residue in docs (Low)**
   - A few repository docs still contain generic planning checklists that include placeholder terms.
   - Follow-up: one-time cleanup pass before tagged release notes publication.

5. **Provider key management UX (Medium)**
   - Multiple providers can be configured; accidental mixups remain possible.
   - Follow-up: validate key-selection precedence and add explicit CLI help examples for Anthropic/OpenAI priority modes.

## Non-blocking cleanup tasks

- Review and close loop on `docs/DECISIONS.md` placeholders.
- Add a dedicated Skills release checklist artifact (`docs/`).
- Add CI guard rails for placeholder strings in user-facing skill docs.

