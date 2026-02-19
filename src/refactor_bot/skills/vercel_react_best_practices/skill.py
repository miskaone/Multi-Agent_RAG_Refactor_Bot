from pathlib import Path

from ...skills.base import Skill
from ...models.skill_models import SkillMetadata
from ...models.skill_models import RefactorRule
from .rules import get_rules


class VercelReactBestPracticesSkill(Skill):
    def __init__(self) -> None:
        self._skill_path: Path | None = None

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
        skill_path = self._active_skill_file()
        if not skill_path:
            return []
        return get_rules(skill_path)

    def get_prompt_context(self, directive: str, task=None) -> str:
        ag_path = self._active_skill_file("AGENTS.md")
        if ag_path and ag_path.exists():
            return ag_path.read_text(encoding="utf-8")
        return "Vercel React Best Practices loaded."

    def load_from_disk(self, skill_path: Path) -> None:
        self._skill_path = skill_path

        metadata_path = skill_path / "metadata.json"
        if metadata_path.exists():
            # Optional extension point for future dynamic metadata fields.
            # Keep runtime robust: ignore malformed metadata and continue with defaults.
            try:
                data = _read_metadata(metadata_path)
            except Exception:
                data = {}
            if data:
                self.metadata = SkillMetadata(
                    name=self.metadata.name,
                    version=data.get("version", self.metadata.version),
                    description=self.metadata.description,
                    author=data.get("organization", self.metadata.author),
                    impact_levels=self.metadata.impact_levels,
                    categories=self.metadata.categories,
                    triggers=self.metadata.triggers,
                )

    def _active_skill_file(self, filename: str = "SKILL.md") -> Path | None:
        candidate = self._skill_path or (Path(__file__).parent)
        if filename and (candidate / filename).exists():
            return candidate / filename
        return None


skill = VercelReactBestPracticesSkill()


def _read_metadata(path: Path) -> dict[str, str]:
    import json

    with path.open(encoding="utf-8") as fp:
        data = json.load(fp)
    return data if isinstance(data, dict) else {}
