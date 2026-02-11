//! WebSocket message types matching docs/protocol.md. Client ↔ server JSON.

use serde::{Deserialize, Serialize};

/// Client → server: query message.
#[derive(Debug, Clone, Serialize)]
pub struct QueryMessage<'a> {
    #[serde(rename = "type")]
    pub typ: &'static str,
    pub question: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub index: Option<&'a str>,
}

impl<'a> QueryMessage<'a> {
    pub fn new(question: &'a str, index: Option<&'a str>) -> Self {
        Self {
            typ: "query",
            question,
            index,
        }
    }
}

/// Server → client: stream chunk.
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct StreamChunkMessage {
    pub chunk: String,
}

/// Server → client: stream end with sources.
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct StreamEndMessage {
    pub sources: Vec<String>,
}

/// Server → client: error.
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct ErrorMessage {
    pub message: String,
}

/// Server → client: status response.
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct StatusMessage {
    pub status: String,
    #[serde(default)]
    pub message: Option<String>,
}

/// Server → client: non-streaming response (optional).
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct ResponseMessage {
    pub answer: String,
    pub sources: Vec<serde_json::Value>,
}

/// One server message; discriminator is JSON "type" field.
#[derive(Debug, Clone)]
pub enum ServerMessage {
    StreamStart,
    StreamChunk(String),
    StreamEnd(Vec<String>),
    Error(String),
    Status { status: String, message: Option<String> },
    Response { answer: String, sources: Vec<serde_json::Value> },
}

impl ServerMessage {
    pub fn from_json(value: &serde_json::Value) -> Result<Self, String> {
        let typ = value
            .get("type")
            .and_then(|t| t.as_str())
            .ok_or("missing type")?;
        match typ {
            "stream_start" => Ok(ServerMessage::StreamStart),
            "stream_chunk" => {
                let m: StreamChunkMessage =
                    serde_json::from_value(value.clone()).map_err(|e| e.to_string())?;
                Ok(ServerMessage::StreamChunk(m.chunk))
            }
            "stream_end" => {
                let m: StreamEndMessage =
                    serde_json::from_value(value.clone()).map_err(|e| e.to_string())?;
                Ok(ServerMessage::StreamEnd(m.sources))
            }
            "error" => {
                let m: ErrorMessage =
                    serde_json::from_value(value.clone()).map_err(|e| e.to_string())?;
                Ok(ServerMessage::Error(m.message))
            }
            "status" => {
                let m: StatusMessage =
                    serde_json::from_value(value.clone()).map_err(|e| e.to_string())?;
                Ok(ServerMessage::Status {
                    status: m.status,
                    message: m.message,
                })
            }
            "response" => {
                let m: ResponseMessage =
                    serde_json::from_value(value.clone()).map_err(|e| e.to_string())?;
                Ok(ServerMessage::Response {
                    answer: m.answer,
                    sources: m.sources,
                })
            }
            _ => Err(format!("unknown type: {}", typ)),
        }
    }
}
