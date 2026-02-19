# PR Review Checklist

## Mandatory checks

1. Environment/security smoke

- Ensure `.env` exists locally with required keys:
  - `ANTHROPIC_API_KEY`
  - `OPENAI_API_KEY` (optional, when OpenAI fallback is needed)
- Ensure secrets are not tracked in Git (`git status --ignored | rg '\.env'` should show ignore status).

2. Local control-run smoke check

```bash
cd /Users/michaellydick/dev/test-repo1
./scripts/check-control-repo.sh
```

3. Merge-risk regression check (strict)

```bash
cd /Users/michaellydick/dev/test-repo1
./scripts/check-control-repo.sh --strict
```

4. Optional focused runtime check

```bash
cd /Users/michaellydick/dev/Multi-Agent_RAG_Refactor_Bot
uv run python -m refactor_bot.cli "Convert class components to hooks" /Users/michaellydick/dev/test-repo1 --llm-provider anthropic --output-json
```

## Checklist items to include in PR description

- [ ] `--strict` control check passes.
- [ ] No real API key appears in repository diffs or docs examples.
- [ ] New behavior around env loading and provider selection is documented.
- [ ] If behavior changed, include expected control-run deltas (task count / finding pattern).
