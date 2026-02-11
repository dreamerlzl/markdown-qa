//! Tauri commands for config load/save and WebSocket connection management.
//! The Tauri `#[command]` wrappers delegate to testable plain functions.

use md_qa_client::config::{self, ApiSection, Config, ServerSection};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::sync::Mutex;

// ── Global runtime and connection state (single connection for the GUI) ─
use std::sync::OnceLock;

fn global_runtime() -> &'static tokio::runtime::Runtime {
    static RT: OnceLock<tokio::runtime::Runtime> = OnceLock::new();
    RT.get_or_init(|| {
        tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .expect("failed to create tokio runtime")
    })
}

static CONNECTION: Mutex<Option<md_qa_client::Client>> = Mutex::new(None);

/// JSON-friendly config form values sent to/from the frontend.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ConfigForm {
    pub api_base_url: String,
    pub api_key: String,
    pub embedding_model: String,
    pub llm_model: String,
    pub server_port: u16,
    pub directories: Vec<String>,
    pub reload_interval: u64,
    pub index_name: String,
}

impl Default for ConfigForm {
    fn default() -> Self {
        Self {
            api_base_url: String::new(),
            api_key: String::new(),
            embedding_model: String::new(),
            llm_model: String::new(),
            server_port: 8765,
            directories: Vec::new(),
            reload_interval: 300,
            index_name: "default".into(),
        }
    }
}

impl From<Config> for ConfigForm {
    fn from(c: Config) -> Self {
        Self {
            api_base_url: c.api.base_url.unwrap_or_default(),
            api_key: c.api.api_key.unwrap_or_default(),
            embedding_model: c.api.embedding_model.unwrap_or_default(),
            llm_model: c.api.llm_model.unwrap_or_default(),
            server_port: c.server.port.unwrap_or(8765),
            directories: c.server.directories,
            reload_interval: c.server.reload_interval.unwrap_or(300),
            index_name: c.server.index_name.unwrap_or_else(|| "default".into()),
        }
    }
}

impl From<ConfigForm> for Config {
    fn from(f: ConfigForm) -> Self {
        Config {
            api: ApiSection {
                base_url: Some(f.api_base_url),
                api_key: Some(f.api_key),
                embedding_model: Some(f.embedding_model),
                llm_model: Some(f.llm_model),
            },
            server: ServerSection {
                port: Some(f.server_port),
                directories: f.directories,
                reload_interval: Some(f.reload_interval),
                index_name: Some(f.index_name),
            },
        }
    }
}

/// Resolve config path from optional override, env, or default.
pub fn resolve_config_path(override_path: Option<&str>) -> Result<PathBuf, String> {
    if let Some(p) = override_path {
        return Ok(PathBuf::from(p));
    }
    if let Ok(val) = std::env::var("MD_QA_CONFIG") {
        return Ok(PathBuf::from(val));
    }
    config::default_config_path().ok_or_else(|| "Cannot determine config path".into())
}

// ── Testable backend functions ──────────────────────────────────────────

/// Load config from `path` and return form values.
pub fn do_load_config(path: &str) -> Result<ConfigForm, String> {
    let cfg = config::load(std::path::Path::new(path)).map_err(|e| e.to_string())?;
    Ok(ConfigForm::from(cfg))
}

/// Save form values to `path` as YAML. Creates parent dirs if needed.
pub fn do_save_config(path: &str, form: &ConfigForm) -> Result<(), String> {
    let cfg: Config = form.clone().into();
    config::save(std::path::Path::new(path), &cfg).map_err(|e| e.to_string())
}

// ── Connection status ───────────────────────────────────────────────

/// Connection status returned to the frontend.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ConnectionStatus {
    /// "connected", "disconnected", or "error"
    pub state: String,
    /// Error message when state is "error" or "disconnected".
    pub message: Option<String>,
}

/// Attempt to connect to the WebSocket server at `url`.
/// Returns a `ConnectionStatus` (never an Err — connection failure is reported in the status).
pub fn do_connect(url: &str) -> Result<ConnectionStatus, String> {
    let rt = global_runtime();
    let result = rt.block_on(md_qa_client::connect(url));

    match result {
        Ok(client) => {
            let mut guard = CONNECTION.lock().map_err(|e| e.to_string())?;
            *guard = Some(client);
            Ok(ConnectionStatus {
                state: "connected".into(),
                message: None,
            })
        }
        Err(e) => Ok(ConnectionStatus {
            state: "disconnected".into(),
            message: Some(e.to_string()),
        }),
    }
}

/// Disconnect the current WebSocket connection (if any). Safe to call when not connected.
pub fn do_disconnect() {
    if let Ok(mut guard) = CONNECTION.lock() {
        *guard = None;
    }
}

/// Check if a connection is currently held.
pub fn is_connected() -> bool {
    CONNECTION
        .lock()
        .map(|g| g.is_some())
        .unwrap_or(false)
}

// ── Chat query ──────────────────────────────────────────────────────────

/// Result of a chat query returned to the frontend.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ChatReply {
    /// Full assembled answer text (all stream chunks concatenated).
    pub answer: String,
    /// Source file paths returned with STREAM_END.
    pub sources: Vec<String>,
    /// Error message from the server, if any.
    pub error: Option<String>,
}

/// Send a query over the current connection. Returns the assembled reply.
pub fn do_send_query(question: &str, index: Option<&str>) -> Result<ChatReply, String> {
    let mut guard = CONNECTION.lock().map_err(|e| e.to_string())?;
    let client = guard.as_mut().ok_or("Not connected")?;

    let rt = global_runtime();
    let events = rt.block_on(client.query(question, index)).map_err(|e| e.to_string())?;

    let mut answer = String::new();
    let mut sources = Vec::new();
    let mut error = None;

    for event in events {
        match event {
            md_qa_client::StreamEvent::StreamStart => {}
            md_qa_client::StreamEvent::StreamChunk(chunk) => answer.push_str(&chunk),
            md_qa_client::StreamEvent::StreamEnd(srcs) => sources = srcs,
            md_qa_client::StreamEvent::Error(msg) => error = Some(msg),
        }
    }

    Ok(ChatReply {
        answer,
        sources,
        error,
    })
}

// ── Tauri command wrappers ──────────────────────────────────────────────

#[tauri::command]
pub fn get_config_path() -> Result<String, String> {
    let p = resolve_config_path(None)?;
    p.to_str()
        .map(|s| s.to_string())
        .ok_or_else(|| "Config path is not valid UTF-8".into())
}

#[tauri::command]
pub fn load_config(path: String) -> Result<ConfigForm, String> {
    do_load_config(&path)
}

#[tauri::command]
pub fn save_config(path: String, form: ConfigForm) -> Result<(), String> {
    do_save_config(&path, &form)
}

#[tauri::command]
pub fn connect_server(url: String) -> Result<ConnectionStatus, String> {
    do_connect(&url)
}

#[tauri::command]
pub fn disconnect_server() -> Result<(), String> {
    do_disconnect();
    Ok(())
}

#[tauri::command]
pub fn send_query(question: String, index: Option<String>) -> Result<ChatReply, String> {
    do_send_query(&question, index.as_deref())
}

#[tauri::command]
pub fn connection_status() -> ConnectionStatus {
    if is_connected() {
        ConnectionStatus {
            state: "connected".into(),
            message: None,
        }
    } else {
        ConnectionStatus {
            state: "disconnected".into(),
            message: None,
        }
    }
}
