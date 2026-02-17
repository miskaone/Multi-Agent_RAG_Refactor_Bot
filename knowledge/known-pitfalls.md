# Known Pitfalls

Structured failure lessons from past cycles. Checked by the research-scout before every plan.

## Format

Each pitfall follows this structure:
- **Failure Point**: What went wrong
- **Flawed Reasoning**: Why the original approach seemed correct
- **Correct Approach**: What should be done instead
- **General Principle**: The transferable lesson

---

## Pitfall 001: tree-sitter-languages Package Incompatibility

**Cycle**: 1 (2026-02-16)

**Failure Point**: Used `tree-sitter-languages` package and `language.query()` API, which failed at runtime with tree-sitter 0.22+.

**Flawed Reasoning**: The package name suggests it's the official multi-language support package for tree-sitter. Documentation examples showed `language.query()` usage.

**Correct Approach**: Use individual language packages (`tree-sitter-javascript`, `tree-sitter-typescript`) and the `Query(language, query_string)` + `QueryCursor` API. Always verify package compatibility with current tree-sitter version.

**General Principle**: Ecosystem packages may lag behind core library updates. When using parser/AST libraries, verify compatibility between core and plugin packages before implementation.

---

## Pitfall 002: macOS Path Symlink Normalization

**Cycle**: 1 (2026-02-16)

**Failure Point**: Tests failed on macOS because `/var` is a symlink to `/private/var`, causing path equality checks to fail.

**Flawed Reasoning**: Assumed `Path` objects would handle symlink resolution automatically in comparisons.

**Correct Approach**: Always use `.resolve()` on `Path` objects before comparison: `Path(repo_path).resolve()`. This resolves all symlinks to their canonical paths.

**General Principle**: macOS has several system-level symlinks (`/var`, `/tmp`, `/etc`). Always normalize paths with `.resolve()` before comparison or storage.

---

## Pitfall 003: Symlink Security in File Discovery

**Cycle**: 1 (2026-02-16)

**Failure Point**: Initial `_discover_files()` implementation followed symlinks, creating a path traversal attack vector (SEC-001).

**Flawed Reasoning**: Wanted to support symlinked files within repositories, assumed validation would catch malicious paths.

**Correct Approach**: Skip symlinks entirely in file discovery: `if file_path.is_symlink(): continue`. If symlink support is needed, resolve symlink and validate that resolved path is still within repository boundary.

**General Principle**: File discovery operations that traverse user-controlled directories must never blindly follow symlinks. Symlinks can point outside the intended boundary, enabling path traversal attacks.

---

## Pitfall 004: Test-Implementation API Mismatch in Parallel Agent Work

**Cycle**: 2 (2026-02-16)

**Failure Point**: Engineer and test-writer worked in parallel on RAG components. Tests used different method names (`persist_directory`, `upsert_records`, `similarity_score`) than implementation (`persist_dir`, `embed_symbols` + `upsert`, `similarity`), causing 9 test failures.

**Flawed Reasoning**: Implementation plan described components and responsibilities but didn't specify exact method signatures. Assumed agents would naturally converge on the same API.

**Correct Approach**: When agents work in parallel on interfacing components, the plan MUST include explicit interface contracts:
- Method names and signatures
- Parameter names and types
- Return types
- Example usage

Create a "contracts" section in the plan that both agents reference.

**General Principle**: Parallel agent work creates risk of API divergence. Prevent this with explicit interface contracts in the plan. The more agents work independently, the more explicit the contracts must be.

---

## Pitfall 005: ChromaDB Metadata Type Limitations

**Cycle**: 2 (2026-02-16)

**Failure Point**: Stored `dependencies` and `imports` (lists) directly to ChromaDB metadata. ChromaDB silently JSON-serialized them on write, but retrieval returned JSON strings instead of lists. Code broke when trying to iterate over metadata.

**Flawed Reasoning**: Assumed ChromaDB would handle complex types like lists automatically, similar to other databases.

**Correct Approach**: ChromaDB metadata only supports primitives (str, int, float, bool). For complex types:
1. JSON-serialize before storage: `json.dumps(list_field)`
2. Add deserialization step in retrieval: `json.loads(metadata['field'])`
3. Document this requirement in docstrings

Always check vector database metadata type constraints before schema design.

**General Principle**: Vector databases have different type constraints than traditional databases. Always verify metadata type support before schema design, and add explicit serialization/deserialization for complex types.

---

## Pitfall 006: Barrel File Symbol Assumptions in Tests

**Cycle**: 2 (2026-02-16)

**Failure Point**: Test asserted all `.ts` files would have at least one symbol. Failed on `index.ts` (barrel file) which only re-exports symbols from other modules.

**Flawed Reasoning**: All source files contain code, so they must contain symbols (functions, classes, etc.).

**Correct Approach**: Barrel/index files are valid source files with no function/class symbols. When testing code indexing:
- Don't assert all source files have symbols
- Instead, assert specific files you control have expected symbols
- Or exclude barrel files from the assertion: `if file.name == 'index.ts': continue`

**General Principle**: In TypeScript/JavaScript ecosystems, barrel files (index.ts) are common patterns for re-exporting. They contain only import/export statements, no executable symbols. Tests must account for this valid pattern.

---

## Pitfall 007: Missing Deserialization in ChromaDB Retrieval

**Cycle**: 2 (2026-02-16)

**Failure Point**: Phase 4 reviewer found that `dependencies` and `imports` fields were serialized to JSON on write but never deserialized on read. Retrieval code returned raw JSON strings.

**Flawed Reasoning**: Focused on storage concerns during implementation, forgot about retrieval path.

**Correct Approach**: For every serialization step, immediately add the corresponding deserialization:
1. Add serialization in write path: `json.dumps(field)`
2. Add deserialization in read path: `json.loads(metadata['field'])`
3. Test round-trip: write then read and verify types match

Create a helper method (e.g., `_deserialize_metadata()`) to centralize this logic.

**General Principle**: Serialization and deserialization are paired operations. When adding serialization, immediately implement deserialization in the retrieval path. Test the full round-trip to catch type mismatches early.

---

## Pitfall 008: Bare Substring Matching for Prompt Injection

**Cycle**: 3 (2026-02-16)

**Failure Point**: Initial prompt injection validation used 5 basic substring patterns like "ignore previous" but failed to catch variations like "IGNORE PREVIOUS", "disregard previous", or model-specific patterns like `<|start`, `[INST]`, `<<SYS>>`.

**Flawed Reasoning**: Basic substring matching (e.g., checking for "inst") seems sufficient for catching injection attempts. Case-insensitive checks should handle most variations.

**Correct Approach**: Use defense-in-depth with multiple layers:
1. **Substring patterns** (17 patterns): Common phrases like "ignore previous", "system prompt", "you are now"
2. **Regex patterns** (7 patterns): Model-specific tokens like `<\|[a-z_]+`, `\[INST\]`, `<<SYS>>`, code fence system overrides
3. **Case-insensitive matching**: Apply `.lower()` to directive before checking
4. **Length limits**: Enforce max length (e.g., 2000 chars) to prevent flooding
5. **Avoid overly broad patterns**: Don't use bare "inst" which blocks legitimate words like "instructions"

**General Principle**: Prompt injection defense requires multiple validation layers. Attackers use case variations, synonym substitution, and model-specific control tokens. A single validation approach will have gaps. Always combine substring matching, regex patterns, and length limits.

---

## Pitfall 009: LLM-Generated Confidence Scores Outside Valid Range

**Cycle**: 3 (2026-02-16)

**Failure Point**: LLM-generated confidence scores can exceed [0.0, 1.0] range when LLM is asked to provide confidence estimates. Without validation, scores like 1.5 or -0.2 can pass through.

**Flawed Reasoning**: LLMs understand confidence scores are 0-1 from training data and will naturally output valid ranges.

**Correct Approach**: Always validate and clamp LLM-generated numeric values:
```python
if confidence_score is not None:
    confidence_score = max(0.0, min(1.0, confidence_score))
```

Add this validation in data ingestion/deserialization code, not just in the LLM prompt.

**General Principle**: Never trust LLM-generated numeric values to be within expected ranges. LLMs can hallucinate numbers outside valid bounds. Always add validation and clamping to enforce constraints.

---

## Pitfall 010: Path.resolve() on macOS Temp Directories Adds /private Prefix

**Cycle**: 4 (2026-02-16)

**Failure Point**: Path containment check using `str(path).startswith(str(base))` failed in `validate_diff_with_git()` because `tempfile.TemporaryDirectory()` returns `/var/folders/...`, but `Path(path).resolve()` expands it to `/private/var/folders/...` on macOS.

**Flawed Reasoning**: Adding `.resolve()` on both sides of a containment check should normalise paths consistently. The `.startswith()` approach seemed safe because both sides were resolved.

**Correct Approach**: Use `Path.is_relative_to()` instead of `str.startswith()` for path containment checks:
```python
# Wrong:
if not str(resolved_path).startswith(str(resolved_base)):
    raise ValueError(...)

# Correct:
if not resolved_path.is_relative_to(resolved_base):
    raise ValueError(...)
```
`is_relative_to()` compares path components, not string prefixes, so it is immune to `/private` symlink expansion asymmetry.

**General Principle**: macOS has multiple symlink aliases (`/tmp -> /private/tmp`, `/var -> /private/var`, `/etc -> /private/etc`). String-prefix containment checks break when one side is resolved and the other is not, or when resolution happens at different times. Always use `Path.is_relative_to()` for path boundary validation.

---

## Pitfall 011: Review Agent False Positives on Import Usage

**Cycle**: 4 (2026-02-16)

**Failure Point**: Code reviewer (CQ-C4-021) flagged an import as unused. The import was actually used in a test assertion on a different line that the reviewer did not trace to. Fixing the "finding" would have broken tests.

**Flawed Reasoning**: Static import analysis is reliable; if an identifier appears only in the import line, it must be unused.

**Correct Approach**: Before applying any "unused import" fix from a reviewer, verify with grep/static analysis that the identifier truly has zero non-import occurrences:
```bash
grep -n "SymbolName" file.py
```
If the identifier appears in assertions, decorators, or type annotations on other lines, the import is used and the finding is a false positive.

**General Principle**: Automated and LLM-based reviewers produce false positives at approximately 5% rate. Treat all "unused import" findings as hypotheses to verify, not facts to act on. Never remove an import before confirming it is absent from all non-import uses.

---

## Pitfall 012: shutil.copytree Copies Symlinks by Default

**Cycle**: 5 (2026-02-17)

**Failure Point**: `shutil.copytree(src, dst)` defaults to `symlinks=False`, which means it follows symlinks and copies the **contents** of the target. If the source repository contains a symlink pointing outside the repo boundary (e.g., `ln -s /etc/passwd sensitive`), the copy operation will read and copy the sensitive file into the temp directory, and the subsequent write-back of `modified_content` could overwrite it.

**Flawed Reasoning**: The temp dir operation already validates `file_path` with `is_relative_to()` before writing, so symlinks in the copied tree are not a concern.

**Correct Approach**: Always pass `symlinks=False` (the default) when using `shutil.copytree` for security-sensitive temp dir operations. Additionally, when the intent is to NOT follow symlinks (preserve the symlink as a symlink), pass `symlinks=True`. Review the exact semantics before use:
```python
# Safe: copies symlinks as symlinks, does NOT follow them into sensitive targets
shutil.copytree(repo_path, tmpdir, symlinks=False, dirs_exist_ok=True)
```

**General Principle**: `shutil.copytree` symlink behavior is a security-relevant decision. Always explicitly state your intent with `symlinks=True` or `symlinks=False` rather than relying on the default. In temp dir sandboxing scenarios, use `symlinks=False` to prevent symlink escape.

---

## Pitfall 014: LangGraph Dead Edges (Unreachable Nodes via Missing Edge Map Keys)

**Cycle**: 6 (2026-02-17)

**Failure Point**: The initial `build_graph()` wiring included `"skip": "skip_node"` in the `validate_node` conditional edge map, but `make_decide_fn()` never returned `"skip"` (its logic routed failures to `"retry"` or `"abort"` only). `skip_node` was registered but permanently unreachable. Separately, the plan docstring listed `skip_node` in the edge topology despite it never being reachable from `validate_node`.

**Flawed Reasoning**: Including a key in the edge map seemed harmless — LangGraph would just never route there. The node existed for future use.

**Correct Approach**: Conditional edge maps must be a closed set matching the exact strings the router function can return. Any key in the map that cannot be returned is a dead edge. Remove the node, the registration, and the edge map key together:
```python
# Wrong: "skip" key but decide_fn never returns "skip"
graph.add_conditional_edges(
    "validate_node",
    _decide_fn,
    {"apply": "apply_node", "retry": "retry_node", "skip": "skip_node", "abort": "abort_node"},
)

# Correct: map exactly matches possible return values
graph.add_conditional_edges(
    "validate_node",
    _decide_fn,
    {"apply": "apply_node", "retry": "retry_node", "abort": "abort_node"},
)
```
Keep `skip_node` only if there is a reachable path that returns `"skip"`.

**General Principle**: Treat LangGraph's conditional edge map as a contract between the router function's return values and the graph's nodes. Before committing, enumerate every string the router can return and verify each has a corresponding key. Dead keys are not silent no-ops — they indicate a logic gap (either the router is missing a case or the node is dead code).

---

## Pitfall 015: Annotated Reducer Fields Require Non-None Return Values in Every Node

**Cycle**: 6 (2026-02-17)

**Failure Point**: `execute_node` initially returned `diffs` from `executor.execute()` without a None guard. If `executor.execute()` returned `None` instead of an empty list (e.g., if the executor had an error path that returned None rather than `[]`), LangGraph's `operator.add` reducer would raise `TypeError: 'NoneType' object is not iterable` — and the error message would not point to the node that returned None.

**Flawed Reasoning**: The `executor.execute()` contract says it returns `list[FileDiff]`. If the contract is upheld, the None guard is unnecessary defensive code.

**Correct Approach**: For every field using `Annotated[list, operator.add]`, every node that touches the field must include an explicit None guard before returning:
```python
diffs = executor.execute(task=task, repo_index=state["repo_index"], context=context)
# Guard even when the contract says it returns list — external agents can break contracts
if diffs is None:
    diffs = []
return {"diffs": diffs, ...}
```
Also apply the guard on the error path — `"diffs": []` not `"diffs": None`.

**General Principle**: `Annotated[list, operator.add]` reducers fail silently until runtime when any node returns `None` for the field. The TypeError from LangGraph's reducer does not identify which node returned None. Always return `[]` (not `None`) from every node for every `Annotated[list, ...]` field, both on the success path and on every error/early-exit path.

---

## Pitfall 013: Naming Custom Exceptions Same as Framework Exceptions

**Cycle**: 5 (2026-02-17)

**Failure Point**: The initial plan named the test-validator exception `ValidationError`. This collides with `pydantic.ValidationError`, which is imported in many modules throughout the project. When both are in scope, code that catches `ValidationError` may accidentally catch Pydantic model validation failures instead of test-validator failures, or imports become ambiguous.

**Flawed Reasoning**: `ValidationError` is a descriptive, clear name for what the exception represents. Since it lives in `agents/exceptions.py`, the fully-qualified name is different from pydantic's.

**Correct Approach**: Prefix or suffix custom exception names to avoid shadowing popular framework exceptions:
```python
# Wrong: collides with pydantic.ValidationError
class ValidationError(AgentError): ...

# Correct: domain-qualified name
class TestValidationError(AgentError): ...
```
Check for conflicts against these commonly imported names before finalizing: `ValueError`, `ValidationError`, `TypeError`, `RuntimeError`, `OSError`, `IOError`, `TimeoutError`.

**General Principle**: Popular frameworks (Pydantic, Django, Marshmallow, Cerberus) define `ValidationError`. Custom exceptions named `ValidationError` will shadow or be shadowed by these in any module that imports both. Always use a domain-specific prefix/suffix: `AuditError`, `TestValidationError`, `ParsingError`, etc.

---

## Pitfall 016: Patching Lazy Imports at the Wrong Module Path

**Cycle**: 7 (2026-02-17)

**Failure Point**: Tests using `@patch("refactor_bot.cli.main.EmbeddingService")` failed because `EmbeddingService` is not imported at module level in `main.py` — it is imported lazily inside `create_agents()`. The mock never intercepts the real class.

**Flawed Reasoning**: Standard mock patching targets `module.ClassName` where the class is used. This works when the class is imported at module level, but lazy imports happen inside a function scope, so the module-level attribute never exists.

**Correct Approach**: Patch at the class's defining module, where the import actually resolves:
```python
# Wrong: class not at module level due to lazy import
@patch("refactor_bot.cli.main.EmbeddingService")

# Correct: patch where the class is defined
@patch("refactor_bot.rag.embeddings.EmbeddingService")
```

**General Principle**: When a module uses lazy imports (imports inside functions), `@patch("that_module.ClassName")` fails because the name is never a module-level attribute. Always patch at the source module where the class is defined. This applies to any codebase that uses lazy imports for startup performance.

---

## Pitfall 017: Substring-Based Error Classification Causes False Positives

**Cycle**: 7 (2026-02-17)

**Failure Point**: Initial abort detection used `if "abort" in str(error).lower()` to classify errors as graph aborts. This matched any error message containing the word "abort" — including legitimate errors like "Transaction aborted by database" or "User aborted the operation" — causing incorrect exit codes.

**Flawed Reasoning**: The abort_node in graph.py writes error messages containing "abort", so checking for the substring seemed like a reliable detection method.

**Correct Approach**: Use prefix matching with a sentinel constant:
```python
# Wrong: substring match causes false positives
if "abort" in str(error).lower():
    return EXIT_GRAPH_ABORT

# Correct: prefix match with constant shared between graph.py and cli
ABORT_PREFIX = "ABORT:"
if str(error).startswith(ABORT_PREFIX):
    return EXIT_GRAPH_ABORT
```

**General Principle**: Error classification based on substring matching in error messages is inherently fragile. Use structured sentinel values (prefixes, error codes, exception subclasses) instead. If you must inspect error messages, use prefix matching with a shared constant, not substring search.

---
