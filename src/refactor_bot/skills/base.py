from __future__ import annotations

from pathlib import Path

from typing import Any, Protocol, runtime_checkable
from ..models.skill_models import SkillMetadata
from ..models.task_models import TaskNode
from ..models.skill_models import RefactorRule


@runtime_checkable
class Skill(Protocol):
    """Core Skill Protocol – matches Vercel Agent Skills 2026 standard."""

    metadata: SkillMetadata

    def applies_to(
        self,
        repo_index: Any,
        directive: str | None = None,
    ) -> bool:
        """Return True if this skill should be active."""

    def get_rules(self) -> list[RefactorRule]:
        """Rules provided by this skill (used by Auditor)."""

    def get_prompt_context(
        self, directive: str, task: TaskNode | None = None
    ) -> str:
        """Full context string to inject into LLM prompts."""

    def load_from_disk(self, skill_path: Path) -> None:
        """Optional runtime load of SKILL.md / AGENTS.md."""
