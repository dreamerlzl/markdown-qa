# Spec: GUI Client

## ADDED Requirements

### Requirement: Config file read and write
The GUI client SHALL read and write the same configuration file used by the server and TUI client: `~/.md-qa/config.yaml` only. The client SHALL not read or write TOML; YAML is the single supported format for the GUI and Rust TUI.

#### Scenario: Load existing YAML config at startup
- **WHEN** the user opens the GUI and a YAML config exists at `~/.md-qa/config.yaml`
- **THEN** the GUI loads and displays all configured fields (API base URL, API key, embedding model, LLM model, server port, directories, reload interval, index name)
- **AND** the user can edit and save; the file remains YAML

#### Scenario: Create config directory and file if missing
- **WHEN** the user opens the GUI and `~/.md-qa` or `config.yaml` does not exist
- **THEN** the client SHALL create the directory and `config.yaml` when the user saves
- **AND** the created file SHALL be valid YAML with the same schema the server expects

### Requirement: Config form fields
The GUI SHALL provide editable fields for: API base URL, API key (masked), embedding model, LLM model, server port, list of markdown directories (with add/remove), reload interval, and index name. Values SHALL be read from the config file at startup and written back on user-initiated save.

#### Scenario: Edit and save API and server settings
- **WHEN** the user edits API base URL, API key, port, or other config fields and clicks Save
- **THEN** the client writes the updated values to the config file at `~/.md-qa/`
- **AND** the written structure SHALL match the schema expected by the server (e.g. `api.base_url`, `api.api_key`, `server.port`, `server.directories`, etc.)

#### Scenario: Add and remove directories
- **WHEN** the user adds a directory (e.g. via a directory picker) or removes one from the list
- **THEN** the updated directories list SHALL be persisted on save
- **AND** the server and TUI client can read the same config without change

### Requirement: Connect to server on startup
The GUI client SHALL attempt to connect to the WebSocket server on application startup using the server URL derived from config (e.g. `ws://localhost:{port}`). The client SHALL display connection status (connected, disconnected, or error). The chat panel SHALL be disabled or clearly marked when disconnected.

#### Scenario: Successful connection on startup
- **WHEN** the GUI starts and the server is running at the configured port
- **THEN** the client connects to the WebSocket server
- **AND** the UI shows a connected status
- **AND** the user can send queries in the chat panel

#### Scenario: Server not running on startup
- **WHEN** the GUI starts and the server is not running or not reachable
- **THEN** the client shows a disconnected or error status
- **AND** the chat panel is disabled or indicates that the user must start the server
- **AND** the client MAY offer a Reconnect action (one attempt on user action for v1)

### Requirement: Chat panel and streaming responses
The GUI SHALL provide a chat panel where the user can type a question and send it to the server. The client SHALL send queries using the same WebSocket protocol as the TUI (query message type, optional index field). The client SHALL display streamed answer chunks as they arrive and SHALL display sources when the stream ends (STREAM_END). Session-only chat (no persistent history) is acceptable for v1.

#### Scenario: Send question and display streamed answer
- **WHEN** the user is connected and submits a question in the chat panel
- **THEN** the client sends a query message to the server
- **AND** the client displays each streamed chunk in the reply area as it arrives
- **AND** when the stream ends the client displays the associated sources (e.g. file paths)

#### Scenario: Handle stream error
- **WHEN** the server returns an error message during a query or stream
- **THEN** the client SHALL display the error to the user in the chat UI
- **AND** the client remains connected for further queries where applicable

### Requirement: Index used for queries
The client SHALL use the single index name from config (`server.index_name`) when sending queries. The client MAY include this index name in the query message for protocol compatibility. The GUI SHALL NOT require an index selector in v1 because the server exposes only one loaded index.

#### Scenario: Query uses config index
- **WHEN** the user sends a question from the GUI
- **THEN** the client sends the query with the index name from config (or omits it if server uses default)
- **AND** the server responds using its single loaded index

### Requirement: Cross-platform support
The GUI client SHALL run on Windows, macOS, and Linux with the same behavior. Config path `~/.md-qa` SHALL be interpreted according to the platform (user home directory).

#### Scenario: Config path on each platform
- **WHEN** the client runs on Windows, macOS, or Linux
- **THEN** the client resolves `~/.md-qa` to the user's home directory and the appropriate path separator
- **AND** the config file is read and written at that location

### Requirement: No server lifecycle in GUI
The GUI client SHALL NOT start, stop, or manage the server process. The server is assumed to be already running; the client only connects as a WebSocket client.

#### Scenario: GUI does not start server
- **WHEN** the user opens the GUI
- **THEN** the client does not spawn or control the server process
- **AND** if the server is not running, the client only shows connection status and does not attempt to start it
