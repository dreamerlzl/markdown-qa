//! Integration tests for chat backend (task 7.1).
//! Verifies send_query command returns streamed answer and sources from a real
//! WebSocket server, and that error messages are surfaced. No mocks.

use md_qa_gui_lib::commands::{do_connect, do_disconnect, do_send_query};

fn free_port() -> u16 {
    let l = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    l.local_addr().unwrap().port()
}

/// Spawn a test server that replies with STREAM_START, one chunk, and STREAM_END.
fn spawn_stream_server(port: u16) -> std::thread::JoinHandle<()> {
    std::thread::spawn(move || {
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .unwrap();
        rt.block_on(async {
            let listener = tokio::net::TcpListener::bind(format!("127.0.0.1:{}", port))
                .await
                .unwrap();
            let (tcp, _) = listener.accept().await.unwrap();
            let ws = tokio_tungstenite::accept_async(tcp).await.unwrap();
            let (mut write, mut read) = ws.split();

            use futures_util::{SinkExt, StreamExt};
            use tokio_tungstenite::tungstenite::Message;

            // Wait for query.
            let _ = read.next().await;

            write
                .send(Message::Text(r#"{"type":"stream_start"}"#.into()))
                .await
                .unwrap();
            write
                .send(Message::Text(
                    r#"{"type":"stream_chunk","chunk":"Hello "}"#.into(),
                ))
                .await
                .unwrap();
            write
                .send(Message::Text(
                    r#"{"type":"stream_chunk","chunk":"world!"}"#.into(),
                ))
                .await
                .unwrap();
            write
                .send(Message::Text(
                    r#"{"type":"stream_end","sources":["/x.md","/y.md"]}"#.into(),
                ))
                .await
                .unwrap();

            tokio::time::sleep(std::time::Duration::from_millis(200)).await;
        });
    })
}

/// Spawn a test server that replies with an error message.
fn spawn_error_server(port: u16) -> std::thread::JoinHandle<()> {
    std::thread::spawn(move || {
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .unwrap();
        rt.block_on(async {
            let listener = tokio::net::TcpListener::bind(format!("127.0.0.1:{}", port))
                .await
                .unwrap();
            let (tcp, _) = listener.accept().await.unwrap();
            let ws = tokio_tungstenite::accept_async(tcp).await.unwrap();
            let (mut write, mut read) = ws.split();

            use futures_util::{SinkExt, StreamExt};
            use tokio_tungstenite::tungstenite::Message;

            let _ = read.next().await;

            write
                .send(Message::Text(
                    r#"{"type":"error","message":"Index not ready"}"#.into(),
                ))
                .await
                .unwrap();

            tokio::time::sleep(std::time::Duration::from_millis(200)).await;
        });
    })
}

#[test]
fn chat_receives_streamed_answer_and_sources() {
    let port = free_port();
    let _server = spawn_stream_server(port);
    std::thread::sleep(std::time::Duration::from_millis(100));

    let url = format!("ws://127.0.0.1:{}", port);
    let status = do_connect(&url).unwrap();
    assert_eq!(status.state, "connected");

    let reply = do_send_query("What is this?", None).expect("query should succeed");

    assert_eq!(reply.answer, "Hello world!");
    assert_eq!(reply.sources, vec!["/x.md", "/y.md"]);
    assert!(reply.error.is_none());

    do_disconnect();
}

#[test]
fn chat_receives_error_message() {
    let port = free_port();
    let _server = spawn_error_server(port);
    std::thread::sleep(std::time::Duration::from_millis(100));

    let url = format!("ws://127.0.0.1:{}", port);
    let status = do_connect(&url).unwrap();
    assert_eq!(status.state, "connected");

    let reply = do_send_query("test", None).expect("query should succeed");

    assert!(reply.error.is_some());
    assert!(
        reply.error.as_deref().unwrap().contains("Index not ready"),
        "error should contain server message, got: {:?}",
        reply.error
    );

    do_disconnect();
}

#[test]
fn chat_query_when_not_connected_returns_error() {
    // Ensure disconnected state.
    do_disconnect();

    let result = do_send_query("test", None);
    assert!(result.is_err(), "should error when not connected");
}
