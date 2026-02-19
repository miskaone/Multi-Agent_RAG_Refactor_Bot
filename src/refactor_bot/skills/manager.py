from __future__ import annotations

from .registry import registry
# from ..languages.registry import registry as lang_registry  # will be added in Phase 2


def activate_skills_for_repo(
    repo_index,
    directive: str | None = None,
    selected_skill_names: list[str] | None = None,
):
    """Helper called from RepoIndexer / CLI."""
    registry.register_from_package("vercel_react_best_practices")
    if selected_skill_names:
        for skill_name in selected_skill_names:
            normalized_skill_name = skill_name.strip().lower().replace("_", "-")
            if not registry.has_skill(normalized_skill_name):
                registry.register_from_package(normalized_skill_name)

        registry.activate_by_name(selected_skill_names)
    else:
        registry.auto_activate(repo_index, directive)
    return registry.get_active_skills()
