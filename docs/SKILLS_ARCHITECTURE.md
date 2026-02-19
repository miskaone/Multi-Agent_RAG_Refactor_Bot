# Skills Architecture

**Version:** 1.0 (for v0.2.0+)  
**Date:** February 18, 2026  
**Status:** Production-ready (v0.2.0+)

## Overview
This document defines the **Skills-based architecture** that replaces the legacy `rules/` directory and hard-coded React best practices.

A **Skill** is a self-contained, versioned, reusable capability that extends the bot with:
- Detection logic (`applies_to`)
- Rules (for Auditor)
- Prompt context (for Planner + Executor)
- Human-readable docs (SKILL.md)
- Agent-specific instructions (AGENTS.md)

This design is **100% compatible** with Vercel’s official Agent Skills standard (January 2026).

## Directory Structure

```text
src/refactor_bot/
├── skills/
│   ├── __init__.py
│   ├── base.py
│   ├── registry.py
│   ├── manager.py
│   └── vercel_react_best_practices/
│       ├── __init__.py
│       ├── skill.py
│       ├── rules.py
│       ├── SKILL.md
│       ├── AGENTS.md
│       └── metadata.json
├── models/
│   └── skill_models.py
└── ...
```

## Core Interfaces

### Skill Protocol (`skills/base.py`)

(See code below)

## Integration Points

1. RepoIndexer → `skill_registry.auto_activate(...)`
2. CLI → `--skills` flag
3. Planner / Executor → `registry.get_prompt_context_for_all_active()`
4. ConsistencyAuditor → `registry.get_all_rules()`

## Migration Path

- Legacy `rules/react_rules.py` remains as an implementation fallback during v0.2.x rollout.
- New skills are now active for repository-aware pipeline behavior.

## Usage

```bash
python -m refactor_bot.cli "Convert class components to hooks" ./my-app --skills vercel-react-best-practices
```
