from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any, Dict, List

from .base import Skill
from ..models.skill_models import RefactorRule

if TYPE_CHECKING:
    from ..models.schemas import RepoIndex


class SkillRegistry:
    _instance = None
    _skills: Dict[str, Skill] = {}
    _active_skills: List[Skill] = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "SkillRegistry":
        return cls()

    def register(self, skill: Skill) -> None:
        self._skills[skill.metadata.name] = skill

    def register_from_package(self, package_name: str) -> None:
        try:
            module = importlib.import_module(f"refactor_bot.skills.{package_name}")
            if hasattr(module, "skill"):
                self.register(module.skill)
        except Exception as e:
            print(f"[SkillRegistry] Failed to register {package_name}: {e}")

    def auto_activate(self, repo_index: "RepoIndex", directive: str | None = None) -> List[Skill]:
        self._active_skills = [
            s for s in self._skills.values() if s.applies_to(repo_index, directive)
        ]
        return self._active_skills

    def activate_by_name(self, names: List[str]) -> None:
        self._active_skills = [s for name, s in self._skills.items() if name in names]

    def get_active_skills(self) -> List[Skill]:
        return self._active_skills

    def get_prompt_context_for_all_active(self, directive: str, task: Any = None) -> str:
        return "\n\n".join(
            s.get_prompt_context(directive, task) for s in self._active_skills
        )

    def get_all_rules(self) -> List["RefactorRule"]:
        rules = []
        for s in self._active_skills:
            rules.extend(s.get_rules())
        return rules


registry = SkillRegistry.get_instance()
