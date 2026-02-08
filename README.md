# markdown-qa

Q&A over local Markdown: index directories with embeddings (FAISS + OpenAI-compatible API), run a WebSocket server, and ask questions from the CLI.

- **Table of contents**
  - [Feature highlights](#feature-highlights)
  - [Requirements](#requirements)
  - [Quick setup](#quick-setup)
  - [Configuration](#configuration)
  - [Usage](#usage)
  - [Development](#development)

## Feature highlights

- **Incremental updates** — Only re-index changed files (by mtime); full rebuild when needed.
- **WebSocket server** — Long-running process; optional scheduled reload; config file watched for API/server changes.
- **CLI client** — Single-question mode or interactive session; optional `--index` and `--server`.

## Requirements

- **Python 3.13+**
- **uv** (recommended) or pip
- **API**: OpenAI-compatible embedding + chat API (base URL + API key)

## Quick setup

```bash
# Clone and enter repo
git clone <repo-url> && cd markdown-qa

# Install dependencies (uv)
uv sync

# Optional: config for API (otherwise use env vars below)
mkdir -p ~/.md-qa
# Edit ~/.md-qa/config.yaml — see Configuration
```

**Minimal config (env vars):**

```bash
export MARKDOWN_QA_API_BASE_URL="https://your-api.com/v1"
export MARKDOWN_QA_API_KEY="your-key"
```

Then start the server and client:

```bash
# Terminal 1: index and serve (e.g. this repo’s docs)
uv run python -m markdown_qa.server --directories /path/to/your/md/docs

# Terminal 2: ask questions
uv run python -m markdown_qa.client "Your question here"
# Or interactive:
uv run python -m markdown_qa.client
```

## Configuration

Precedence: **CLI args** → **config file** → **env** → **defaults**.

| Source | Location |
|--------|----------|
| Config file | `~/.md-qa/config.yaml` or `~/.md-qa/config.toml` |
| Env vars | `MARKDOWN_QA_API_BASE_URL`, `MARKDOWN_QA_API_KEY`, `MARKDOWN_QA_EMBEDDING_MODEL`, `MARKDOWN_QA_LLM_MODEL` |

Example **YAML** config:

```yaml
api:
  base_url: "https://your-api.com/v1"
  api_key: "your-api-key"
  embedding_model: "text-embedding-3-small"   # optional
  llm_model: "gpt-4o-mini"                    # optional
server:
  port: 8765
  directories:
    - /path/to/docs1
    - /path/to/docs2
  reload_interval: 300
  index_name: "default"
```

If you use the config file for `server.directories`, you can run the server without `--directories`.

## Usage

**Server**

```bash
uv run python -m markdown_qa.server [OPTIONS]
# --port PORT
# --directories DIR [DIR ...]
# --reload-interval SECS
# --index-name NAME
```

**Client**

```bash
uv run python -m markdown_qa.client [QUESTION] [OPTIONS]
# --server ws://localhost:8765
# --index INDEX_NAME
```

- Omit `QUESTION` for interactive mode.
- Default server URL: `ws://localhost:8765`.

## Development

- **Tests:** `uv run pytest`
- **Dependencies:** managed with **uv** only (`uv add`, `uv remove`, `uv sync`). See `.cursor/rules/uv.md`.
- **Specs:** `openspec/` and `AGENTS.md` describe the Markdown Q&A behaviour and OpenSpec workflow.
