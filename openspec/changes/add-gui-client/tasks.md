## 1. Protocol and project setup

- [x] 1.1 Document WebSocket protocol (message types, stream phases, config schema) in a single spec used by Python server and Rust client
- [x] 1.2 Create Rust workspace with shared client library crate and Tauri app crate
- [x] 1.3 Add dependencies: tokio, tokio-tungstenite, serde, serde_yaml; Tauri dependencies for app crate

## 2. Rust client library — config

- [x] 2.1 Add integration tests: config load from a real file in a temp dir (YAML), config save creates directory and file when missing, round-trip preserves schema (api.base_url, api.api_key, server.port, server.directories, etc.); use predicates for assertions; run tests and confirm they fail
- [x] 2.2 Implement config types (API and server sections) with serde for YAML; resolve `~/.md-qa/config.yaml` per platform
- [x] 2.3 Implement config load and save to make config tests pass

## 3. Rust client library — WebSocket and messages

- [x] 3.1 Add integration tests: connect to a real WebSocket server (e.g. existing Python server or minimal test server), send query message, assert received stream (STREAM_START, STREAM_CHUNK, STREAM_END) and sources; test error message handling; no mocks; run tests and confirm they fail
- [x] 3.2 Define message types (query, stream start/chunk/end, error, response) matching protocol spec
- [x] 3.3 Implement async WebSocket connect and send query / handle streamed responses to make WebSocket tests pass

## 4. Rust TUI binary

- [x] 4.1 Add tests with assert_cmd: run TUI binary with config path (env or flag) pointing to temp config; feed query via stdin (or script); assert stdout contains streamed answer and sources using predicates; run with server down and assert disconnected behavior; confirm tests fail before implementation
- [x] 4.2 Implement Rust TUI binary using shared client library; read config for server URL and index; connect, send input as query, print stream then sources
- [x] 4.3 Document and deprecate Python markdown_qa.client (TUI); point users to Rust TUI binary

## 5. Tauri app and config UI

- [x] 5.1 Add tests for config UI backend: load config from real path (temp dir), save creates dir/file, form values round-trip; use predicates; confirm tests fail
- [x] 5.2 Create Tauri app shell (desktop-only, no mobile entry point); integrate shared Rust client library; load config at startup
- [x] 5.3 Build config form: API base URL, API key (masked), embedding model, LLM model, server port, index name, reload interval; add directories list with add/remove; implement Save to `~/.md-qa/config.yaml` (create dir if missing) and make config tests pass

## 6. Connection and status

- [x] 6.1 Add tests: with server not running, assert UI shows disconnected/error and chat disabled or marked; with server running, assert connected status; use integration test or controlled run (e.g. config pointing to port); confirm tests fail
- [x] 6.2 Implement connect on GUI startup; show connection status (connected / disconnected / error); disable or mark chat when disconnected
- [x] 6.3 Add Reconnect action (one attempt on user click for v1) and ensure tests pass

## 7. Chat panel

- [x] 7.1 Add tests: submit question when connected, assert reply area receives streamed chunks and then sources (e.g. via backend integration test or e2e with real server); assert error message displayed on server error; no mocks; confirm tests fail
- [x] 7.2 Implement chat panel: input and send, query message with index from config; display streamed chunks and sources on STREAM_END; display server errors and remain connected
- [x] 7.3 Verify all chat tests pass

## 8. Cross-platform and documentation

- [x] 8.1 Add tests for config path: resolve `~/.md-qa` on current platform (or use temp home env); run on Windows, macOS, Linux in CI; confirm behavior
- [x] 8.2 Update README: how to run GUI vs TUI, launch commands, and that server must be started separately
- [x] 8.3 Add CI for Rust client and Tauri build; run test suite (optional: per-platform installer tasks deferred)
