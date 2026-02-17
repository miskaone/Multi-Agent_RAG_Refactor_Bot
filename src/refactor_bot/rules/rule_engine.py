"""Rule engine for React refactoring patterns."""

from pydantic import BaseModel


class ReactRule(BaseModel):
    """Represents a single React refactoring rule."""

    rule_id: str
    category: str
    priority: str
    description: str
    incorrect_pattern: str
    correct_pattern: str


def select_applicable_rules(
    directive: str,
    is_react_project: bool,
    all_rules: list[ReactRule] | None = None,
) -> list[str]:
    """Select applicable rules based on directive and project type.

    Args:
        directive: The refactoring directive from the user
        is_react_project: Whether the project is detected as React
        all_rules: List of all available rules (defaults to REACT_RULES if None)

    Returns:
        List of rule IDs that should be applied
    """
    if not is_react_project:
        return []

    if all_rules is None:
        from refactor_bot.rules.react_rules import REACT_RULES

        all_rules = REACT_RULES

    # Always include CRITICAL rules for React projects
    critical_rules = [rule.rule_id for rule in all_rules if rule.priority == "CRITICAL"]

    # Check for keywords to include HIGH priority rules
    directive_lower = directive.lower()

    high_rule_keywords = {
        "server-auth-actions": ["auth", "authentication", "authorization", "security"],
        "server-cache-react": ["cache", "caching", "dedupe", "deduplication"],
        "server-cache-lru": ["cache", "caching", "lru", "persistent"],
        "server-dedup-props": ["props", "duplicate", "redundant"],
        "server-serialization": ["serialize", "serialization", "hydration"],
        "server-parallel-fetching": ["parallel", "layout", "waterfall"],
        "server-after-nonblocking": ["async", "nonblocking", "after", "analytics"],
    }

    high_rules = []
    for rule_id, keywords in high_rule_keywords.items():
        if any(keyword in directive_lower for keyword in keywords):
            high_rules.append(rule_id)

    # Combine critical and matched high priority rules (deduplicated)
    return list(set(critical_rules + high_rules))
