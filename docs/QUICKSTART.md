# Quick Start

Get the Multi-Agent RAG Refactor Bot running in under 5 minutes.

## Prerequisites

- **Python 3.12+**
- **uv** (recommended): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Anthropic API key**: [console.anthropic.com](https://console.anthropic.com/)
- **OpenAI API key**: [platform.openai.com](https://platform.openai.com/)

## 1. Install

```bash
git clone https://github.com/miskaone/Multi-Agent_RAG_Refactor_Bot.git
cd Multi-Agent_RAG_Refactor_Bot
uv sync
```

## 2. Configure API Keys

```bash
cp .env.example .env
# edit .env with your real keys
```

The app automatically loads `.env` at startup.

```bash
# optional manual export
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

## 3. Verify Installation

```bash
python -m refactor_bot.cli --help
```

You should see:

```
usage: refactor-bot [-h] [--max-retries MAX_RETRIES] ...

Multi-Agent RAG Refactor Bot for JS/TS codebases
```

## 4. Dry Run

Test your configuration without calling any APIs:

```bash
python -m refactor_bot.cli "Convert class components to hooks" /path/to/your/react-app --dry-run
```

Expected output:

```
Configuration:
========================================
  directive: Convert class components to hooks
  repo_path: /path/to/your/react-app
  max_retries: 3
  model: claude-sonnet-4-5-20250929
  ...
========================================
```

## 5. Run a Refactoring

```bash
python -m refactor_bot.cli "Convert class components to hooks" /path/to/your/react-app
```

The bot will:
1. Index your repository and embed code symbols
2. Plan refactoring tasks with dependency ordering
3. Generate code diffs for each task
4. Audit diffs for structural integrity
5. Run your test suite to validate changes
6. Apply successful changes or retry/abort on failure

## 6. JSON Output

For programmatic use:

```bash
python -m refactor_bot.cli "Migrate to TypeScript" ./my-project --output-json
```

## Troubleshooting

### "Agent error: ..."

Missing or invalid API key. Verify:

```bash
echo $ANTHROPIC_API_KEY
echo $OPENAI_API_KEY
```

### "Error: '/path' is not a valid directory."

The repo path doesn't exist or is a file. Use an absolute or relative path to a directory.

### Exit code 4 (abort)

The pipeline aborted because test pass rate dropped below 85% or retries were exhausted. Run with `--verbose` for details:

```bash
python -m refactor_bot.cli "..." ./repo --verbose
```

## Release notes and review

- Changelog draft: [CHANGELOG_DRAFT.md](CHANGELOG_DRAFT.md)
- PR review checklist: [PR_REVIEW_CHECKLIST.md](PR_REVIEW_CHECKLIST.md)
