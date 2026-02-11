//! Client config load/save for `~/.md-qa/config.yaml`.
//! Schema matches docs/protocol.md (api.*, server.*).

use std::path::{Path, PathBuf};

/// API section (base_url, api_key, embedding_model, llm_model).
#[derive(Debug, Clone, Default, serde::Serialize, serde::Deserialize)]
pub struct ApiSection {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub base_url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub api_key: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embedding_model: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub llm_model: Option<String>,
}

/// Server section (port, directories, reload_interval, index_name).
#[derive(Debug, Clone, Default, serde::Serialize, serde::Deserialize)]
pub struct ServerSection {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub port: Option<u16>,
    #[serde(default)]
    pub directories: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reload_interval: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub index_name: Option<String>,
}

/// Full config matching docs/protocol.md schema.
#[derive(Debug, Clone, Default, serde::Serialize, serde::Deserialize)]
pub struct Config {
    #[serde(default)]
    pub api: ApiSection,
    #[serde(default)]
    pub server: ServerSection,
}

/// Returns the default config file path: `~/.md-qa/config.yaml` (platform-specific).
pub fn default_config_path() -> Option<PathBuf> {
    let home = home_dir()?;
    Some(home.join(".md-qa").join("config.yaml"))
}

#[cfg(unix)]
fn home_dir() -> Option<PathBuf> {
    std::env::var_os("HOME").map(PathBuf::from)
}

#[cfg(windows)]
fn home_dir() -> Option<PathBuf> {
    std::env::var_os("USERPROFILE").map(PathBuf::from)
}

#[cfg(not(any(unix, windows)))]
fn home_dir() -> Option<PathBuf> {
    None
}

/// Load config from a YAML file. Path is typically `~/.md-qa/config.yaml`.
pub fn load(path: &Path) -> Result<Config, ConfigError> {
    let contents = std::fs::read_to_string(path).map_err(|e| ConfigError::Io(e.to_string()))?;
    serde_yaml::from_str(&contents).map_err(|e| ConfigError::Io(e.to_string()))
}

/// Save config to a YAML file. Creates parent directory if missing.
pub fn save(path: &Path, config: &Config) -> Result<(), ConfigError> {
    if let Some(parent) = path.parent() {
        if !parent.exists() {
            std::fs::create_dir_all(parent).map_err(|e| ConfigError::Io(e.to_string()))?;
        }
    }
    let contents = serde_yaml::to_string(config).map_err(|e| ConfigError::Io(e.to_string()))?;
    std::fs::write(path, contents).map_err(|e| ConfigError::Io(e.to_string()))
}

/// Config load/save error.
#[derive(Debug)]
pub enum ConfigError {
    Io(String),
}

impl std::fmt::Display for ConfigError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ConfigError::Io(s) => write!(f, "IO error: {}", s),
        }
    }
}

impl std::error::Error for ConfigError {}
