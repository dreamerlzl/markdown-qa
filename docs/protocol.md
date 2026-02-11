# Markdown Q&A WebSocket Protocol and Config Schema

This document is the single source of truth for the WebSocket message protocol and client config schema. The Python server and Rust client (GUI and TUI) both implement this spec. Any change to the protocol or config format is done here first, then in both codebases.

## Transport

- **Protocol:** WebSocket (JSON text frames).
- **Server:** Listens on a configurable port (default 8765). Client connects to `ws://localhost:{port}` (or configured host).
- **Encoding:** All messages are JSON objects with a `type` field. No binary frames.

## Message Types

### Client → Server

#### `query`

Sent by the client to ask a question. Server responds with a stream (see Stream phases below) or an `error` message.

| Field     | Type   | Required | Description                          |
|----------|--------|----------|--------------------------------------|
| `type`   | string | yes      | `"query"`                            |
| `question` | string | yes    | The question text. Must be non-empty after trim. |
| `index`  | string | no       | Optional index name. Server may ignore if it only has one index. |

**Validation (server):** `type` must be `"query"`, `question` must be present and a non-empty string after trim.

#### `status`

Client can request server readiness. Server responds with a single `status` message.

| Field | Type   | Required | Description   |
|-------|--------|----------|---------------|
| `type` | string | yes     | `"status"`   |

### Server → Client

#### `stream_start`

Marks the beginning of a streamed answer. No payload beyond `type`.

| Field | Type   | Required | Description        |
|-------|--------|----------|--------------------|
| `type` | string | yes     | `"stream_start"`  |

#### `stream_chunk`

A piece of the answer text. Client should append chunks in order until `stream_end`.

| Field  | Type   | Required | Description      |
|--------|--------|----------|------------------|
| `type`  | string | yes     | `"stream_chunk"` |
| `chunk` | string | yes     | Text fragment.   |

#### `stream_end`

Marks the end of the stream and carries source references.

| Field    | Type     | Required | Description                    |
|----------|----------|----------|--------------------------------|
| `type`   | string   | yes      | `"stream_end"`                 |
| `sources`| string[] | yes      | List of source file paths.     |

#### `error`

Indicates an error (e.g. invalid query, server not ready, processing failure). Connection remains open unless the error is fatal.

| Field     | Type   | Required | Description     |
|-----------|--------|----------|-----------------|
| `type`    | string | yes      | `"error"`       |
| `message` | string | yes      | Error message.  |

#### `status` (response)

Sent in reply to a client `status` request.

| Field     | Type   | Required | Description                                      |
|-----------|--------|----------|--------------------------------------------------|
| `type`    | string | yes      | `"status"`                                       |
| `status`  | string | yes      | One of: `"ready"`, `"indexing"`, `"not_ready"`.  |
| `message` | string | no       | Optional human-readable message.                 |

#### `response` (non-streaming)

Optional; used if the server ever returns a single full response instead of a stream. For the current server, answers are always streamed (`stream_start` → `stream_chunk`* → `stream_end`).

| Field    | Type   | Required | Description        |
|----------|--------|----------|--------------------|
| `type`   | string | yes      | `"response"`       |
| `answer` | string | yes      | Full answer text.  |
| `sources`| array  | yes      | List of source objects. |

## Stream Phases (Query Response)

For a valid `query` message, the server sends a sequence of messages:

1. **One** `stream_start`.
2. **Zero or more** `stream_chunk` messages (order preserved).
3. **One** `stream_end` with `sources`.

If an error occurs before or during the stream, the server sends a single `error` message instead (no stream). After sending the stream or an error, the server is ready for the next message.

## Config Schema (YAML)

The client (GUI and Tauri) reads and writes **YAML only** from `~/.md-qa/config.yaml`. The server may also support TOML; the Rust client does not. Path `~/.md-qa` is the user's home directory (platform-specific).

### Top-level structure

```yaml
api:
  base_url: string      # Required for server (LLM/embedding API)
  api_key: string       # Required for server
  embedding_model: string  # Optional, default e.g. "text-embedding-3-small"
  llm_model: string     # Optional, default e.g. "qwen-flash"

server:
  port: number          # WebSocket server port, default 8765
  directories: [string] # List of markdown root paths (or comma-separated string)
  reload_interval: number  # Seconds, default 300
  index_name: string    # Index name, default "default"
```

### Field summary

| Key | Section | Type | Default (if any) | Notes |
|-----|---------|------|------------------|--------|
| `base_url` | api | string | — | Required. |
| `api_key` | api | string | — | Required. |
| `embedding_model` | api | string | e.g. "text-embedding-3-small" | |
| `llm_model` | api | string | e.g. "qwen-flash" | |
| `port` | server | number | 8765 | 1–65535. |
| `directories` | server | list of strings or string | — | Comma-separated string is normalized to list. |
| `reload_interval` | server | number | 300 | Positive. |
| `index_name` | server | string | "default" | |

The Rust client uses this schema for load and save. The Python server reads the same structure from `api` and `server` (and supports TOML in addition to YAML).
