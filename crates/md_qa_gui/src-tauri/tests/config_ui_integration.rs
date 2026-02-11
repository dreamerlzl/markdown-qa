//! Integration tests for config UI backend (task 5.1).
//! Tests the Tauri command backend functions with real files in a temp dir.
//! No mocks. Should fail until task 5.3 completes the full config form.

use md_qa_gui_lib::commands::{do_load_config, do_save_config, ConfigForm};
use predicates::prelude::*;
use std::io::Write as _;

/// Load config from a real YAML file in a temp dir; verify all form fields populated.
#[test]
fn load_config_from_real_file() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("config.yaml");
    let mut f = std::fs::File::create(&path).unwrap();
    writeln!(
        f,
        r#"api:
  base_url: "https://api.example.com/v1"
  api_key: "sk-test-key"
  embedding_model: "text-embedding-3-small"
  llm_model: "gpt-4o-mini"
server:
  port: 9000
  directories:
    - /home/user/docs
    - /home/user/notes
  reload_interval: 600
  index_name: "my-index""#
    )
    .unwrap();

    let form = do_load_config(path.to_str().unwrap()).expect("load should succeed");

    assert_eq!(form.api_base_url, "https://api.example.com/v1");
    assert_eq!(form.api_key, "sk-test-key");
    assert_eq!(form.embedding_model, "text-embedding-3-small");
    assert_eq!(form.llm_model, "gpt-4o-mini");
    assert_eq!(form.server_port, 9000);
    assert_eq!(form.directories, vec!["/home/user/docs", "/home/user/notes"]);
    assert_eq!(form.reload_interval, 600);
    assert_eq!(form.index_name, "my-index");
}

/// Save config creates directory and file when both are missing.
#[test]
fn save_creates_directory_and_file() {
    let dir = tempfile::tempdir().unwrap();
    let nested = dir.path().join("new-dir").join("config.yaml");

    // Directory doesn't exist yet.
    let parent_exists = predicate::path::exists();
    assert!(!parent_exists.eval(nested.parent().unwrap()));

    let form = ConfigForm {
        api_base_url: "https://api.test.com".into(),
        api_key: "key-123".into(),
        embedding_model: "embed".into(),
        llm_model: "llm".into(),
        server_port: 7777,
        directories: vec!["/tmp/docs".into()],
        reload_interval: 120,
        index_name: "idx".into(),
    };

    do_save_config(nested.to_str().unwrap(), &form).expect("save should succeed");

    // File should now exist.
    assert!(parent_exists.eval(nested.as_path()));
    let contents = std::fs::read_to_string(&nested).unwrap();
    assert!(predicate::str::contains("api_key").eval(&contents) || predicate::str::contains("key-123").eval(&contents));
}

/// Round-trip: save then load preserves all form field values.
#[test]
fn round_trip_preserves_form_values() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("config.yaml");

    let original = ConfigForm {
        api_base_url: "https://round.trip/v1".into(),
        api_key: "rt-key".into(),
        embedding_model: "rt-embed".into(),
        llm_model: "rt-llm".into(),
        server_port: 4321,
        directories: vec!["/a".into(), "/b".into(), "/c".into()],
        reload_interval: 999,
        index_name: "rt-index".into(),
    };

    do_save_config(path.to_str().unwrap(), &original).expect("save should succeed");
    let loaded = do_load_config(path.to_str().unwrap()).expect("load should succeed");

    assert_eq!(loaded, original);
}

/// Load from non-existent file returns an error (not a panic).
#[test]
fn load_missing_file_returns_error() {
    let result = do_load_config("/tmp/does-not-exist-ever/config.yaml");
    assert!(result.is_err());
    let err = result.unwrap_err();
    assert!(predicate::str::is_match("(?i)(io|error|no such)").unwrap().eval(&err));
}
