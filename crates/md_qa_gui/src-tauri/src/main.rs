// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    #[cfg(target_os = "linux")]
    sanitize_gtk_environment();

    md_qa_gui_lib::run();
}

/// Strip GTK modules that trigger the Gdk-CRITICAL assertion
/// `gdk_wayland_window_set_dbus_properties_libgtk_only:
///  assertion 'GDK_IS_WAYLAND_WINDOW (window)' failed`
///
/// The `appmenu-gtk-module` (global-menu integration) calls
/// `gdk_wayland_window_set_dbus_properties_libgtk_only` on windows that are
/// not yet – or never will be – proper GDK Wayland windows.  Removing it from
/// `GTK_MODULES` before GTK initialises prevents the assertion without
/// affecting application functionality.
#[cfg(target_os = "linux")]
fn sanitize_gtk_environment() {
    use std::env;

    if let Ok(modules) = env::var("GTK_MODULES") {
        let filtered: Vec<&str> = modules
            .split(':')
            .filter(|m| !m.contains("appmenu-gtk-module"))
            .collect();
        if filtered.is_empty() {
            env::remove_var("GTK_MODULES");
        } else {
            env::set_var("GTK_MODULES", filtered.join(":"));
        }
    }

    if env::var_os("WEBKIT_DISABLE_DMABUF_RENDERER").is_none() {
        env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1");
    }
}
