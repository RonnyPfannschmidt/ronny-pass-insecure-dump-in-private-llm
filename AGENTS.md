# Project: pass-analysis-lm

Analyze a [pass](https://www.passwordstore.org/) password store using a self-hosted LLM.

## Structure

- `src/ronny/pass_analysis_lm/`
  - `cli.py` – Click CLI (`run`, `config`, `tui` subcommands)
  - `analysis.py` – pydantic-ai agent for security analysis
  - `config.py` – TOML config loading, provider/model resolution
  - `secrets.py` – API key storage via system keyring
  - `store.py` – pass CLI wrapper (`pass show`)
  - `tui/` – Textual TUI (tree view, entry viewer, results panel)

## Conventions

- Python ≥ 3.11, strict mypy, ruff linting
- No comments unless explicitly requested
- Keep responses concise; avoid preamble/postamble
- Follow existing code style and patterns

## Commands

```
pre-commit run -a           # linting and typechecking
uv run pytest tests/        # tests
```

## Attribution

All AI-assisted commits must include attribution for model and harness.
