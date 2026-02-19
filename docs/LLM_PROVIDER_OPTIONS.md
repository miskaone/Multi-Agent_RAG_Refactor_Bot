# LLM Provider Options and Fallback Behavior

## CLI

- Primary provider: `--llm-provider {auto|anthropic|openai}`
  - `auto` (default): prefer Anthropic when `ANTHROPIC_API_KEY` is present, else OpenAI when `OPENAI_API_KEY` is present.
  - `anthropic`: force Anthropic `messages.create` tool-calling.
  - `openai`: force OpenAI `chat.completions` function-calling.

- Fallback provider: `--llm-fallback-provider {anthropic|openai}`
  - Optional. Only used when `--allow-llm-fallback` is set or interactive HIL approval is granted.

- HIL fallback toggle: `--allow-llm-fallback`
  - When set, system can use fallback automatically after failure on primary.

- Interactive HIL fallback:
  - Automatic when running in a TTY and not `--dry-run`.
  - Prompts:
    - `Use fallback provider 'openai|anthropic'? [y/N]:`

## Required credentials

- Anthropic: `ANTHROPIC_API_KEY`
- OpenAI: `OPENAI_API_KEY`

## Local environment file

The CLI now loads environment variables from a `.env` file in the project root.
Keep your keys out of command history and shell exports by storing them in `.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...   # optional
```

Run with:

```bash
uv run python -m refactor_bot.cli "Convert class components to hooks" . \
  --llm-provider anthropic
```

If both providers are set, the active provider still follows `--llm-provider`.

Examples:

```bash
# Force Anthropic
uv run python -m refactor_bot.cli "Convert class components to hooks" /path/to/repo \
  --llm-provider anthropic

# Use OpenAI first, Anthropic fallback (non-interactive)
uv run python -m refactor_bot.cli "Convert class components to hooks" /path/to/repo \
  --llm-provider openai --llm-fallback-provider anthropic --allow-llm-fallback

# Human-in-the-loop fallback from Anthropic to OpenAI
uv run python -m refactor_bot.cli "Convert class components to hooks" /path/to/repo \
  --llm-provider anthropic --llm-fallback-provider openai
```

## Notes

- If no test runner is detected, validator still uses the same provider selection/fallback logic for LLM-only validation.
- If neither provider key is available and fallback is reached, validation returns the existing low-trust fallback-unavailable message when `--allow-no-runner-pass` is enabled.

## Release notes and review

- Changelog draft: [CHANGELOG_DRAFT.md](CHANGELOG_DRAFT.md)
- PR review checklist: [PR_REVIEW_CHECKLIST.md](PR_REVIEW_CHECKLIST.md)
