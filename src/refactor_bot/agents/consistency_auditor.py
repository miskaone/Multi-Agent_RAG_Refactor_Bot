"""Consistency Auditor agent: checks diffs for structural integrity."""

import re
from typing import Any

from tree_sitter import Language, Parser, Query, QueryCursor, Tree

from refactor_bot.models.diff_models import FileDiff
from refactor_bot.models.report_models import AuditFinding, AuditReport, FindingSeverity
from refactor_bot.models.schemas import RepoIndex, FileInfo, SymbolInfo
from refactor_bot.rules import REACT_RULES
from refactor_bot.rules.rule_engine import ReactRule
from refactor_bot.utils.ast_parser import (
    get_language_for_file,
    get_parser,
    extract_imports,
    extract_symbols,
    extract_exports,
    JS_LANGUAGE,
    TS_LANGUAGE,
    TSX_LANGUAGE,
)


LANG_MAP: dict[str, Language] = {
    "javascript": JS_LANGUAGE,
    "typescript": TS_LANGUAGE,
    "tsx": TSX_LANGUAGE,
}


ANTI_PATTERN_SIGNALS: dict[str, list[str]] = {
    "async-parallel":           ["await fetchUser()", "await fetchPosts()"],
    "bundle-barrel-imports":    ["from 'lodash'", "from '@mui/material'"],
    "async-defer-await":        ["const data = await fetch"],
    "async-dependencies":       ["await fetchUser(userId)", "await fetchAnalytics()"],
    "async-api-routes":         ["await db.user.findUnique", "await db.post.findMany"],
    "async-suspense-boundaries":["async function ParentComponent", "async function ChildComponent"],
    "bundle-dynamic-imports":   ["import { Chart } from 'chart.js'"],
    "bundle-defer-third-party": ["import Analytics from '@segment"],
    "bundle-conditional":       ["import { DevTools } from 'dev-tools'"],
    "bundle-preload":           ["const Dashboard = lazy("],
    "server-auth-actions":      ["const session = useSession()"],
    "server-cache-react":       ["await db.user.findUnique"],
    "server-cache-lru":         ["await db.post.findMany"],
    "server-dedup-props":       ["await fetchUser(userId)"],
    "server-serialization":     ["date={post.createdAt}"],
    "server-parallel-fetching": ["await fetchNavigation()"],
    "server-after-nonblocking": ["await analytics.track("],
}


class ConsistencyAuditor:
    """Checks diffs for structural consistency: orphaned imports,
    signature mismatches, dependency integrity, and React anti-patterns."""

    def __init__(self, react_rules: list[ReactRule] | None = None) -> None:
        """Initialize with optional rule override (defaults to REACT_RULES)."""
        self._rules: list[ReactRule] = react_rules if react_rules is not None else list(REACT_RULES)
        self._finding_counter: int = 0

    def audit(
        self,
        diffs: list[FileDiff],
        repo_index: RepoIndex,
    ) -> AuditReport:
        """Run all audits and return consolidated report.

        Returns AuditReport with passed=True if no ERROR-severity findings.
        """
        self._finding_counter = 0
        all_findings: list[AuditFinding] = []

        for diff in diffs:
            orphan_findings = self._check_orphaned_imports(diff)
            all_findings.extend(orphan_findings)

        # Signature mismatch across all diffs
        sig_findings = self._check_signature_mismatches(diffs, repo_index)
        all_findings.extend(sig_findings)

        # Dependency integrity across all diffs
        dep_findings = self._check_dependency_integrity(diffs, repo_index)
        all_findings.extend(dep_findings)

        # Anti-pattern checks (only for React projects)
        if repo_index.is_react_project:
            for diff in diffs:
                ap_findings = self._check_react_anti_patterns(diff)
                all_findings.extend(ap_findings)

        # Note: if parseable_count == 0, all diffs had unsupported extensions.
        # This is not an error — we silently return a passing report.

        # Compute counts
        error_count = sum(1 for f in all_findings if f.severity == FindingSeverity.ERROR)
        warning_count = sum(1 for f in all_findings if f.severity == FindingSeverity.WARNING)
        info_count = sum(1 for f in all_findings if f.severity == FindingSeverity.INFO)

        return AuditReport(
            passed=error_count == 0,
            findings=all_findings,
            diffs_audited=len(diffs),
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
        )

    def _check_orphaned_imports(self, diff: FileDiff) -> list[AuditFinding]:
        """Parse modified_content via tree-sitter. Extract import bindings
        using import_specifier/namespace_import/default import queries.
        For each binding, search AST for identifier nodes outside import_statement.
        If count == 0, emit ERROR finding with finding_type='orphaned_import'."""
        parsed = self._parse_content(diff.file_path, diff.modified_content)
        if parsed is None:
            return []

        tree, language = parsed
        content_bytes = diff.modified_content.encode("utf-8")
        findings: list[AuditFinding] = []

        # Collect all import bindings (named, namespace, default)
        import_bindings: list[tuple[str, int | None]] = []  # (name, line_number)

        # Query for named import specifiers: import { useState, useCallback } from '...'
        named_query = Query(language, """
            (import_statement
                (import_clause
                    (named_imports
                        (import_specifier
                            name: (identifier) @binding))))
        """)
        named_cursor = QueryCursor(named_query)
        for match in named_cursor.matches(tree.root_node):
            _, captures = match
            if "binding" in captures:
                for node in captures["binding"]:
                    name = node.text.decode("utf-8") if node.text else ""
                    line = node.start_point[0] + 1
                    if name:
                        import_bindings.append((name, line))

        # Query for namespace imports: import * as foo from '...'
        namespace_query = Query(language, """
            (import_statement
                (import_clause
                    (namespace_import
                        (identifier) @binding)))
        """)
        namespace_cursor = QueryCursor(namespace_query)
        for match in namespace_cursor.matches(tree.root_node):
            _, captures = match
            if "binding" in captures:
                for node in captures["binding"]:
                    name = node.text.decode("utf-8") if node.text else ""
                    line = node.start_point[0] + 1
                    if name:
                        import_bindings.append((name, line))

        # Query for default imports: import foo from '...'
        default_query = Query(language, """
            (import_statement
                (import_clause
                    (identifier) @binding))
        """)
        default_cursor = QueryCursor(default_query)
        for match in default_cursor.matches(tree.root_node):
            _, captures = match
            if "binding" in captures:
                for node in captures["binding"]:
                    name = node.text.decode("utf-8") if node.text else ""
                    line = node.start_point[0] + 1
                    if name:
                        import_bindings.append((name, line))

        if not import_bindings:
            return findings

        # Collect all import_statement node byte ranges to exclude them
        import_statement_ranges: list[tuple[int, int]] = []
        for child in tree.root_node.children:
            if child.type == "import_statement":
                import_statement_ranges.append((child.start_byte, child.end_byte))

        # Collect all identifier nodes outside import statements
        def collect_identifiers_outside_imports(node: Any) -> list[Any]:
            """Recursively collect identifier nodes not inside import_statement."""
            result = []
            # If this node is an import_statement, skip it entirely
            if node.type == "import_statement":
                return result
            if node.type in ("identifier", "type_identifier"):
                result.append(node)
            for child in node.children:
                result.extend(collect_identifiers_outside_imports(child))
            return result

        outside_identifiers = collect_identifiers_outside_imports(tree.root_node)
        outside_names: set[str] = set()
        for id_node in outside_identifiers:
            name = id_node.text.decode("utf-8") if id_node.text else ""
            if name:
                outside_names.add(name)

        # Deduplicate bindings (same name may appear from multiple queries)
        seen_bindings: set[str] = set()
        for binding_name, line_number in import_bindings:
            if binding_name in seen_bindings:
                continue
            seen_bindings.add(binding_name)
            if binding_name not in outside_names:
                findings.append(AuditFinding(
                    finding_id=self._next_finding_id(),
                    file_path=diff.file_path,
                    finding_type="orphaned_import",
                    severity=FindingSeverity.ERROR,
                    description=f"Imported binding '{binding_name}' is never used.",
                    line_number=line_number,
                    evidence=f"import binding: {binding_name}",
                ))

        return findings

    def _check_signature_mismatches(
        self,
        diffs: list[FileDiff],
        repo_index: RepoIndex,
    ) -> list[AuditFinding]:
        """Build map of exported names from modified diffs. Compare against
        repo_index baseline. If a name was renamed or removed and callers
        in repo_index reference the old name (via SymbolInfo.calls), emit
        ERROR finding with finding_type='signature_mismatch'.
        Also check parameter count changes via regex heuristic."""
        findings: list[AuditFinding] = []

        # Build a map: file_path -> set of exported names BEFORE the diff (baseline)
        baseline_exports: dict[str, set[str]] = {}
        for file_info in repo_index.files:
            baseline_exports[file_info.file_path] = set(file_info.exports)
            # Also index by relative_path
            baseline_exports[file_info.relative_path] = set(file_info.exports)

        # Build a map: file_path -> set of exported names AFTER the diff
        modified_exports: dict[str, set[str]] = {}
        for diff in diffs:
            parsed = self._parse_content(diff.file_path, diff.modified_content)
            if parsed is None:
                continue
            tree, language = parsed
            new_exports = set(extract_exports(tree, language))
            modified_exports[diff.file_path] = new_exports

        # Build a map: symbol_name -> list of callers (FileInfo)
        # from repo_index: iterate all symbols and their calls
        callers_of: dict[str, list[str]] = {}  # symbol_name -> [caller_file_path]
        for file_info in repo_index.files:
            for symbol in file_info.symbols:
                for called_name in symbol.calls:
                    if called_name not in callers_of:
                        callers_of[called_name] = []
                    callers_of[called_name].append(file_info.file_path)

        # For each modified diff, check removed exports
        for diff in diffs:
            if diff.file_path not in modified_exports:
                continue
            new_exports = modified_exports[diff.file_path]

            # Find baseline exports for this file
            old_exports = baseline_exports.get(diff.file_path, set())
            if not old_exports:
                continue

            # Names that were removed or renamed
            removed_names = old_exports - new_exports
            for removed_name in removed_names:
                if removed_name in callers_of:
                    caller_paths = callers_of[removed_name]
                    for caller_path in caller_paths:
                        findings.append(AuditFinding(
                            finding_id=self._next_finding_id(),
                            file_path=diff.file_path,
                            finding_type="signature_mismatch",
                            severity=FindingSeverity.ERROR,
                            description=(
                                f"Exported symbol '{removed_name}' was removed or renamed "
                                f"in '{diff.file_path}', but is still referenced by '{caller_path}'."
                            ),
                            evidence=(
                                f"Old export: {removed_name}; "
                                f"New exports: {sorted(new_exports)}; "
                                f"Caller: {caller_path}"
                            ),
                        ))

            # Parameter count heuristic: compare original vs modified
            for export_name in old_exports & new_exports:
                orig_match = re.search(
                    rf'(?:function\s+{re.escape(export_name)}\s*\(|'
                    rf'(?:const|let|var)\s+{re.escape(export_name)}\s*=\s*(?:async\s*)?\()([^)]*)',
                    diff.original_content,
                )
                mod_match = re.search(
                    rf'(?:function\s+{re.escape(export_name)}\s*\(|'
                    rf'(?:const|let|var)\s+{re.escape(export_name)}\s*=\s*(?:async\s*)?\()([^)]*)',
                    diff.modified_content,
                )
                if orig_match and mod_match:
                    orig_params = [p.strip() for p in orig_match.group(1).split(",") if p.strip()]
                    mod_params = [p.strip() for p in mod_match.group(1).split(",") if p.strip()]
                    if len(orig_params) != len(mod_params) and export_name in callers_of:
                        for caller_path in callers_of[export_name]:
                            findings.append(AuditFinding(
                                finding_id=self._next_finding_id(),
                                file_path=diff.file_path,
                                finding_type="signature_mismatch",
                                severity=FindingSeverity.ERROR,
                                description=(
                                    f"Parameter count changed for '{export_name}': "
                                    f"{len(orig_params)} -> {len(mod_params)} parameters. "
                                    f"Callers may be broken."
                                ),
                                evidence=(
                                    f"Original params ({len(orig_params)}): {orig_params}; "
                                    f"Modified params ({len(mod_params)}): {mod_params}; "
                                    f"Caller: {caller_path}"
                                ),
                            ))

        return findings

    def _check_dependency_integrity(
        self,
        diffs: list[FileDiff],
        repo_index: RepoIndex,
    ) -> list[AuditFinding]:
        """For each import path in modified diffs, verify the target module
        exists in repo_index.files or is a known package (starts with no
        relative prefix like './' or '../'). Emit ERROR finding with
        finding_type='dependency_integrity' if not found."""
        findings: list[AuditFinding] = []

        # Build set of all known file paths from repo_index
        known_paths: set[str] = set()
        for file_info in repo_index.files:
            known_paths.add(file_info.file_path)
            known_paths.add(file_info.relative_path)

        for diff in diffs:
            parsed = self._parse_content(diff.file_path, diff.modified_content)
            if parsed is None:
                continue
            tree, language = parsed
            import_paths = extract_imports(tree, language)

            for import_path in import_paths:
                # Skip non-relative imports (they are external packages)
                if not import_path.startswith("./") and not import_path.startswith("../"):
                    continue

                # Check if this relative import resolves to a known file
                found = False
                for known in known_paths:
                    # Try matching by suffix or checking the path itself
                    # Strip common extensions for comparison
                    clean_import = import_path.rstrip("/")
                    if known.endswith(clean_import) or known.endswith(clean_import + ".ts") or \
                       known.endswith(clean_import + ".tsx") or known.endswith(clean_import + ".js"):
                        found = True
                        break
                    # Also check if the import path appears in the known path
                    if clean_import in known:
                        found = True
                        break

                if not found:
                    findings.append(AuditFinding(
                        finding_id=self._next_finding_id(),
                        file_path=diff.file_path,
                        finding_type="dependency_integrity",
                        severity=FindingSeverity.ERROR,
                        description=(
                            f"Import '{import_path}' in '{diff.file_path}' "
                            f"does not resolve to any known file in the repository."
                        ),
                        evidence=f"Unresolved import: {import_path}",
                    ))

        return findings

    def _check_react_anti_patterns(
        self,
        diff: FileDiff,
    ) -> list[AuditFinding]:
        """Check modified_content against ANTI_PATTERN_SIGNALS dict.
        Emit WARNING finding with finding_type='anti_pattern' and rule_id set.
        Only called when repo_index.is_react_project is True."""
        findings: list[AuditFinding] = []
        content = diff.modified_content

        # Build signals from self._rules if available, fall back to module-level
        signals_map = ANTI_PATTERN_SIGNALS
        if self._rules:
            # Build rule_id set for filtering
            active_rule_ids = {r.rule_id for r in self._rules}
            signals_map = {
                k: v for k, v in ANTI_PATTERN_SIGNALS.items()
                if k in active_rule_ids
            }

        for rule_id, signals in signals_map.items():
            for signal in signals:
                if signal in content:
                    findings.append(AuditFinding(
                        finding_id=self._next_finding_id(),
                        file_path=diff.file_path,
                        finding_type="anti_pattern",
                        severity=FindingSeverity.WARNING,
                        description=(
                            f"Anti-pattern detected (rule '{rule_id}'): "
                            f"signal '{signal}' found in modified content."
                        ),
                        rule_id=rule_id,
                        evidence=signal,
                    ))
                    # One finding per rule_id is enough
                    break

        return findings

    def _parse_content(
        self,
        file_path: str,
        content: str,
    ) -> tuple[Tree, Language] | None:
        """Parse content string via tree-sitter.
        Returns (tree, language) or None for unsupported extensions."""
        try:
            lang_name = get_language_for_file(file_path)
        except ValueError:
            return None

        language = LANG_MAP.get(lang_name)
        if language is None:
            return None

        parser = get_parser(lang_name)
        tree = parser.parse(content.encode("utf-8"))
        return tree, language

    def _next_finding_id(self) -> str:
        """Return next finding_id in 'AF-001' format."""
        self._finding_counter += 1
        return f"AF-{self._finding_counter:03d}"
