from refactor_bot.models import RefactorRule, SkillMetadata
from refactor_bot.models.report_models import RefactorRule as LegacyRefactorRule
from refactor_bot.models.skill_models import RefactorRule as CoreRefactorRule


def test_public_model_exports_remain_compatible():
    assert LegacyRefactorRule is CoreRefactorRule
    assert RefactorRule is CoreRefactorRule
    assert isinstance(
        SkillMetadata(
            name="x",
            version="1",
            description="y",
            impact_levels=["LOW"],
            categories=["c"],
            triggers=["t"],
        ),
        SkillMetadata,
    )
