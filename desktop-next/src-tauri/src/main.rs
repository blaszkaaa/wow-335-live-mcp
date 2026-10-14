// Suppress the terminal window for the packaged Tauri GUI on Windows.
// Debug builds retain a console to make development diagnostics possible.
#![cfg_attr(all(target_os = "windows", not(debug_assertions)), windows_subsystem = "windows")]

use serde_json::{json, Value};
use std::{fs, path::PathBuf, sync::Mutex, time::Duration};
use tauri::{Manager, RunEvent};
use tauri_plugin_shell::{process::CommandChild, ShellExt};

fn discovery_file() -> Result<PathBuf, String> {
    let root = std::env::var("LOCALAPPDATA")
        .map_err(|_| "LOCALAPPDATA is unavailable".to_string())?;
    Ok(PathBuf::from(root).join("WoWMCP").join("control-center.json"))
}

#[tauri::command]
async fn backend_api(action: String, payload: Option<Value>) -> Result<Value, String> {
    let (endpoint, is_post) = match action.as_str() {
        "dashboard" => ("/v2/dashboard", false),
        "get_settings" => ("/v2/settings", false),
        "refresh" => ("/v2/refresh", true),
        "launch" => ("/v2/launch", true),
        "demo" => ("/v2/demo", true),
        "set_settings" => ("/v2/settings", true),
        _ => return Err("Unsupported desktop API action".to_string()),
    };
    let contents = fs::read_to_string(discovery_file()?)
        .map_err(|_| "Local WoW MCP service is starting or unavailable".to_string())?;
    let config: Value = serde_json::from_str(&contents)
        .map_err(|_| "Invalid local service configuration".to_string())?;
    let port = config["port"].as_u64()
        .filter(|p| *p > 0 && *p <= 65535)
        .ok_or("Invalid service port")?;
    let token = config["token"].as_str()
        .filter(|v| v.len() == 64 && v.as_bytes().iter().all(|b| b.is_ascii_hexdigit()))
        .ok_or("Invalid service token")?;
    let address = format!("http://127.0.0.1:{}{}", port, endpoint);
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(7))
        .build()
        .map_err(|err| err.to_string())?;
    let req = if is_post {
        client.post(&address).json(&payload.unwrap_or(json!({})))
    } else {
        client.get(&address)
    };
    let response = req.header("X-WoWMCP-Token", token).send().await
        .map_err(|_| "Unable to contact local WoW MCP service".to_string())?;
    if !response.status().is_success() {
        return Err(format!("Local service returned {}", response.status()));
    }
    response.json::<Value>().await.map_err(|err| err.to_string())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let (mut events, child) = app.shell().sidecar("wow-mcp-service")?.spawn()?;
            app.manage(Mutex::new(Some(child)));
            tauri::async_runtime::spawn(async move {
                while events.recv().await.is_some() {}
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![backend_api])
        .build(tauri::generate_context!())
        .expect("Failed to initialize WoW MCP Control Center")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                let managed = app.state::<Mutex<Option<CommandChild>>>();
                if let Ok(mut process) = managed.lock() {
                    if let Some(child) = process.take() {
                        let _ = child.kill();
                    }
                };
            }
        });
}
