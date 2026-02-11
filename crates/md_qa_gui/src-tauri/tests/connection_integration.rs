//! Integration tests for connection status backend (task 6.1).
//! Tests that the GUI backend correctly reports connected / disconnected / error
//! states against a real (or absent) WebSocket server. No mocks.

use md_qa_gui_lib::commands::{do_connect, do_disconnect};

/// Start a minimal test WebSocket server on `port`, accepting one connection.
fn spawn_ws_server(port: u16) -> std::thread::JoinHandle<()> {
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
            let _ws = tokio_tungstenite::accept_async(tcp).await.unwrap();
            // Keep the connection open long enough for the test.
            tokio::time::sleep(std::time::Duration::from_secs(2)).await;
        });
    })
}

fn free_port() -> u16 {
    let l = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    l.local_addr().unwrap().port()
}

#[test]
fn connect_to_running_server_reports_connected() {
    let port = free_port();
    let _server = spawn_ws_server(port);
    std::thread::sleep(std::time::Duration::from_millis(100));

    let url = format!("ws://127.0.0.1:{}", port);
    let status = do_connect(&url).expect("do_connect should not panic");

    assert_eq!(status.state, "connected");
    assert!(status.message.is_none() || status.message.as_deref() == Some(""));

    // Cleanup
    do_disconnect();
}

#[test]
fn connect_to_absent_server_reports_error() {
    let port = free_port();
    // No server started on this port.
    let url = format!("ws://127.0.0.1:{}", port);
    let status = do_connect(&url).expect("do_connect should not panic");

    assert!(
        status.state == "disconnected" || status.state == "error",
        "expected disconnected or error, got: {}",
        status.state
    );
    assert!(status.message.is_some(), "error message should be set");
}

#[test]
fn disconnect_when_not_connected_is_safe() {
    // Should not panic or error.
    do_disconnect();
}

#[test]
fn connection_status_after_disconnect() {
    let port = free_port();
    let _server = spawn_ws_server(port);
    std::thread::sleep(std::time::Duration::from_millis(100));

    let url = format!("ws://127.0.0.1:{}", port);
    let status = do_connect(&url).unwrap();
    assert_eq!(status.state, "connected");

    do_disconnect();
    // After disconnect, a new connect to a dead port should fail
    let port2 = free_port();
    let url2 = format!("ws://127.0.0.1:{}", port2);
    let status2 = do_connect(&url2).unwrap();
    assert!(status2.state == "disconnected" || status2.state == "error");
}
