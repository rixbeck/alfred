# Alfred — Unified Vault Operations Suite

Four tools, one install, one config, one CLI.

| Tool | What it does |
|------|-------------|
| **Curator** | Watches inbox/, processes raw inputs (emails, voice memos) into structured vault records |
| **Janitor** | Scans vault for quality issues (broken links, invalid frontmatter, orphans) and fixes them |
| **Distiller** | Extracts latent knowledge (assumptions, decisions, constraints) from operational records |
| **Surveyor** | Embeds vault content, clusters semantically, labels clusters, suggests relationships |

## Quick Start

```bash
pip install -e .
alfred quickstart
alfred up
```

## Install

```bash
# Base install (curator + janitor + distiller)
pip install -e .

# Full install (adds surveyor — requires Ollama + OpenRouter)
pip install -e ".[all]"
```

## CLI

```bash
alfred quickstart              # Interactive setup wizard
alfred up [--only curator,janitor]  # Start all/selected daemons
alfred status                  # Show status from all tools

alfred curator                 # Start curator daemon
alfred janitor scan            # Run structural scan
alfred janitor fix             # Scan + agent fix
alfred janitor watch           # Daemon mode
alfred janitor status          # Show sweep status
alfred janitor history         # Show sweep history
alfred janitor ignore <file>   # Ignore a file

alfred distiller scan          # Scan for extraction candidates
alfred distiller run           # Scan + extract
alfred distiller watch         # Daemon mode
alfred distiller status        # Show extraction status
alfred distiller history       # Show run history

alfred surveyor                # Start surveyor pipeline
```

All commands accept `--config path/to/config.yaml` (default: `config.yaml`).

## Agent Backends

Curator, Janitor, and Distiller use an AI agent to process vault content. Three backends:

- **Claude Code** (`claude` on PATH) — default
- **Zo Computer** — set `ZO_API_KEY` in `.env`
- **OpenClaw** (`openclaw` on PATH)

Surveyor uses Ollama locally for embeddings and OpenRouter for cluster labeling.

## Config

Copy `config.yaml.example` to `config.yaml` and edit. Copy `.env.example` to `.env` for API keys.
