//! Integration tests for the md-qa TUI binary (task 4.1).
//! Uses assert_cmd to run the binary, a real temp config, and an in-process
//! WebSocket server. No mocks. Tests should fail until task 4.2 implementation.

use assert_cmd::cargo::cargo_bin_cmd;
use assert_cmd::Command;
use predicates::prelude::*;
use std::io::Write as _;
use std::net::TcpListener as StdTcpListener;

/// Pick a free port by binding to :0 and extracting the assigned port.
fn free_port() -> u16 {
    let listener = StdTcpListener::bind("127.0.0.1:0").unwrap();
    listener.local_addr().unwrap().port()
}

/// Write a minimal YAML config to a temp file pointing at `port`.
fn write_config(dir: &tempfile::TempDir, port: u16) -> std::path::PathBuf {
    let path = dir.path().join("config.yaml");
    let mut f = std::fs::File::create(&path).unwrap();
    writeln!(
        f,
        "api:\n  base_url: http://localhost\nserver:\n  port: {}\n  index_name: default",
        port
    )
    .unwrap();
    path
}

/// Spawn a minimal WebSocket server that, for each connection, waits for one
/// message then replies with STREAM_START, one STREAM_CHUNK, and STREAM_END.
/// Returns a join handle; drops the listener when the handle is dropped.
fn spawn_test_server(port: u16) -> std::thread::JoinHandle<()> {
    std::thread::spawn(move || {
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .unwrap();
        rt.block_on(async {
            let listener = tokio::net::TcpListener::bind(format!("127.0.0.1:{}", port))
                .await
                .unwrap();

            // Accept one connection (the binary under test).
            let (tcp, _) = listener.accept().await.unwrap();
            let ws = tokio_tungstenite::accept_async(tcp).await.unwrap();
            let (mut write, mut read) = ws.split();

            // Wait for the query message.
            use futures_util::StreamExt;
            let _ = read.next().await;

            // Send streamed response.
            use futures_util::SinkExt;
            use tokio_tungstenite::tungstenite::Message;
            write
                .send(Message::Text(r#"{"type":"stream_start"}"#.into()))
                .await
                .unwrap();
            write
                .send(Message::Text(
                    r#"{"type":"stream_chunk","chunk":"Test answer."}"#.into(),
                ))
                .await
                .unwrap();
            write
                .send(Message::Text(
                    r#"{"type":"stream_end","sources":["/docs/a.md","/docs/b.md"]}"#.into(),
                ))
                .await
                .unwrap();

            // Small delay so the client can read before we drop.
            tokio::time::sleep(std::time::Duration::from_millis(200)).await;
        });
    })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[test]
fn tui_prints_streamed_answer_and_sources() {
    let port = free_port();
    let dir = tempfile::tempdir().unwrap();
    let config_path = write_config(&dir, port);

    // Start the test WebSocket server on the chosen port.
    let _server = spawn_test_server(port);

    // Give server a moment to bind.
    std::thread::sleep(std::time::Duration::from_millis(100));

    // Run the binary, passing the config path and a question on stdin.
    let mut cmd = Command::from(cargo_bin_cmd!("md-qa"));
    cmd.arg("--config")
        .arg(&config_path)
        .write_stdin("What is the answer?\n");

    cmd.assert()
        .success()
        .stdout(predicate::str::contains("Test answer."))
        .stdout(predicate::str::contains("/docs/a.md"))
        .stdout(predicate::str::contains("/docs/b.md"));
}

#[test]
fn tui_with_config_env_var() {
    let port = free_port();
    let dir = tempfile::tempdir().unwrap();
    let config_path = write_config(&dir, port);

    let _server = spawn_test_server(port);
    std::thread::sleep(std::time::Duration::from_millis(100));

    // Use MD_QA_CONFIG env var instead of --config flag.
    let mut cmd = Command::from(cargo_bin_cmd!("md-qa"));
    cmd.env("MD_QA_CONFIG", &config_path)
        .write_stdin("What is the answer?\n");

    cmd.assert()
        .success()
        .stdout(predicate::str::contains("Test answer."));
}

#[test]
fn tui_with_positional_question_argument() {
    let port = free_port();
    let dir = tempfile::tempdir().unwrap();
    let config_path = write_config(&dir, port);

    let _server = spawn_test_server(port);
    std::thread::sleep(std::time::Duration::from_millis(100));

    // Provide question as a positional argument (no stdin piping).
    let mut cmd = Command::from(cargo_bin_cmd!("md-qa"));
    cmd.arg("--config")
        .arg(&config_path)
        .arg("What is the answer?");

    cmd.assert()
        .success()
        .stdout(predicate::str::contains("Test answer."));
}

#[test]
fn tui_server_down_shows_error() {
    // Point the config at a port where nothing is listening.
    let port = free_port();
    let dir = tempfile::tempdir().unwrap();
    let config_path = write_config(&dir, port);

    let mut cmd = Command::from(cargo_bin_cmd!("md-qa"));
    cmd.arg("--config")
        .arg(&config_path)
        .write_stdin("hello\n");

    // The binary should exit with a non-zero code and print an error.
    cmd.assert()
        .failure()
        .stderr(predicate::str::is_match("(?i)(connect|error|refused|disconnected)").unwrap());
}
