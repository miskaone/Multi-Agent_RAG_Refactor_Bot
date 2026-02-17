"""Tests for ConsistencyAuditor agent."""

import pytest
from refactor_bot.agents.consistency_auditor import ConsistencyAuditor, ANTI_PATTERN_SIGNALS
from refactor_bot.agents.exceptions import AuditError
from refactor_bot.models import AuditReport, FileDiff, FileInfo, RepoIndex, SymbolInfo
from refactor_bot.models.report_models import AuditFinding, FindingSeverity


# ---------------------------------------------------------------------------
# Inline fixture content
# ---------------------------------------------------------------------------

# useCallback is imported but never used in the body → orphaned import
ORPHANED_IMPORT_CONTENT = """\
import { useState, useCallback } from 'react';

export function Counter() {
    const [count, setCount] = useState(0);
    return count;
}
"""

# All imports actually used → clean diff
CLEAN_TS_CONTENT = """\
import { useState } from 'react';

export function Counter() {
    const [count, setCount] = useState(0);
    return count;
}
"""

# Contains a barrel import signal that should trigger anti_pattern WARNING
BARREL_IMPORT_CONTENT = """\
import { Button, TextField } from '@mui/material';

export function MyForm() {
    return <Button><TextField /></Button>;
}
"""

# A diff that imports ./nonexistent which is not present in the repo_index
NONEXISTENT_DEP_CONTENT = """\
import { helper } from './nonexistent';

export function doSomething() {
    return helper();
}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_file_diff(
    file_path: str,
    modified_content: str,
    task_id: str = "task-1",
) -> FileDiff:
    return FileDiff(
        file_path=file_path,
        original_content="",
        modified_content=modified_content,
        diff_text="",
        task_id=task_id,
    )


def _make_base_repo_index(is_react_project: bool = True) -> RepoIndex:
    """Minimal RepoIndex with a single placeholder file."""
    file_info = FileInfo(
        file_path="src/counter.ts",
        relative_path="src/counter.ts",
        language="typescript",
        hash="abc123",
    )
    return RepoIndex(
        repo_path="/fake/repo",
        files=[file_info],
        is_react_project=is_react_project,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_audit_detects_orphaned_import():
    """FileDiff with useCallback imported but unused → report.passed=False,
    at least one orphaned_import finding with ERROR severity."""
    auditor = ConsistencyAuditor()
    diff = _make_file_diff("src/counter.ts", ORPHANED_IMPORT_CONTENT)
    repo_index = _make_base_repo_index()

    report = auditor.audit([diff], repo_index)

    assert report.passed is False

    orphaned_findings = [
        f for f in report.findings if f.finding_type == "orphaned_import"
    ]
    assert len(orphaned_findings) >= 1

    # All orphaned_import findings should be ERROR severity
    for finding in orphaned_findings:
        assert finding.severity == FindingSeverity.ERROR

    # The description or evidence should mention useCallback
    descriptions = " ".join(
        (f.description or "") + (f.evidence or "") for f in orphaned_findings
    )
    assert "useCallback" in descriptions


def test_audit_detects_signature_mismatch():
    """Diff renames exported function getUser → fetchUser.
    A caller in repo_index references 'getUser' via calls=[].
    The auditor should emit a signature_mismatch finding."""
    # The modified content exports fetchUser (renamed from getUser)
    modified_content = """\
export function fetchUser(id: string) {
    return { id, name: 'Test' };
}
"""

    auditor = ConsistencyAuditor()
    diff = _make_file_diff("src/callee.ts", modified_content)

    # caller.ts has a symbol that calls the old name "getUser"
    caller_symbol = SymbolInfo(
        name="loadProfile",
        type="function",
        file_path="src/caller.ts",
        start_line=1,
        end_line=5,
        start_byte=0,
        end_byte=100,
        source_code="import { getUser } from './callee';\nexport function loadProfile() { return getUser('123'); }",
        calls=["getUser"],
    )
    caller_file = FileInfo(
        file_path="src/caller.ts",
        relative_path="src/caller.ts",
        language="typescript",
        hash="caller_hash",
        symbols=[caller_symbol],
    )
    # The original callee registered getUser as an export in the index
    callee_file = FileInfo(
        file_path="src/callee.ts",
        relative_path="src/callee.ts",
        language="typescript",
        hash="callee_hash",
        exports=["getUser"],
    )

    repo_index = RepoIndex(
        repo_path="/fake/repo",
        files=[callee_file, caller_file],
        is_react_project=False,
    )

    report = auditor.audit([diff], repo_index)

    mismatch_findings = [
        f for f in report.findings if f.finding_type == "signature_mismatch"
    ]
    assert len(mismatch_findings) >= 1
    for finding in mismatch_findings:
        assert finding.severity == FindingSeverity.ERROR


def test_audit_clean_diff_passes():
    """Diff where all imports are used and no mismatches → report.passed=True,
    error_count == 0."""
    auditor = ConsistencyAuditor()
    diff = _make_file_diff("src/counter.ts", CLEAN_TS_CONTENT)
    repo_index = _make_base_repo_index()

    report = auditor.audit([diff], repo_index)

    assert report.passed is True
    assert report.error_count == 0


def test_audit_react_anti_pattern_warning():
    """React project diff containing a barrel import signal (@mui/material)
    should emit a WARNING finding with finding_type='anti_pattern'."""
    auditor = ConsistencyAuditor()
    diff = _make_file_diff("src/my_form.tsx", BARREL_IMPORT_CONTENT)
    repo_index = _make_base_repo_index(is_react_project=True)

    report = auditor.audit([diff], repo_index)

    anti_pattern_findings = [
        f for f in report.findings if f.finding_type == "anti_pattern"
    ]
    assert len(anti_pattern_findings) >= 1

    # Anti-pattern findings must be WARNING (not ERROR), so the report may still pass
    for finding in anti_pattern_findings:
        assert finding.severity == FindingSeverity.WARNING


def test_audit_non_react_skips_anti_pattern():
    """When is_react_project=False the auditor should not produce any
    anti_pattern findings, even when the content matches a signal."""
    auditor = ConsistencyAuditor()
    diff = _make_file_diff("src/my_form.tsx", BARREL_IMPORT_CONTENT)
    repo_index = _make_base_repo_index(is_react_project=False)

    report = auditor.audit([diff], repo_index)

    anti_pattern_findings = [
        f for f in report.findings if f.finding_type == "anti_pattern"
    ]
    assert len(anti_pattern_findings) == 0


def test_audit_unsupported_extension_skipped():
    """A FileDiff with a .py extension should be handled gracefully.
    The audit must complete without raising an exception and may return
    passed=True since there are no parseable TypeScript/JS diffs to error on."""
    auditor = ConsistencyAuditor()
    diff = _make_file_diff(
        "src/helper.py",
        "def helper():\n    return 42\n",
    )
    repo_index = _make_base_repo_index()

    # Must not raise
    report = auditor.audit([diff], repo_index)

    assert isinstance(report, AuditReport)
    # No orphaned_import findings from an unsupported extension
    orphaned = [f for f in report.findings if f.finding_type == "orphaned_import"]
    assert len(orphaned) == 0


def test_audit_multiple_diffs():
    """Two diffs: one clean and one with an orphaned import.
    The report should contain exactly one ERROR-severity finding (the orphan)."""
    auditor = ConsistencyAuditor()

    clean_diff = _make_file_diff("src/clean.ts", CLEAN_TS_CONTENT, task_id="task-1")
    orphan_diff = _make_file_diff(
        "src/counter.ts", ORPHANED_IMPORT_CONTENT, task_id="task-2"
    )

    repo_index = _make_base_repo_index()

    report = auditor.audit([clean_diff, orphan_diff], repo_index)

    error_findings = [
        f for f in report.findings if f.severity == FindingSeverity.ERROR
    ]
    assert len(error_findings) == 1
    assert error_findings[0].finding_type == "orphaned_import"
    assert report.passed is False


def test_audit_dependency_integrity():
    """A diff that imports './nonexistent' (not present in repo_index.files)
    should produce a dependency_integrity finding."""
    auditor = ConsistencyAuditor()
    diff = _make_file_diff("src/consumer.ts", NONEXISTENT_DEP_CONTENT)

    # repo_index does not contain any file matching nonexistent
    repo_index = _make_base_repo_index()

    report = auditor.audit([diff], repo_index)

    dep_findings = [
        f for f in report.findings if f.finding_type == "dependency_integrity"
    ]
    assert len(dep_findings) >= 1
    for finding in dep_findings:
        assert finding.severity == FindingSeverity.ERROR
