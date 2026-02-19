from __future__ import annotations

import importlib
from pathlib import Path
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
        self._skills[self._normalize_name(skill.metadata.name)] = skill

    def has_skill(self, name: str) -> bool:
        return self._normalize_name(name) in self._skills

    def normalize_skill_names(self, names: List[str]) -> List[str]:
        return [self._normalize_name(name) for name in names]

    def register_from_package(self, package_name: str) -> None:
        try:
            module_name = package_name.replace("-", "_")
            module = importlib.import_module(f"refactor_bot.skills.{module_name}")
            if hasattr(module, "skill"):
                skill = module.skill
                try:
                    package_dir = Path(module.__file__).parent if module.__file__ else None
                    if package_dir is not None:
                        skill.load_from_disk(package_dir)
                except Exception as e:
                    print(f"[SkillRegistry] Skill load failed for {package_name}: {e}")
                self.register(skill)
        except Exception as e:
            print(f"[SkillRegistry] Failed to register {package_name}: {e}")

    def auto_activate(self, repo_index: "RepoIndex", directive: str | None = None) -> List[Skill]:
        self._active_skills = [
            s for s in self._skills.values() if s.applies_to(repo_index, directive)
        ]
        return self._active_skills

    def activate_by_name(self, names: List[str]) -> None:
        normalized_names = self.normalize_skill_names(names)
        unknown = [name for name in normalized_names if name not in self._skills]

        if unknown:
            raise ValueError(f"Unknown skill(s): {', '.join(unknown)}")

        activated: list[Skill] = []
        seen: set[str] = set()
        for name in normalized_names:
            skill = self._skills.get(name)
            if skill is None or name in seen:
                continue
            activated.append(skill)
            seen.add(name)
        self._active_skills = activated

    def get_active_skills(self) -> List[Skill]:
        return self._active_skills

    def get_prompt_context_for_all_active(self, directive: str, task: Any = None) -> str:
        return "\n\n".join(
            s.get_prompt_context(directive, task) for s in self._active_skills
        )

    def get_all_rules(self) -> List["RefactorRule"]:
        rules = []
        for s in self._active_skills:
            try:
                rules.extend(s.get_rules())
            except Exception as exc:
                print(f"[SkillRegistry] Failed to load rules from skill '{s.metadata.name}': {exc}")
        return rules

    @staticmethod
    def _normalize_name(value: str) -> str:
        return value.strip().replace("_", "-").lower()


registry = SkillRegistry.get_instance()
