# DECISIONS.md

**Project:** Multi-Agent RAG Refactor Bot  
**Version:** v0.1.1 (Closing All Gaps)  
**File created:** February 18, 2026  
**Last updated:** [YYYY-MM-DD]  
**Owner:** [Your Name / Developer]

This file records **binding architectural and implementation decisions** made before starting the gap-closing work.  
All changes in the `feature/close-all-gaps-v0.1.1` branch must align with the decisions recorded here.

---

## 1. Skip Behavior

**Decision required:** What to do with the currently unreachable `skip_node`?

**Options considered:**
- **A (Recommended):** Remove `skip_node` entirely (clean dead code, simplify graph)
- **B:** Wire `skip_node` into the graph with explicit conditional routing

**Chosen decision:** [A / B]  
**Rationale:**  
[Write 1–3 sentences why this was chosen]

**Implementation impact:**  
[Will be filled after implementation – e.g. “skip_node and all references deleted”]

---

## 2. No-Test-Runner Mode Policy

**Decision required:** How should the pipeline behave when no test runner (`vitest`, `npm test`, etc.) is detected?

**Options considered:**
- **A (Recommended – Conservative):** Default `passed=False` + `runner_available=False` → forces ABORT unless `--allow-no-runner-pass` flag is used
- **B:** Allow LLM fallback to return `passed=True` by default (riskier)

**Chosen decision:** [A / B]  
**Rationale:**  
[Write 1–3 sentences]

**Flag behavior (if A chosen):**
- `--allow-no-runner-pass` (default: false)
- When enabled + Anthropic key present → LLM fallback with `low_trust_pass=True` flag in `TestReport`

---

## 3. Partial Rollback Support

**Decision required:** Should we support partial/subtree rollback on failed tasks?

**Options considered:**
- **A (Recommended):** Remove all references to partial rollback (PRD, docs, helpers, comments)
- **B:** Implement simple subtree rollback inside `apply_node` / recovery helpers

**Chosen decision:** [A / B]  
**Rationale:**  
[Write 1–3 sentences]

---

## 4. Abort Threshold Lockdown

**Decision required:** Standardize the test pass-rate abort threshold

**Options considered:**
- Lock to exactly `0.85` (0.85) everywhere (matches current code)
- Keep flexibility / different values

**Chosen decision:**  
**Final value:** `0.85` (85%)  

**Files that must be updated:**  
- `orchestrator/graph.py` (or wherever `compute_test_pass_rate` is used)
- All documentation (PRD, design spec, README)

---

## 5. Additional Decisions (if any)

**Decision 5.1:** [Title]  
**Chosen:**  
**Rationale:**  

---

## Sign-off

I confirm that the decisions above are final and will be followed during implementation.

**Developer signature:** _______________________________  
**Date:** _______________________________

---

**Next step:** Commit this file **before** any code changes in the feature branch.

```bash
git add docs/DECISIONS.md
git commit -m "docs: record binding decisions for v0.1.1 gap closure"