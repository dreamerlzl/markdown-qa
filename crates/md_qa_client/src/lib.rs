//! Shared Markdown Q&A client library (config, WebSocket protocol, stream handling).
//! Used by the Tauri GUI and the Rust TUI.

pub mod client;
pub mod config;
pub mod messages;

pub use client::{connect, Client, ClientError, StreamEvent};
pub use config::{default_config_path, ApiSection, Config, ConfigError, ServerSection};
