//! WebSocket client: connect, send query, receive stream (STREAM_START, STREAM_CHUNK, STREAM_END).

use futures_util::{SinkExt, StreamExt};
use std::collections::HashSet;
use std::sync::Arc;
use tokio_tungstenite::tungstenite::Message;
use tokio_tungstenite::MaybeTlsStream;
use tokio_tungstenite::WebSocketStream;

use crate::messages::{QueryMessage, ServerMessage};

/// Events received during a query stream (see docs/protocol.md).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum StreamEvent {
    StreamStart,
    StreamChunk(String),
    StreamEnd(Vec<String>),
    Error(String),
}

type WsStream = WebSocketStream<MaybeTlsStream<tokio::net::TcpStream>>;

fn deduplicate_sources(sources: Vec<String>) -> Vec<String> {
    let mut seen = HashSet::new();
    let mut unique = Vec::new();
    for source in sources {
        if seen.insert(source.clone()) {
            unique.push(source);
        }
    }
    unique
}

/// Connected WebSocket client.
pub struct Client {
    inner: Arc<tokio::sync::Mutex<WsStream>>,
}

/// Client connection error.
#[derive(Debug)]
pub struct ClientError(pub String);

impl std::fmt::Display for ClientError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for ClientError {}

impl From<tokio_tungstenite::tungstenite::Error> for ClientError {
    fn from(e: tokio_tungstenite::tungstenite::Error) -> Self {
        ClientError(e.to_string())
    }
}

impl From<serde_json::Error> for ClientError {
    fn from(e: serde_json::Error) -> Self {
        ClientError(e.to_string())
    }
}

impl From<String> for ClientError {
    fn from(s: String) -> Self {
        ClientError(s)
    }
}

/// Connect to the WebSocket server at `url` (e.g. `ws://localhost:8765`).
pub async fn connect(url: &str) -> Result<Client, ClientError> {
    let (ws_stream, _) = tokio_tungstenite::connect_async(url).await?;
    Ok(Client {
        inner: Arc::new(tokio::sync::Mutex::new(ws_stream)),
    })
}

impl Client {
    /// Send a query and collect stream events until STREAM_END or ERROR.
    pub async fn query(
        &self,
        question: &str,
        index: Option<&str>,
    ) -> Result<Vec<StreamEvent>, ClientError> {
        let mut guard = self.inner.lock().await;
        let msg = QueryMessage::new(question, index);
        let json = serde_json::to_string(&msg).map_err(ClientError::from)?;
        guard.send(Message::Text(json)).await?;

        let mut events = Vec::new();
        while let Some(item) = guard.next().await {
            let message = item.map_err(|e| ClientError(e.to_string()))?;
            let text = match message {
                Message::Text(t) => t,
                Message::Close(_) => break,
                _ => continue,
            };
            let value: serde_json::Value =
                serde_json::from_str(&text).map_err(ClientError::from)?;
            let server_msg = ServerMessage::from_json(&value).map_err(ClientError::from)?;
            match server_msg {
                ServerMessage::StreamStart => events.push(StreamEvent::StreamStart),
                ServerMessage::StreamChunk(chunk) => events.push(StreamEvent::StreamChunk(chunk)),
                ServerMessage::StreamEnd(sources) => {
                    events.push(StreamEvent::StreamEnd(deduplicate_sources(sources)));
                    break;
                }
                ServerMessage::Error(message) => {
                    events.push(StreamEvent::Error(message));
                    break;
                }
                ServerMessage::Status { .. } | ServerMessage::Response { .. } => {}
            }
        }
        Ok(events)
    }
}
