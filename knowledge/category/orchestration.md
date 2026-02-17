# Orchestration

Learnings related to LangGraph state machine, recovery logic, and agent coordination.

---

## L022: LangGraph Conditional Edge Map Keys Must Be Exact (2026-02-17)

**Context**: Cycle 6 — build_graph() wiring in `src/refactor_bot/orchestrator/graph.py`

**Finding**: The initial plan routed `validate_node` to four destinations: `apply`, `retry`, `skip`, and `abort`. But `make_decide_fn()` only ever returned three strings (`"apply"`, `"retry"`, `"abort"`). The `"skip"` key in the edge map was a dead edge — `skip_node` was registered in the graph but permanently unreachable. LangGraph does not raise an error for unused edge map keys; it silently compiles the graph with the dead node in place.

**Pattern to avoid**:
```python
# Dead edge: "skip" key added "for future use" but decide_fn never returns "skip"
graph.add_conditional_edges(
    "validate_node",
    _decide_fn,
    {"apply": "apply_node", "retry": "retry_node", "skip": "skip_node", "abort": "abort_node"},
)
```

**Correct pattern**:
```python
# Edge map exactly matches the router function's possible return values
graph.add_conditional_edges(
    "validate_node",
    _decide_fn,
    {"apply": "apply_node", "retry": "retry_node", "abort": "abort_node"},
)
```

**Checklist before wiring conditional edges**:
1. Enumerate every string the router function can return (trace all branches).
2. Verify each string has exactly one key in the edge map.
3. Verify each key in the edge map corresponds to a string the router can return.
4. If a node "might be needed later", do not add it to the map until the router actually routes to it.

**See also**: known-pitfalls.md P014, LEARNINGS.md L022

---

## L023: None Guards on Optional State Fields Accessed in Node Functions (2026-02-17)

**Context**: Cycle 6 — `retry_node` in `src/refactor_bot/orchestrator/graph.py`

**Finding**: `retry_node` reads `state["test_results"].post_run` to build feedback context for the next execution. `test_results` is typed `TestReport | None` and `post_run` is typed `TestRunResult | None`. The initial implementation accessed `post_run.passed` and `post_run.failed` without checking if `post_run is None`, relying on the invariant that `make_validate_node`'s synthetic fallback always populates `post_run`.

The reviewer (ARCH-C6-001) correctly flagged this as a Critical defect: the `TestReport` Pydantic model allows `post_run=None` (for the LLM-fallback path where no subprocess ran), and if `validate_node` uses LLM fallback, `retry_node` would raise `AttributeError: 'NoneType' object has no attribute 'passed'`.

**Fix applied**:
```python
# Before (fragile — relies on synthetic fallback invariant)
if state["test_results"] is not None:
    tests = state["test_results"]
    context_messages.append(f"failed={tests.post_run.failed}")  # AttributeError if post_run is None

# After (defensive — checks both levels)
if state["test_results"] is not None:
    tests = state["test_results"]
    pass_rate = compute_test_pass_rate(tests)
    if tests.post_run is not None:
        context_messages.append(f"failed={tests.post_run.failed}")
    else:
        context_messages.append(f"test_pass_rate={pass_rate:.2%}, no post_run data")
```

**General rule**: Any time a node accesses a nested optional field (`state["X"].y` where either X or y can be None), add an explicit None guard at each level. Do not rely on invariants about how prior nodes populated the state — future refactors may change those nodes.

**See also**: LEARNINGS.md L023

---

## L024: Closure-Based Factory Pattern for LangGraph Nodes (2026-02-17)

**Context**: Cycle 6 — `build_graph()` in `src/refactor_bot/orchestrator/graph.py`

**Finding**: Using factory functions that return closures (rather than directly importing agent singletons inside nodes) enables effortless mocking in tests. The pattern:

```python
# Factory returns a closure capturing the agent instance
def make_execute_node(executor: RefactorExecutor, retriever: Retriever):
    def execute_node(state: RefactorState) -> dict:
        diffs = executor.execute(task=task, ...)
        return {"diffs": diffs, ...}
    return execute_node

# In build_graph() — agents injected at graph construction time
def build_graph(indexer, retriever, planner, executor, auditor, validator):
    _execute_node = make_execute_node(executor, retriever)
    graph.add_node("execute_node", _execute_node)
    return graph.compile()

# In tests — trivial mocking
executor = MagicMock()
executor.execute.return_value = [diff]
graph = build_graph(indexer, retriever, planner, executor, auditor, validator)
result = graph.invoke(initial_state)
assert executor.execute.call_count == 1
```

Without this pattern, tests would need to patch module-level imports, which is brittle and often requires `unittest.mock.patch` with full dotted import paths. The closure factory approach is simpler and more resilient to module restructuring.

**Trade-off**: `build_graph()` accumulates many parameters (6 agents in Cycle 6). If agent count grows beyond ~8, consider grouping related agents into a config/dependency dataclass.

**See also**: LEARNINGS.md L024

---

## L025: Annotated Reducer Fields — Always Return Lists, Never None (2026-02-17)

**Context**: Cycle 6 — `execute_node` in `src/refactor_bot/orchestrator/graph.py`

**Finding**: State fields typed as `Annotated[list[X], operator.add]` use `operator.add(existing, new)` to accumulate values across nodes. If any node returns `None` for such a field, `operator.add([], None)` raises `TypeError: can only concatenate list (not "NoneType") to list`. LangGraph does not provide a helpful error message indicating which node returned None.

**Three places to guard**:
1. **Success path**: after calling the agent, before returning.
2. **Error path**: in the `except` block, return `"diffs": []` not `"diffs": None`.
3. **No-op early exit**: if a node has an early-return path (e.g., no pending task found), return `"diffs": []`.

```python
def execute_node(state: RefactorState) -> dict:
    task = get_next_pending_task(state["task_tree"])
    if task is None:
        # Early exit — must still return diffs as list
        return {"errors": ["no eligible task"], "diffs": []}

    try:
        diffs = executor.execute(task=task, ...)
        if diffs is None:   # Defensive: agent contract may be violated
            diffs = []
        return {"diffs": diffs, ...}
    except Exception as exc:
        # Error path — must return diffs as list
        return {"errors": [str(exc)], "diffs": [], ...}
```

**Applies to all `Annotated[list, operator.add]` fields**: in Cycle 6 these are `diffs` and `errors`.

**See also**: known-pitfalls.md P015, LEARNINGS.md L025

---

## L026: Lazy Imports in CLI Entry Points (2026-02-17)

**Context**: Cycle 7 — `src/refactor_bot/cli/main.py`

**Finding**: The CLI module imports heavy dependencies (anthropic, chromadb, tree-sitter, langgraph) only inside `create_agents()` and `main()`, not at module level. This means `--help` and `--dry-run` execute in milliseconds without loading the full dependency graph. Without lazy imports, even `refactor-bot --help` would take 2-3 seconds to load chromadb and tree-sitter.

**Pattern**:
```python
# At module level: only stdlib + lightweight project imports
import argparse
import json
import os
import sys
from refactor_bot.agents.exceptions import AgentError  # lightweight

def create_agents(config: dict):
    # Heavy imports deferred to actual usage
    from refactor_bot.rag.embeddings import EmbeddingService
    from refactor_bot.rag.vector_store import VectorStore
    from refactor_bot.agents.repo_indexer import RepoIndexer
    # ... etc
```

**Testing implication**: When mocking lazy-imported classes in tests, `@patch("refactor_bot.cli.main.ClassName")` fails because the name is never a module-level attribute. Patch at the source module instead: `@patch("refactor_bot.rag.embeddings.EmbeddingService")`. See L028, P016.

**See also**: LEARNINGS.md L026, known-pitfalls.md P016

---

## L027: CLI API Key Security — Env Vars Only (2026-02-17)

**Context**: Cycle 7 — SEC-C7-001 review finding

**Finding**: The initial CLI design accepted `--api-key` and `--openai-key` as command-line arguments. This is a security anti-pattern because:
1. Process arguments are visible to all users via `ps aux` on Unix systems
2. Shell history stores the full command line including secrets
3. CI/CD logs may capture command invocations

The reviewer (SEC-C7-001) flagged this as Critical. The fix removed all API key CLI arguments and reads keys exclusively from environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`).

**Additional safeguard**: A `_SAFE_CONFIG_KEYS` allowlist controls which configuration keys can appear in `--dry-run` and JSON output, preventing accidental secret leakage even if a key is added to the config dict internally.

**See also**: LEARNINGS.md L027
