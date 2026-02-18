# Skills Architecture

**Version:** 1.0 (for v0.2.0+)  
**Date:** February 18, 2026  
**Status:** Proposed → Implement after v0.1.1

## Overview

This document defines the **Skills-based architecture** that replaces the legacy `rules/` directory and hard-coded React best practices.

A **Skill** is a self-contained, versioned, reusable capability that extends the bot with:
- Detection logic (`applies_to`)
- Rules (for Auditor)
- Prompt context (for Planner + Executor)
- Human-readable docs (SKILL.md)
- Agent-specific instructions (AGENTS.md)

This design is **100% compatible** with the official [Vercel Agent Skills standard](https://github.com/vercel-labs/agent-skills) released January 2026 (react-best-practices, composition-patterns, etc.).

## Why Skills?

- Matches the 2026 industry standard used by Claude Code, Cursor, Opencode, Codex.
- Enables progressive disclosure (load only needed context → token efficient).
- Community-contributable (drop in a new skill folder).
- Perfectly aligns with future `LanguagePack` system.
- Turns “some extended Vercel React support” into first-class, updatable skills.
- CLI control: `--skills vercel-react-best-practices,security,typescript-strict`

## Directory Structure

```text
src/refactor_bot/
├── skills/
│   ├── __init__.py
│   ├── base.py                 # Skill Protocol + base classes
│   ├── registry.py             # SkillRegistry (singleton)
│   ├── manager.py              # SkillManager (orchestrator integration)
│   └── vercel_react_best_practices/   # First official skill
│       ├── __init__.py
│       ├── skill.py            # Skill implementation
│       ├── rules.py            # RefactorRule list
│       ├── SKILL.md            # Human docs (verbatim from Vercel)
│       ├── AGENTS.md           # LLM context (verbatim from Vercel)
│       └── metadata.json       # Standard Vercel metadata
├── models/
│   └── skill_models.py         # Pydantic models (added)
├── rules/                      # Legacy – will be deprecated after migration
└── ...