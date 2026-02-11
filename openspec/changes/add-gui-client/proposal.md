# Proposal: Add GUI Client

## Why

Users without terminal experience need a way to configure the markdown Q&A system (API key, base URL, document paths, etc.) and to ask questions via a graphical interface. A cross-platform GUI gives these users the same capabilities as the existing CLI client while allowing others to keep using the TUI.

## What Changes

- Add a **cross-platform desktop GUI** (Windows, macOS, Linux) that:
  - **Config**: Edits the same config file (`~/.md-qa/config.yaml` or `.toml`) via a form—API base URL, API key, embedding/LLM model, server port, list of markdown directories (with add/remove), reload interval, index name. Writes back to the existing config so server and TUI client are unchanged.
  - **Chat**: Connects to the existing WebSocket server on startup and provides a chat panel to send questions and view streamed answers plus sources. Uses the same client protocol and message types as the TUI; no server or protocol changes.
- Users can choose to interact via **GUI or TUI**; both are supported. The server is assumed to be already running (started separately); the GUI does not start or manage the server.
- **No chat history** in the first version (session-only); history can be added later.

No breaking changes to existing CLI, server, or config format.

## Capabilities

### New Capabilities

- **gui-client**: Cross-platform GUI application for configuration editing and Q&A chat. Covers: reading/writing `~/.md-qa` config, connecting to the WebSocket server on startup, sending queries and displaying streamed answers and sources, and optional index selection. Does not include server lifecycle or chat history.

### Modified Capabilities

- None. Server, protocol, and config semantics stay as-is; the GUI is a new client front-end.

## Impact

- **New code**: GUI entrypoint and UI layer (e.g. `markdown_qa.gui` or similar). Reuses existing `MarkdownQAClient`, `APIConfig`, `ServerConfig`, and message types; GUI only adds a different presentation (forms + chat panel).
- **Dependencies**: New GUI framework dependency (e.g. PyQt6, PySide6, or CustomTkinter) and possibly packaging tooling for cross-platform distribution.
- **Documentation**: README and usage docs updated to describe GUI vs TUI and how to launch the GUI.
- **Testing**: Tests for config read/write from the GUI and for chat flow (e.g. connection, send query, receive stream) where feasible; may rely on integration tests or manual QA for full UI.
