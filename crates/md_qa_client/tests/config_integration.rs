//! Integration tests for config load/save. Run with `cargo test`; they fail until task 2.3.

use md_qa_client::{config, Config};
use predicates::prelude::*;

#[test]
fn load_existing_yaml_config() {
    let dir = tempfile::tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    std::fs::write(
        &config_path,
        r#"
api:
  base_url: "https://api.example.com/v1"
  api_key: "test-key"
  embedding_model: "text-embedding-3-small"
  llm_model: "qwen-flash"
server:
  port: 8765
  directories:
    - "/path/to/docs"
  reload_interval: 300
  index_name: "default"
"#,
    )
    .unwrap();

    let result = config::load(&config_path);
    let cfg = result.expect("load should succeed");
    assert_eq!(
        cfg.api.base_url.as_deref(),
        Some("https://api.example.com/v1")
    );
    assert_eq!(cfg.api.api_key.as_deref(), Some("test-key"));
    assert_eq!(
        cfg.api.embedding_model.as_deref(),
        Some("text-embedding-3-small")
    );
    assert_eq!(cfg.api.llm_model.as_deref(), Some("qwen-flash"));
    assert_eq!(cfg.server.port, Some(8765));
    assert_eq!(cfg.server.directories, vec!["/path/to/docs"]);
    assert_eq!(cfg.server.reload_interval, Some(300));
    assert_eq!(cfg.server.index_name.as_deref(), Some("default"));
}

#[test]
fn save_creates_directory_and_file_when_missing() {
    let dir = tempfile::tempdir().unwrap();
    let config_dir = dir.path().join("md-qa");
    let config_path = config_dir.join("config.yaml");
    assert!(!config_dir.exists(), "config dir should not exist yet");

    let mut config = Config::default();
    config.api.base_url = Some("https://api.example.com".into());
    config.api.api_key = Some("key".into());
    config.server.port = Some(8766);
    config.server.directories = vec!["/docs".into()];
    config.server.reload_interval = Some(60);
    config.server.index_name = Some("default".into());

    let result = config::save(&config_path, &config);
    result.expect("save should succeed");
    let pred = predicates::path::exists();
    assert!(
        pred.eval(&config_path),
        "config file should exist after save"
    );
    assert!(config_dir.exists(), "config directory should be created");
}

#[test]
fn round_trip_preserves_schema() {
    let dir = tempfile::tempdir().unwrap();
    let config_path = dir.path().join("config.yaml");
    let yaml = r#"
api:
  base_url: "https://api.example.com/v1"
  api_key: "secret"
  embedding_model: "text-embedding-3-small"
  llm_model: "qwen-flash"
server:
  port: 8765
  directories:
    - "/a"
    - "/b"
  reload_interval: 300
  index_name: "myindex"
"#;
    std::fs::write(&config_path, yaml).unwrap();

    let loaded = config::load(&config_path).expect("load should succeed");
    config::save(&config_path, &loaded).expect("save should succeed");

    let contents = std::fs::read_to_string(&config_path).unwrap();
    let pred = predicates::str::contains("api:");
    assert!(
        pred.eval(&contents),
        "saved file should contain api section"
    );
    let pred = predicates::str::contains("base_url");
    assert!(pred.eval(&contents), "saved file should contain base_url");
    let pred = predicates::str::contains("server:");
    assert!(
        pred.eval(&contents),
        "saved file should contain server section"
    );
    let pred = predicates::str::contains("directories");
    assert!(
        pred.eval(&contents),
        "saved file should contain directories"
    );

    let reloaded = config::load(&config_path).expect("reload should succeed");
    assert_eq!(reloaded.api.base_url, loaded.api.base_url);
    assert_eq!(reloaded.api.api_key, loaded.api.api_key);
    assert_eq!(reloaded.server.port, loaded.server.port);
    assert_eq!(reloaded.server.directories, loaded.server.directories);
    assert_eq!(reloaded.server.index_name, loaded.server.index_name);
}

/// Config path resolves to `~/.md-qa/config.yaml` using the current platform's home dir.
/// We override the HOME env var to a temp dir to verify the resolution.
#[test]
fn default_config_path_uses_home_directory() {
    let dir = tempfile::tempdir().unwrap();
    let home = dir.path().to_str().unwrap().to_string();

    // Override HOME (Unix) / USERPROFILE (Windows) temporarily.
    let key = if cfg!(windows) { "USERPROFILE" } else { "HOME" };
    let original = std::env::var(key).ok();

    std::env::set_var(key, &home);
    let path = config::default_config_path();
    // Restore.
    match original {
        Some(v) => std::env::set_var(key, v),
        None => std::env::remove_var(key),
    }

    let path = path.expect("should resolve a config path");
    let expected = dir.path().join(".md-qa").join("config.yaml");
    assert_eq!(path, expected);
}
