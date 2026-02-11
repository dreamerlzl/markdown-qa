// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windowsubsystem = "windows")]

fn main() {
    md_qa_gui_lib::run();
}
