//! Tauri application library. Config UI and chat panel are added in later tasks.

pub mod commands;

pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            commands::get_config_path,
            commands::load_config,
            commands::save_config,
            commands::connect_server,
            commands::disconnect_server,
            commands::connection_status,
            commands::send_query,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
