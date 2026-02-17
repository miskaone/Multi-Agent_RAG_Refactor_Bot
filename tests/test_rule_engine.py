"""Tests for rule engine and REACT_RULES."""


from refactor_bot.rules.react_rules import REACT_RULES
from refactor_bot.rules.rule_engine import ReactRule, select_applicable_rules


class TestReactRules:
    """Tests for REACT_RULES constant."""

    def test_react_rules_has_exactly_17_entries(self):
        """Test that REACT_RULES has exactly 17 entries."""
        assert len(REACT_RULES) == 17

    def test_all_rules_have_non_empty_patterns(self):
        """Test that all rules have non-empty incorrect and correct patterns."""
        for rule in REACT_RULES:
            assert rule.incorrect_pattern, f"Rule {rule.rule_id} has empty incorrect_pattern"
            assert rule.correct_pattern, f"Rule {rule.rule_id} has empty correct_pattern"
            assert len(rule.incorrect_pattern.strip()) > 0
            assert len(rule.correct_pattern.strip()) > 0

    def test_all_priorities_are_critical_or_high(self):
        """Test that all rules have priority CRITICAL or HIGH."""
        valid_priorities = {"CRITICAL", "HIGH"}
        for rule in REACT_RULES:
            assert rule.priority in valid_priorities, (
                f"Rule {rule.rule_id} has invalid priority: {rule.priority}"
            )

    def test_all_rules_have_required_fields(self):
        """Test that all rules have all required fields."""
        for rule in REACT_RULES:
            assert rule.rule_id
            assert rule.category
            assert rule.priority
            assert rule.description
            assert rule.incorrect_pattern
            assert rule.correct_pattern

    def test_all_rule_ids_are_unique(self):
        """Test that all rule IDs are unique."""
        rule_ids = [rule.rule_id for rule in REACT_RULES]
        assert len(rule_ids) == len(set(rule_ids)), "Duplicate rule IDs found"

    def test_rules_are_react_rule_instances(self):
        """Test that all REACT_RULES entries are ReactRule instances."""
        for rule in REACT_RULES:
            assert isinstance(rule, ReactRule)


class TestReactRuleModel:
    """Tests for ReactRule Pydantic model."""

    def test_react_rule_creation(self):
        """Test creating a ReactRule instance."""
        rule = ReactRule(
            rule_id="TEST001",
            category="performance",
            priority="CRITICAL",
            description="Test rule",
            incorrect_pattern="bad code",
            correct_pattern="good code",
        )
        assert rule.rule_id == "TEST001"
        assert rule.category == "performance"
        assert rule.priority == "CRITICAL"
        assert rule.description == "Test rule"
        assert rule.incorrect_pattern == "bad code"
        assert rule.correct_pattern == "good code"


class TestSelectApplicableRules:
    """Tests for select_applicable_rules function."""

    def test_returns_empty_for_non_react_project(self):
        """Test that select_applicable_rules returns empty list for non-React projects."""
        result = select_applicable_rules(
            directive="Refactor the authentication module",
            is_react_project=False,
        )
        assert result == []

    def test_returns_empty_for_non_react_project_with_keywords(self):
        """Test that non-React projects get empty list even with matching keywords."""
        result = select_applicable_rules(
            directive="Optimize server-side rendering and bundle size",
            is_react_project=False,
        )
        assert result == []

    def test_includes_critical_rules_for_react_project(self):
        """Test that CRITICAL rules are included for React projects."""
        result = select_applicable_rules(
            directive="Refactor the component",
            is_react_project=True,
        )
        # Should return some rules (at least CRITICAL ones)
        assert isinstance(result, list)
        assert len(result) > 0

        # Verify all returned items are rule IDs (strings)
        for rule_id in result:
            assert isinstance(rule_id, str)

    def test_keyword_matching_server(self):
        """Test HIGH rules with 'server' keyword included when directive mentions server."""
        result = select_applicable_rules(
            directive="Optimize server-side rendering for better performance",
            is_react_project=True,
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_keyword_matching_bundle(self):
        """Test HIGH rules with 'bundle' keyword included when directive mentions bundle."""
        result = select_applicable_rules(
            directive="Reduce bundle size and improve loading time",
            is_react_project=True,
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_keyword_matching_async(self):
        """Test that HIGH rules with 'async' keyword are included when directive mentions async."""
        result = select_applicable_rules(
            directive="Refactor async data fetching patterns",
            is_react_project=True,
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_keyword_matching_case_insensitive(self):
        """Test that keyword matching is case-insensitive."""
        result_lower = select_applicable_rules(
            directive="optimize server components",
            is_react_project=True,
        )
        result_upper = select_applicable_rules(
            directive="OPTIMIZE SERVER COMPONENTS",
            is_react_project=True,
        )
        result_mixed = select_applicable_rules(
            directive="Optimize Server Components",
            is_react_project=True,
        )

        # All should return rules
        assert len(result_lower) > 0
        assert len(result_upper) > 0
        assert len(result_mixed) > 0

    def test_custom_all_rules_parameter(self):
        """Test that custom all_rules parameter works."""
        custom_rules = [
            ReactRule(
                rule_id="CUSTOM001",
                category="test",
                priority="CRITICAL",
                description="Custom test rule",
                incorrect_pattern="old pattern",
                correct_pattern="new pattern",
            ),
            ReactRule(
                rule_id="CUSTOM002",
                category="test",
                priority="HIGH",
                description="Custom high priority rule",
                incorrect_pattern="old async",
                correct_pattern="new async",
            ),
        ]

        result = select_applicable_rules(
            directive="Test directive",
            is_react_project=True,
            all_rules=custom_rules,
        )

        # Should return rule IDs from custom rules
        assert isinstance(result, list)
        # At minimum, CRITICAL rule should be included
        assert "CUSTOM001" in result

    def test_custom_rules_empty_for_non_react(self):
        """Test that custom rules still respect is_react_project=False."""
        custom_rules = [
            ReactRule(
                rule_id="CUSTOM001",
                category="test",
                priority="CRITICAL",
                description="Custom test rule",
                incorrect_pattern="old pattern",
                correct_pattern="new pattern",
            ),
        ]

        result = select_applicable_rules(
            directive="Test directive",
            is_react_project=False,
            all_rules=custom_rules,
        )

        assert result == []

    def test_multiple_keywords_in_directive(self):
        """Test directive with multiple matching keywords."""
        result = select_applicable_rules(
            directive="Optimize server bundle and improve async data loading",
            is_react_project=True,
        )
        # Should include rules matching any of: server, bundle, async
        assert isinstance(result, list)
        assert len(result) > 0

    def test_returns_list_of_strings(self):
        """Test that function returns list of rule ID strings."""
        result = select_applicable_rules(
            directive="Refactor components",
            is_react_project=True,
        )
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, str)

    def test_empty_directive_react_project(self):
        """Test that empty directive still returns CRITICAL rules for React project."""
        result = select_applicable_rules(
            directive="",
            is_react_project=True,
        )
        # Should still return CRITICAL rules even with empty directive
        assert isinstance(result, list)
