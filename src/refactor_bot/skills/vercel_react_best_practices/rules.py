"""Helpers for loading Vercel React best-practice rules from markdown."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import re

from refactor_bot.models.skill_models import RefactorRule
from refactor_bot.rules.react_rules import REACT_RULES

SECTION_HEADER_RE = re.compile(r"^###\s+\d+\.\s+(?P<section>.+?)\s*\((?P<priority>[^)]+)\)")
RULE_ITEM_RE = re.compile(r"^- `(?P<rule_id>[^`]+)` - (?P<description>.*)$")


def _parse_skill_catalog(skill_markdown_path: Path) -> Dict[str, Tuple[str, str, str]]:
    """Parse rule id, category, and priority from SKILL.md quick-reference section."""
    rules: Dict[str, Tuple[str, str, str]] = {}
    current_section = "General"
    current_priority = "MEDIUM"

    with skill_markdown_path.open(encoding="utf-8") as fp:
        for raw_line in fp:
            line = raw_line.strip()

            section_match = SECTION_HEADER_RE.match(line)
            if section_match:
                current_section = section_match.group("section").strip()
                current_priority = section_match.group("priority").strip()
                continue

            rule_match = RULE_ITEM_RE.match(line)
            if rule_match:
                rule_id = rule_match.group("rule_id").strip()
                description = rule_match.group("description").strip()
                rules[rule_id] = (current_section, current_priority, description)

    return rules


def get_rules(skill_markdown_path: Path) -> list[RefactorRule]:
    """Load skill-backed React rules into shared `RefactorRule` format."""
    catalog = _parse_skill_catalog(skill_markdown_path)
    if not catalog:
        return []

    react_rule_index = {rule.rule_id: rule for rule in REACT_RULES}
    rules: list[RefactorRule] = []

    for rule_id, (category, priority, description) in catalog.items():
        template = react_rule_index.get(rule_id)
        if not template:
            rules.append(
                RefactorRule(
                    rule_id=rule_id,
                    category=category,
                    priority=priority,
                    description=f"{description} (pattern not shipped in code base)",
                    incorrect_pattern=f"// TODO: add incorrect pattern for {rule_id}",
                    correct_pattern=f"// TODO: add correct pattern for {rule_id}",
                )
            )
            continue

        rules.append(
            RefactorRule(
                rule_id=rule_id,
                category=template.category or category,
                priority=template.priority or priority,
                description=(
                    f"{description}\n\n"
                    f"Legacy guidance: {template.description}"
                ).strip(),
                incorrect_pattern=template.incorrect_pattern,
                correct_pattern=template.correct_pattern,
            )
        )
    return rules
