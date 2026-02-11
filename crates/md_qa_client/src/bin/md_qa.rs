//! md-qa: Rust TUI binary for Markdown Q&A.
//! Reads config, connects to WebSocket server, sends query from stdin, prints
//! streamed answer and sources to stdout.

use md_qa_client::config;
use md_qa_client::StreamEvent;
use std::io::{self, BufRead, Write};
use std::path::PathBuf;
use std::process;

fn resolve_config_path() -> PathBuf {
    // 1. --config <path> flag
    let args: Vec<String> = std::env::args().collect();
    if let Some(pos) = args.iter().position(|a| a == "--config") {
        if let Some(path) = args.get(pos + 1) {
            return PathBuf::from(path);
        }
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
    let config_path = resolve_config_path();

    let cfg = match config::load(&config_path) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("Error: failed to load config from {}: {}", config_path.display(), e);
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
