//! Integration tests for WebSocket client: connect, send query, receive stream.
//! Uses a minimal in-process WebSocket server (no mocks). Fail until task 3.3.

use md_qa_client::{connect, Client, StreamEvent};
use std::sync::atomic::{AtomicBool, Ordering};
use tokio::net::TcpListener;
use tokio_tungstenite::accept_async;

#[tokio::test]
async fn connect_and_receive_stream() {
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();
    let done = std::sync::Arc::new(AtomicBool::new(false));
    let done_clone = done.clone();
    tokio::spawn(async move {
        let (tcp_stream, _) = listener.accept().await.unwrap();
        let ws_stream = accept_async(tcp_stream).await.unwrap();
        let (mut write, mut read) = ws_stream.split();
        let _ = read.next().await;
        let stream_start = r#"{"type":"stream_start"}"#;
        let stream_chunk = r#"{"type":"stream_chunk","chunk":"Hello."}"#;
        let stream_end = r#"{"type":"stream_end","sources":["/a.md","/b.md"]}"#;
        use futures_util::SinkExt;
        use futures_util::StreamExt;
        write
            .send(tokio_tungstenite::tungstenite::Message::Text(stream_start.into()))
            .await
            .unwrap();
        write
            .send(tokio_tungstenite::tungstenite::Message::Text(stream_chunk.into()))
            .await
            .unwrap();
        write
            .send(tokio_tungstenite::tungstenite::Message::Text(stream_end.into()))
            .await
            .unwrap();
        done_clone.store(true, Ordering::SeqCst);
    });

    let url = format!("ws://127.0.0.1:{}", port);
    let client = connect(&url).await.expect("connect should succeed");
    let events = client
        .query("What is the answer?", None)
        .await
        .expect("query should succeed");

    assert!(!events.is_empty());
    assert_eq!(events[0], StreamEvent::StreamStart);
    let chunks: Vec<String> = events
        .iter()
        .filter_map(|e| {
            if let StreamEvent::StreamChunk(s) = e {
                Some(s.clone())
            } else {
                None
            }
        })
        .collect();
    assert!(!chunks.is_empty());
    assert_eq!(chunks.join(""), "Hello.");
    let end_events: Vec<_> = events
        .iter()
        .filter(|e| matches!(e, StreamEvent::StreamEnd(_)))
        .collect();
    assert_eq!(end_events.len(), 1);
    if let StreamEvent::StreamEnd(sources) = &end_events[0] {
        assert_eq!(sources.as_slice(), ["/a.md", "/b.md"]);
    }
}

#[tokio::test]
async fn receive_error_message() {
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();
    let done = std::sync::Arc::new(AtomicBool::new(false));
    let done_clone = done.clone();
    tokio::spawn(async move {
        let (tcp_stream, _) = listener.accept().await.unwrap();
        let ws_stream = accept_async(tcp_stream).await.unwrap();
        let (mut write, mut read) = ws_stream.split();
        let _ = read.next().await;
        let err_msg = r#"{"type":"error","message":"Server not ready."}"#;
        use futures_util::SinkExt;
        use futures_util::StreamExt;
        write
            .send(tokio_tungstenite::tungstenite::Message::Text(err_msg.into()))
            .await
            .unwrap();
        done_clone.store(true, Ordering::SeqCst);
    });

    let url = format!("ws://127.0.0.1:{}", port);
    let client = connect(&url).await.expect("connect should succeed");
    let events = client
        .query("question", None)
        .await
        .expect("query should succeed");

    let err_events: Vec<_> = events
        .iter()
        .filter_map(|e| {
            if let StreamEvent::Error(s) = e {
                Some(s.as_str())
            } else {
                None
            }
        })
        .collect();
    assert_eq!(err_events.len(), 1);
    assert_eq!(err_events[0], "Server not ready.");
}
