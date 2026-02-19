"""Helpers for loading Vercel React best-practice rules from markdown."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import re

from refactor_bot.models.skill_models import RefactorRule
from refactor_bot.rules.react_rules import REACT_RULES

SECTION_HEADER_RE = re.compile(
    r"^#{1,6}\s+(?:\d+\.\s*)?(?P<section>.+?)\s*(?:\((?P<priority>[^)]+)\))?\s*$"
)
RULE_ITEM_RE = re.compile(
    r"^[\t ]*(?:[-*+]|\d+[.)])\s+`(?P<rule_id>[^`]+)`\s*(?:[-–—:]\s*)?(?P<description>.*)$"
)
TABLE_ROW_RE = re.compile(
    r"^\|?\s*`(?P<rule_id>[^`]+)`\s*\|\s*(?P<description>[^|]+)"
)
SECTION_PRIORITY_RE = re.compile(r"\b(CRITICAL|HIGH|MEDIUM|LOW)\b", re.IGNORECASE)


def _normalize_priority(raw_priority: str) -> str:
    """Clamp priority to known severities."""
    match = SECTION_PRIORITY_RE.search(raw_priority or "")
    if not match:
        return "MEDIUM"
    return match.group(1).upper()


def _strip_numeric_prefix(section: str) -> str:
    return re.sub(r"^\d+\.\s*", "", section).strip()


def _parse_skill_catalog(skill_markdown_path: Path) -> Dict[str, Tuple[str, str, str]]:
    """Parse rule id, category, and priority from SKILL.md quick-reference section."""
    rules: Dict[str, Tuple[str, str, str]] = {}
    current_section = "General"
    current_priority = "MEDIUM"

    if not skill_markdown_path.exists():
        return rules

    in_code_block = False

    with skill_markdown_path.open(encoding="utf-8") as fp:
        for raw_line in fp:
            line = raw_line.rstrip()

            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            line = line.strip()
            if not line:
                continue

            section_match = SECTION_HEADER_RE.match(line)
            if section_match:
                current_section = _strip_numeric_prefix(section_match.group("section").strip())
                current_priority = _normalize_priority(
                    section_match.group("priority") or current_priority
                )
                continue

            rule_match = RULE_ITEM_RE.match(line)
            if not rule_match:
                rule_match = TABLE_ROW_RE.match(line)
            if not rule_match:
                continue

            rule_id = rule_match.group("rule_id").strip()
            description = rule_match.group("description").strip()
            if rule_id and not rule_id.startswith("#") and rule_id not in rules:
                rules[rule_id] = (current_section, current_priority, description)

    return rules


def _normalize_rule(
    rule_id: str,
    category: str,
    priority: str,
    description: str,
    template: RefactorRule | None = None,
) -> RefactorRule:
    if template is None:
        return RefactorRule(
            rule_id=rule_id,
            category=category,
            priority=_normalize_priority(priority),
            description=(
                f"{description} (placeholder guidance; complete pattern not available)"
                if description
                else "Placeholder guidance; complete pattern not available"
            ).strip(),
            incorrect_pattern="// TODO: add incorrect pattern",
            correct_pattern="// TODO: add correct pattern",
        )

    merged_description = (
        f"{description}\n\nLegacy guidance: {template.description}".strip()
        if description
        else template.description
    )
    return RefactorRule(
        rule_id=rule_id,
        category=template.category or category,
        priority=_normalize_priority(template.priority or priority),
        description=merged_description,
        incorrect_pattern=template.incorrect_pattern,
        correct_pattern=template.correct_pattern,
    )


def _build_rules(catalog: Dict[str, Tuple[str, str, str]]) -> list[RefactorRule]:
    if not catalog:
        return [
            RefactorRule(
                rule_id=rule.rule_id,
                category=rule.category,
                priority=rule.priority,
                description=rule.description,
                incorrect_pattern=rule.incorrect_pattern,
                correct_pattern=rule.correct_pattern,
            )
            for rule in REACT_RULES
        ]

    react_rule_index = {rule.rule_id: rule for rule in REACT_RULES}
    rules: list[RefactorRule] = []

    for rule_id, (category, priority, description) in catalog.items():
        template = react_rule_index.get(rule_id)
        rules.append(_normalize_rule(rule_id, category, priority, description, template))

    return rules


def _add_missing_rules_from_react(catalog_rules: list[RefactorRule]) -> list[RefactorRule]:
    catalog_ids = {rule.rule_id for rule in catalog_rules}
    for rule in REACT_RULES:
        if rule.rule_id not in catalog_ids:
            catalog_rules.append(
                RefactorRule(
                    rule_id=rule.rule_id,
                    category=rule.category,
                    priority=rule.priority,
                    description=rule.description,
                    incorrect_pattern=rule.incorrect_pattern,
                    correct_pattern=rule.correct_pattern,
                )
            )
    return catalog_rules


def get_rules(skill_markdown_path: Path) -> list[RefactorRule]:
    """Load skill-backed React rules into shared `RefactorRule` format."""
    catalog = _parse_skill_catalog(skill_markdown_path)
    parsed_rules = _build_rules(catalog)
    return _add_missing_rules_from_react(parsed_rules)
