# Design: Add GUI Client

## Context

The markdown Q&A system has a WebSocket server and a CLI (TUI) client. Configuration is read from `~/.md-qa/config.yaml` and environment variables; the client connects to a server URL and sends queries, receiving streamed answers and sources. Users who avoid the terminal need a graphical way to edit that config and to chat. The GUI must stay consistent with existing config format and protocol so server and TUI remain unchanged.

**Current state:** `MarkdownQAClient` (async, websockets), `APIConfig` / `ServerConfig` (YAML/TOML), `ResponseFormatter`, message types in `markdown_qa.messages`. Server is started separately (e.g. `python -m markdown_qa.server`).

**Constraints:** Same config file and schema; no server or protocol changes; cross-platform (Windows, macOS, Linux).

## Goals / Non-Goals

**Goals:**

- Provide a desktop GUI that edits `~/.md-qa` config (API and server sections) and offers a chat panel.
- Connect to the WebSocket server on application startup; show connection status (connected / disconnected / error).
- Support optional index selection in the chat UI (default from config).
- Session-only chat in v1 (no persistence of history).
- Users can choose to interact via **GUI or TUI**; both use the same client implementation (Rust).

**Non-Goals:**

- Starting or managing the server from the GUI (server is assumed already running).
- Chat history persistence or multi-session history.
- Changing the WebSocket protocol or config file format.
- Web-based UI or mobile support.

## Decisions

### GUI: Tauri; client and TUI rewritten in Rust

- **Rationale:** Use Tauri for the desktop GUI (Rust + web view). To avoid embedding Python (PyO3) and to get a single, shippable binary, the **client side is rewritten in Rust**. One client implementation in Rust is shared by (1) the Tauri GUI and (2) a **Rust TUI** (CLI) that replaces the current Python interactive client. Users can run either the GUI app or the Rust TUI; both connect to the same Python server and speak the same WebSocket protocol.
- **Scope of rewrite:** Implement in Rust: WebSocket client, message types (query, stream start/chunk/end, error, response), config read/write for client use (server URL, port, index; full config for the GUI form via `serde_yaml`). The **Python codebase becomes server-only** for this surface: the existing Python `markdown_qa.client` (TUI) is **deprecated and replaced** by the Rust TUI binary. No Python in the GUI or TUI process.
- **Protocol as contract:** Maintain a **single, written protocol spec** (e.g. in docs or openspec) that defines message types, stream phases, and config schema. The Python server and the Rust client both implement this spec. Any protocol or config-format change is done in the spec first, then in both codebases.
- **Alternatives considered:** Python-native GUI (PySide6/CustomTkinter) reuses the existing Python client but keeps a Python-heavy desktop stack. Tauri + PyO3 embeds Python to reuse the client but adds FFI, GIL, and packaging complexity. Rewriting the client in Rust avoids those and yields one client codebase (Rust) for both GUI and TUI.

### Rust client library: shared by Tauri and Rust TUI

- **Rationale:** One Rust crate (or library within the Tauri app) implements: connect, send query, handle streamed responses (STREAM_START / STREAM_CHUNK / STREAM_END, sources, errors), and config load/save (YAML only). The Tauri app uses this library for the chat panel and config form. The Rust TUI binary uses the same library and prints to the terminal (stream chunks with `print!`, then sources). No duplication of protocol or config logic.
- **Tech:** Async Rust (e.g. tokio), WebSocket crate (e.g. tokio-tungstenite), serde for message types and config. Tauri emits events to the web view for each chunk; TUI writes to stdout.

### Config: read on startup, write on save (Rust)

- **Rationale:** Config is the single source of truth. The GUI loads config at startup from `~/.md-qa/config.yaml` (Rust reads via serde_yaml), populates the form. User edits; "Save" writes back to the same YAML file, creating `~/.md-qa/` if needed. The Rust TUI reads the same config for server URL and index. Precedence (CLI args → config file → env) is preserved; Rust implements the same precedence rules for the TUI; GUI only writes the config file.
- **Format:** Use **YAML only**. The GUI and Rust TUI read and write `~/.md-qa/config.yaml` only. No TOML support in the client; this keeps the client simple and matches the primary documented format. The server may still support TOML for existing users; the GUI does not need to.

### Connect on startup (GUI)

- **Rationale:** User expects to open the app and have chat ready. After loading config, derive server URL (e.g. `ws://localhost:{port}`), connect in the background, and show "Connected" or an error. Chat panel is disabled or clearly marked when disconnected; optional "Reconnect" button. No aggressive auto-retry; one attempt on startup (and on Reconnect) for v1.

### Chat UI: one conversation, stream into current message

- **Rationale:** No history means one linear conversation per session. Each user message is sent with the same protocol as the TUI. Response: append stream chunks to the current reply area, then show sources on STREAM_END. Same behavior in Rust TUI (stream to terminal, then print sources).

### Index selection (what “server exposing indexes” means)

- The server today loads **one** index at a time (the name comes from config: `server.index_name`, e.g. `"default"`). The manifest can track multiple index *names* on disk, but at runtime the server only serves the single loaded index. The query protocol allows an optional `"index"` field in the message, but the current server **does not use it** to switch indexes—it always queries the loaded index. So the server does **not** currently “expose” multiple queryable indexes to the client.
- **For the GUI v1:** Use the single index from config (`server.index_name`). No need for an index selector in the chat UI unless the server later supports multiple loaded indexes and selects by the `index` field. The client can still send the configured index name in the query for future compatibility.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-------------|
| Protocol implemented in two codebases (Python server, Rust client) | Maintain a single written protocol spec; any change is done in the spec first, then in both implementations. Integration tests: server (Python) + client (Rust) for round-trip. |
| Rust/Tauri build and dependency stack | Document Rust and Tauri version requirements; CI for Rust client and Tauri app. |
| API key stored in plain config file | Accept current behavior (same as TUI); optionally document that users can restrict file permissions. Future: optional keychain integration. |
| Packaging and distribution (installers per OS) | Tauri supports building per-platform installers; defer to a later task if needed. v1 can be "build with `cargo tauri build`" and run the Tauri app or Rust TUI binary. |

## Migration Plan

- **Deploy:** New Tauri app (GUI) and Rust TUI binary; Python `markdown_qa.client` deprecated and eventually removed. No migration of config or server; existing users switch to Rust TUI or GUI. Server remains Python.
- **Rollback:** Keep Python client available until Rust TUI is proven; remove Rust client/Tauri app if needed; server unchanged.

## Open Questions

- None at this time. (Config: YAML only for the GUI/TUI client. Index in chat: server has one index; GUI uses config index, no selector needed for v1.)
