# markdown-qa

Q&A over local Markdown: index directories with embeddings (FAISS + OpenAI-compatible API), run a WebSocket server, and ask questions from the CLI or a desktop GUI.

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
- **Desktop GUI** (Tauri) — Config editor + chat panel; connects to the same WebSocket server.
- **Rust TUI client** (`md-qa`) — Single-question mode; reads `~/.md-qa/config.yaml`; same WebSocket protocol as the server.
- **Python CLI client** *(deprecated)* — Single-question mode or interactive session; being replaced by the Rust TUI.

## Requirements

- **Python 3.13+**
- **uv** (recommended) or pip
- **API**: OpenAI-compatible embedding + chat API (base URL + API key)
- **Rust stable** (for the TUI binary and GUI app; install via [rustup](https://rustup.rs))
- **System libs for Tauri** (Linux: `libwebkit2gtk-4.1-dev`, `libgtk-3-dev`, etc. — see [Tauri prerequisites](https://tauri.app/start/prerequisites/))

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

# Terminal 2: ask questions (Rust TUI — recommended)
md-qa --config ~/.md-qa/config.yaml "Your question here"
# Or via stdin:
echo "Your question here" | md-qa --config ~/.md-qa/config.yaml
# Or via env var:
#   export MD_QA_CONFIG=~/.md-qa/config.yaml
#   md-qa "Your question"
#   # or: echo "Your question" | md-qa

# (deprecated) Python client:
# uv run python -m markdown_qa.client "Your question here"
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

**GUI (Tauri desktop app)**

```bash
# Build and run the desktop app
cargo build --release -p md_qa_gui
./target/release/md_qa_gui
# Or during development:
cargo run -p md_qa_gui
```

- Opens a window with a **Settings** tab (config editor) and a **Chat** tab.
- Connects to the WebSocket server on startup using the port from config.
- The server must be started separately (`python -m markdown_qa.server`). The GUI does not start or manage the server.
- Config is read from and written to `~/.md-qa/config.yaml`.

**Client (Rust TUI — recommended)**

```bash
# Build once
cargo build --release -p md_qa_client --bin md-qa

# Single question (positional arg, pipe, or redirect)
md-qa "What is Python?"
md-qa --config ~/.md-qa/config.yaml "What is Python?"
echo "What is Python?" | md-qa --config ~/.md-qa/config.yaml
# Or use env var MD_QA_CONFIG instead of --config
```

- `--config` is optional.
- Config lookup order: `--config` → `MD_QA_CONFIG` → `~/.md-qa/config.yaml` (if present) → built-in defaults.
- With built-in defaults, client connects to `ws://127.0.0.1:8765` and omits index.
- Connects to `ws://127.0.0.1:{port}`, sends the question, prints streamed answer and sources.

**Client (Python — deprecated)**

```bash
uv run python -m markdown_qa.client [QUESTION] [OPTIONS]
# --server ws://localhost:8765
# --index INDEX_NAME
```

- Omit `QUESTION` for interactive mode.
- Default server URL: `ws://localhost:8765`.
- **Deprecated**: use the Rust `md-qa` binary instead.

## Development

- **Python tests:** `uv run pytest`
- **Rust tests:** `cargo test` (runs `md_qa_client` and `md_qa_gui` test suites)
- **Dependencies:** Python managed with **uv** only (`uv add`, `uv remove`, `uv sync`). See `.cursor/rules/uv.md`. Rust managed via `Cargo.toml`.
- **Specs:** `openspec/` and `AGENTS.md` describe the Markdown Q&A behaviour and OpenSpec workflow.
