from typing import List, Literal

from pydantic import BaseModel

from refactor_bot.rules.rule_engine import ReactRule


ImpactLevel = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]


class SkillMetadata(BaseModel):
    name: str
    version: str
    description: str
    author: str = "refactor-bot"
    license: str = "MIT"
    impact_levels: List[ImpactLevel]
    categories: List[str]
    triggers: List[str]


class RefactorRule(ReactRule):
    """Rule model shared by skills and legacy rule systems."""

    pass
