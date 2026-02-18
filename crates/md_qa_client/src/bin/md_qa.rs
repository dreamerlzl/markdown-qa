//! md-qa: Rust TUI binary for Markdown Q&A.
//! Reads config, connects to WebSocket server, sends query from stdin, prints
//! streamed answer and sources to stdout.

use md_qa_client::config;
use md_qa_client::StreamEvent;
use std::io::{self, BufRead, Write};
use std::path::PathBuf;
use std::process;

#[derive(Debug, Clone, PartialEq, Eq)]
struct CliOptions {
    config_path: Option<PathBuf>,
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
  {program_name} [OPTIONS]

Options:
  -c, --config <PATH>  Path to config file (default: MD_QA_CONFIG or ~/.md-qa/config.yaml)
  -h, --help           Print help and exit
  -V, --version        Print version and exit

Input:
  Reads one question from stdin (first line), then streams the answer.
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
                return Err(format!(
                    "Error: unexpected positional argument: {arg}\n\n{}",
                    help_text(&program_name)
                ));
            }
        }
    }

    Ok(CliCommand::Run(CliOptions { config_path }))
}

fn parse_cli_command() -> Result<CliCommand, String> {
    parse_cli_command_from(std::env::args())
}

fn resolve_config_path(override_path: Option<PathBuf>) -> PathBuf {
    // 1. --config <path> flag
    if let Some(path) = override_path {
        return path;
    }

    // 2. MD_QA_CONFIG env var
    if let Ok(val) = std::env::var("MD_QA_CONFIG") {
        return PathBuf::from(val);
    }
    // 3. Default path (~/.md-qa/config.yaml)
    config::default_config_path().unwrap_or_else(|| {
        eprintln!("Error: unable to determine config path (set --config or MD_QA_CONFIG)");
        process::exit(1);
    })
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
    let config_path = resolve_config_path(cli_options.config_path);

    let cfg = match config::load(&config_path) {
        Ok(c) => c,
        Err(e) => {
            eprintln!(
                "Error: failed to load config from {}: {}",
                config_path.display(),
                e
            );
            process::exit(1);
        }
    };

    let port = cfg.server.port.unwrap_or(8765);
    let server_url = format!("ws://127.0.0.1:{}", port);
    let index = cfg.server.index_name.as_deref();

    // Read question from stdin (first non-empty line).
    let stdin = io::stdin();
    let question = {
        let mut line = String::new();
        stdin.lock().read_line(&mut line).unwrap_or(0);
        line.trim().to_string()
    };

    if question.is_empty() {
        eprintln!("Error: no question provided on stdin");
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

#[cfg(test)]
mod tests {
    use super::{parse_cli_command_from, CliCommand};
    use std::path::PathBuf;

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
}
