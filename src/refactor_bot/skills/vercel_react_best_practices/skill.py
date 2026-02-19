from pathlib import Path

from ...skills.base import Skill
from ...models.skill_models import SkillMetadata
from ...models.skill_models import RefactorRule
from .rules import get_rules


class VercelReactBestPracticesSkill(Skill):
    metadata = SkillMetadata(
        name="vercel-react-best-practices",
        version="1.0.0",
        description="Official Vercel React & Next.js performance rules (57 rules, Jan 2026)",
        author="vercel",
        impact_levels=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        categories=["performance", "react", "nextjs"],
        triggers=["react", "nextjs", "performance"]
    )

    def applies_to(self, repo_index, directive=None) -> bool:
        return getattr(repo_index, 'is_react_project', False) or "react" in (directive or "").lower()

    def get_rules(self) -> list[RefactorRule]:
        skill_path = Path(__file__).parent / "SKILL.md"
        if not skill_path.exists():
            return []
        return get_rules(skill_path)

    def get_prompt_context(self, directive: str, task=None) -> str:
        ag_path = Path(__file__).parent / "AGENTS.md"
        if ag_path.exists():
            return ag_path.read_text(encoding="utf-8")
        return "Vercel React Best Practices loaded."

    def load_from_disk(self, skill_path: Path) -> None:
        pass


skill = VercelReactBestPracticesSkill()
