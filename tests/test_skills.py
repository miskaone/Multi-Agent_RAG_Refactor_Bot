"""Unit tests for skills loading, parsing, and activation."""

from pathlib import Path

from refactor_bot.rules.react_rules import REACT_RULES
from refactor_bot.skills.manager import activate_skills_for_repo
from refactor_bot.skills.registry import registry
from refactor_bot.skills.vercel_react_best_practices import rules
from refactor_bot.skills.vercel_react_best_practices.skill import VercelReactBestPracticesSkill


class DummyRepoIndex:
    is_react_project = False


def _reset_registry_state():
    registry._skills = {}
    registry._active_skills = []


def test_vercel_rules_parser_reads_quick_reference(tmp_path: Path):
    skill_markdown = tmp_path / "SKILL.md"
    skill_markdown.write_text(
        "\n".join(
            [
                "# Skill",
                "### 1. Eliminating Waterfalls (CRITICAL)",
                "- `async-parallel` - Use Promise.all() for independent calls",
                "- `bundle-barrel-imports` - Import modules directly",
            ]
        )
    )

    parsed = rules.get_rules(skill_markdown)
    assert len(parsed) == 2
    rule_ids = {r.rule_id for r in parsed}
    assert rule_ids == {"async-parallel", "bundle-barrel-imports"}
    assert parsed[0].category in {"Eliminating Waterfalls", "Bundle Size Optimization"}


def test_vercel_rules_parser_handles_flexible_markup(tmp_path: Path):
    skill_markdown = tmp_path / "SKILL.md"
    skill_markdown.write_text(
        "\n".join(
            [
                "# Skill",
                "## 2. Bundle Size Optimization (CRITICAL)",
                "* `bundle-conditional` Use conditional imports for dev-only tooling",
                "1. `bundle-dynamic-imports` - Split heavy modules into dynamic imports",
                "| `bundle-barrel-imports` | Avoid importing module roots |",
                "",
                "```ts",
                "- `ignore-me` - should not be parsed",
                "```",
            ]
        )
    )

    parsed = rules.get_rules(skill_markdown)
    rule_ids = {r.rule_id for r in parsed}
    assert "bundle-conditional" in rule_ids
    assert "bundle-dynamic-imports" in rule_ids
    assert "bundle-barrel-imports" in rule_ids
    assert "ignore-me" not in rule_ids
    assert parsed[0].rule_id in {"bundle-conditional", "bundle-dynamic-imports", "bundle-barrel-imports"}


def test_vercel_rules_parser_fallback_to_react_catalog_on_missing_reference(tmp_path: Path):
    skill_markdown = tmp_path / "SKILL.md"
    skill_markdown.write_text("[placeholder content copied from upstream is pending]")

    parsed = rules.get_rules(skill_markdown)
    assert len(parsed) == len(REACT_RULES)
    assert {r.rule_id for r in parsed} == {r.rule_id for r in REACT_RULES}


def test_vercel_skill_load_from_disk_uses_prompt_and_rules(tmp_path: Path):
    _reset_registry_state()

    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()

    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        "\n".join(
            [
                "# Vercel",
                "### 1. Eliminating Waterfalls (CRITICAL)",
                "- `async-defer-await` - Move await into branches.",
            ]
        )
    )
    agents_file = skill_dir / "AGENTS.md"
    agents_file.write_text("test agent prompt context")

    vrs = VercelReactBestPracticesSkill()
    vrs.load_from_disk(skill_dir)

    assert vrs.get_prompt_context("noop") == "test agent prompt context"
    parsed = vrs.get_rules()
    assert parsed
    assert parsed[0].rule_id == "async-defer-await"


class TestSkillActivation:
    def test_activate_explicit_skill_name(self):
        _reset_registry_state()
        active = activate_skills_for_repo(
            DummyRepoIndex(),
            selected_skill_names=["vercel-react-best-practices"],
        )
        assert len(active) == 1
        assert active[0].metadata.name == "vercel-react-best-practices"

    def test_activate_unknown_skill_name_raises(self):
        _reset_registry_state()
        try:
            activate_skills_for_repo(
                DummyRepoIndex(),
                selected_skill_names=["not-a-real-skill"],
            )
        except ValueError as exc:
            assert "Unknown skill(s)" in str(exc)
        else:
            raise AssertionError("Expected ValueError for unknown skill")

    def test_activate_skill_name_with_underscores(self):
        _reset_registry_state()
        active = activate_skills_for_repo(
            DummyRepoIndex(),
            selected_skill_names=["vercel_react_best_practices"],
        )
        assert active
        assert active[0].metadata.name == "vercel-react-best-practices"
