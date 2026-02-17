"""Report models for audit and test validation."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class FindingSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class AuditFinding(BaseModel):
    model_config = ConfigDict(frozen=False)

    finding_id: str               # "AF-001" format
    file_path: str                # Which diff triggered this
    finding_type: str             # "orphaned_import" | "signature_mismatch" |
                                  # "anti_pattern" | "dependency_integrity"
    severity: FindingSeverity
    description: str
    line_number: int | None = None
    rule_id: str | None = None    # Linked ReactRule if finding_type == "anti_pattern"
    evidence: str | None = None   # Code snippet or diff excerpt


class AuditReport(BaseModel):
    model_config = ConfigDict(frozen=False)

    passed: bool                          # True if no ERROR-severity findings
    findings: list[AuditFinding] = Field(default_factory=list)
    diffs_audited: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    audited_at: datetime = Field(default_factory=datetime.now)


class TestRunResult(BaseModel):
    model_config = ConfigDict(frozen=False)

    runner: str               # "vitest" | "npm_test" | "llm_fallback" | "none"
    exit_code: int
    stdout: str
    stderr: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration_seconds: float | None = None


class BreakingChange(BaseModel):
    model_config = ConfigDict(frozen=False)

    test_name: str
    file_path: str | None = None
    failure_message: str | None = None


class TestReport(BaseModel):
    model_config = ConfigDict(frozen=False)

    passed: bool                                    # True if post_run.exit_code == 0
    pre_run: TestRunResult | None = None
    post_run: TestRunResult
    breaking_changes: list[BreakingChange] = Field(default_factory=list)
    runner_available: bool = True
    llm_analysis: str | None = None
    tested_at: datetime = Field(default_factory=datetime.now)
