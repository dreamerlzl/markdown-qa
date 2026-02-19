//! md-qa: Rust TUI binary for Markdown Q&A.
//! Loads config when available, connects to WebSocket server, sends a query
//! from a positional argument or stdin, and prints streamed answer/sources.

use md_qa_client::config;
use md_qa_client::StreamEvent;
use std::io::{self, BufRead, IsTerminal, Write};
use std::path::PathBuf;
use std::process;

#[derive(Debug, Clone, PartialEq, Eq)]
struct CliOptions {
    config_path: Option<PathBuf>,
    question: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum CliCommand {
    Run(CliOptions),
    PrintHelp { program_name: String },
    PrintVersion,
}

fn help_text(program_name: &str) -> String {
    format!(
        "md-qa: Rust TUI client for Markdown Q&A

Usage:
  {program_name} [OPTIONS] [QUESTION]

Options:
  -c, --config <PATH>  Optional config file path
  -h, --help           Print help and exit
  -V, --version        Print version and exit

Config:
  --config PATH (if set) takes highest priority.
  Otherwise MD_QA_CONFIG is used when set.
  Otherwise ~/.md-qa/config.yaml is used when it exists.
  If no config file is available, built-in defaults are used (port 8765).

Input:
  QUESTION: optional positional question to send.
  If QUESTION is omitted, reads one question from stdin (first line).
"
    )
}

fn parse_cli_command_from<I, S>(args: I) -> Result<CliCommand, String>
where
    I: IntoIterator<Item = S>,
    S: Into<String>,
{
    let mut args = args.into_iter().map(Into::into);
    let program_name = args.next().unwrap_or_else(|| "md-qa".to_string());
    let mut config_path: Option<PathBuf> = None;
    let mut question: Option<String> = None;

    while let Some(arg) = args.next() {
        match arg.as_str() {
            "-h" | "--help" => return Ok(CliCommand::PrintHelp { program_name }),
            "-V" | "--version" => return Ok(CliCommand::PrintVersion),
            "-c" | "--config" => {
                let value = args.next().ok_or_else(|| {
                    format!(
                        "Error: {arg} requires a value\n\n{}",
                        help_text(&program_name)
                    )
                })?;
                config_path = Some(PathBuf::from(value));
            }
            _ if arg.starts_with("--config=") => {
                let (_, value) = arg.split_once('=').expect("checked with starts_with");
                if value.is_empty() {
                    return Err(format!(
                        "Error: --config requires a value\n\n{}",
                        help_text(&program_name)
                    ));
                }
                config_path = Some(PathBuf::from(value));
            }
            _ if arg.starts_with('-') => {
                return Err(format!(
                    "Error: unknown option: {arg}\n\n{}",
                    help_text(&program_name)
                ));
            }
            _ => {
                if question.is_none() {
                    question = Some(arg);
                } else {
                    return Err(format!(
                        "Error: unexpected positional argument: {arg}\n\n{}",
                        help_text(&program_name)
                    ));
                }
            }
        }
    }

    Ok(CliCommand::Run(CliOptions {
        config_path,
        question,
    }))
}

fn parse_cli_command() -> Result<CliCommand, String> {
    parse_cli_command_from(std::env::args())
}

fn load_runtime_config(cli_override_path: Option<PathBuf>) -> Result<config::Config, String> {
    let env_path = std::env::var("MD_QA_CONFIG").ok().map(PathBuf::from);
    let default_path = config::default_config_path();
    load_runtime_config_from_paths(cli_override_path, env_path, default_path)
}

fn load_runtime_config_from_paths(
    cli_override_path: Option<PathBuf>,
    env_path: Option<PathBuf>,
    default_path: Option<PathBuf>,
) -> Result<config::Config, String> {
    if let Some(path) = cli_override_path {
        return config::load(&path).map_err(|e| {
            format!(
                "Error: failed to load config from {}: {}",
                path.display(),
                e
            )
        });
    }

    if let Some(path) = env_path {
        return config::load(&path).map_err(|e| {
            format!(
                "Error: failed to load config from {}: {}",
                path.display(),
                e
            )
        });
    }

    if let Some(path) = default_path {
        if path.exists() {
            return config::load(&path).map_err(|e| {
                format!(
                    "Error: failed to load config from {}: {}",
                    path.display(),
                    e
                )
            });
        }
    }

    Ok(config::Config::default())
}

fn main() {
    match parse_cli_command() {
        Ok(CliCommand::PrintHelp { program_name }) => {
            print!("{}", help_text(&program_name));
            return;
        }
        Ok(CliCommand::PrintVersion) => {
            println!("md-qa {}", env!("CARGO_PKG_VERSION"));
            return;
        }
        Ok(CliCommand::Run(cli_options)) => run(cli_options),
        Err(message) => {
            eprintln!("{message}");
            process::exit(2);
        }
    }
}

fn run(cli_options: CliOptions) {
    let cfg = match load_runtime_config(cli_options.config_path) {
        Ok(c) => c,
        Err(message) => {
            eprintln!("{message}");
            process::exit(1);
        }
    };

    let port = cfg.server.port.unwrap_or(8765);
    let server_url = format!("ws://127.0.0.1:{}", port);
    let index = cfg.server.index_name.as_deref();

    let question = read_question(cli_options.question);

    if question.is_empty() {
        eprintln!("Error: no question provided (pass QUESTION argument or stdin)");
        process::exit(1);
    }

    // Run the async query on a tokio runtime.
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .unwrap_or_else(|e| {
            eprintln!("Error: failed to create runtime: {}", e);
            process::exit(1);
        });

    rt.block_on(async {
        let client = match md_qa_client::connect(&server_url).await {
            Ok(c) => c,
            Err(e) => {
                eprintln!("Error: connection failed: {}", e);
                process::exit(1);
            }
        };

        let events = match client.query(&question, index).await {
            Ok(ev) => ev,
            Err(e) => {
                eprintln!("Error: query failed: {}", e);
                process::exit(1);
            }
        };

        let stdout = io::stdout();
        let mut out = stdout.lock();

        for event in &events {
            match event {
                StreamEvent::StreamStart => {}
                StreamEvent::StreamChunk(chunk) => {
                    let _ = write!(out, "{}", chunk);
                    let _ = out.flush();
                }
                StreamEvent::StreamEnd(sources) => {
                    // Newline after the answer text.
                    let _ = writeln!(out);
                    if !sources.is_empty() {
                        let _ = writeln!(out, "\nSources:");
                        for src in sources {
                            let _ = writeln!(out, "  {}", src);
                        }
                    }
                }
                StreamEvent::Error(msg) => {
                    eprintln!("Server error: {}", msg);
                    process::exit(1);
                }
            }
        }
    });
}

fn read_question(positional_question: Option<String>) -> String {
    if let Some(question) = positional_question {
        return question.trim().to_string();
    }

    // Read question from stdin (first line). Prompt when attached to a terminal
    // so users invoking bare `md-qa` understand why input is awaited.
    let stdin = io::stdin();
    if stdin.is_terminal() {
        print!("Question: ");
        let _ = io::stdout().flush();
    }

    let mut line = String::new();
    stdin.lock().read_line(&mut line).unwrap_or(0);
    line.trim().to_string()
}

#[cfg(test)]
mod tests {
    use super::{load_runtime_config_from_paths, parse_cli_command_from, CliCommand};
    use std::fs;
    use std::path::PathBuf;

    fn write_test_config(path: &std::path::Path, port: u16, index_name: &str) {
        fs::write(
            path,
            format!(
                "api:\n  base_url: http://localhost\nserver:\n  port: {}\n  index_name: {}\n",
                port, index_name
            ),
        )
        .expect("should write test config");
    }

    #[test]
    fn help_short_flag_exits_before_runtime() {
        let parsed = parse_cli_command_from(["md-qa", "-h"]).expect("parse should succeed");
        assert!(matches!(parsed, CliCommand::PrintHelp { .. }));
    }

    #[test]
    fn help_long_flag_exits_before_runtime() {
        let parsed = parse_cli_command_from(["md-qa", "--help"]).expect("parse should succeed");
        assert!(matches!(parsed, CliCommand::PrintHelp { .. }));
    }

    #[test]
    fn version_flag_prints_version() {
        let parsed = parse_cli_command_from(["md-qa", "--version"]).expect("parse should succeed");
        assert!(matches!(parsed, CliCommand::PrintVersion));
    }

    #[test]
    fn config_flag_sets_override_path() {
        let parsed = parse_cli_command_from(["md-qa", "--config", "/tmp/config.yaml"])
            .expect("parse should succeed");
        match parsed {
            CliCommand::Run(options) => {
                assert_eq!(options.config_path, Some(PathBuf::from("/tmp/config.yaml")));
            }
            other => panic!("expected Run command, got {other:?}"),
        }
    }

    #[test]
    fn config_inline_value_sets_override_path() {
        let parsed = parse_cli_command_from(["md-qa", "--config=/tmp/config.yaml"])
            .expect("parse should succeed");
        match parsed {
            CliCommand::Run(options) => {
                assert_eq!(options.config_path, Some(PathBuf::from("/tmp/config.yaml")));
            }
            other => panic!("expected Run command, got {other:?}"),
        }
    }

    #[test]
    fn missing_config_value_returns_error() {
        let err = parse_cli_command_from(["md-qa", "--config"]).expect_err("parse should fail");
        assert!(err.contains("--config requires a value"));
    }

    #[test]
    fn unknown_option_returns_error() {
        let err = parse_cli_command_from(["md-qa", "--wat"]).expect_err("parse should fail");
        assert!(err.contains("unknown option"));
    }

    #[test]
    fn positional_question_is_accepted() {
        let parsed =
            parse_cli_command_from(["md-qa", "What is Rust?"]).expect("parse should succeed");
        match parsed {
            CliCommand::Run(options) => {
                assert_eq!(options.question.as_deref(), Some("What is Rust?"));
                assert_eq!(options.config_path, None);
            }
            other => panic!("expected Run command, got {other:?}"),
        }
    }

    #[test]
    fn positional_question_with_config_is_accepted() {
        let parsed = parse_cli_command_from(["md-qa", "--config", "/tmp/config.yaml", "hello"])
            .expect("parse should succeed");
        match parsed {
            CliCommand::Run(options) => {
                assert_eq!(options.question.as_deref(), Some("hello"));
                assert_eq!(options.config_path, Some(PathBuf::from("/tmp/config.yaml")));
            }
            other => panic!("expected Run command, got {other:?}"),
        }
    }

    #[test]
    fn multiple_positional_arguments_return_error() {
        let err =
            parse_cli_command_from(["md-qa", "first", "second"]).expect_err("parse should fail");
        assert!(err.contains("unexpected positional argument"));
    }

    #[test]
    fn missing_default_config_uses_built_in_defaults() {
        let dir = tempfile::tempdir().expect("temp dir");
        let missing_default_path = dir.path().join("config.yaml");
        assert!(!missing_default_path.exists());

        let cfg = load_runtime_config_from_paths(None, None, Some(missing_default_path))
            .expect("should fallback to defaults");
        assert_eq!(cfg.server.port, None);
        assert_eq!(cfg.server.index_name, None);
    }

    #[test]
    fn missing_explicit_config_returns_error() {
        let dir = tempfile::tempdir().expect("temp dir");
        let missing_explicit_path = dir.path().join("does-not-exist.yaml");

        let err = load_runtime_config_from_paths(Some(missing_explicit_path.clone()), None, None)
            .expect_err("explicit path should fail when missing");
        assert!(err.contains("failed to load config"));
        assert!(err.contains(&missing_explicit_path.display().to_string()));
    }

    #[test]
    fn explicit_config_path_is_loaded() {
        let dir = tempfile::tempdir().expect("temp dir");
        let config_path = dir.path().join("config.yaml");
        write_test_config(&config_path, 9876, "from-cli");

        let cfg = load_runtime_config_from_paths(Some(config_path), None, None)
            .expect("should load explicit config");
        assert_eq!(cfg.server.port, Some(9876));
        assert_eq!(cfg.server.index_name.as_deref(), Some("from-cli"));
    }

    #[test]
    fn env_config_path_wins_over_default_path() {
        let dir = tempfile::tempdir().expect("temp dir");
        let env_path = dir.path().join("env.yaml");
        let default_path = dir.path().join("default.yaml");
        write_test_config(&env_path, 7777, "from-env");
        write_test_config(&default_path, 8888, "from-default");

        let cfg = load_runtime_config_from_paths(None, Some(env_path), Some(default_path))
            .expect("should load env config");
        assert_eq!(cfg.server.port, Some(7777));
        assert_eq!(cfg.server.index_name.as_deref(), Some("from-env"));
    }
}
