use std::net::TcpListener;
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::{Manager, RunEvent};

/// The Python engine (engine/server.py) running on a local port.
struct Engine {
    url: String,
    child: Mutex<Option<Child>>,
}

fn engine_dir() -> PathBuf {
    std::env::var_os("NORMA_ENGINE_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../engine"))
}

fn python(dir: &PathBuf) -> PathBuf {
    if let Some(path) = std::env::var_os("NORMA_PYTHON") {
        return PathBuf::from(path);
    }
    let venv = if cfg!(windows) {
        dir.join(".venv/Scripts/python.exe")
    } else {
        dir.join(".venv/bin/python")
    };
    if venv.exists() {
        venv
    } else {
        PathBuf::from(if cfg!(windows) { "python" } else { "python3" })
    }
}

fn start_engine() -> Engine {
    let port = TcpListener::bind("127.0.0.1:0")
        .and_then(|listener| listener.local_addr())
        .map(|addr| addr.port())
        .unwrap_or(8865);
    let dir = engine_dir();
    let child = Command::new(python(&dir))
        .arg("server.py")
        .arg("--port")
        .arg(port.to_string())
        .current_dir(&dir)
        .env("PYTHONUNBUFFERED", "1")
        .spawn()
        .map_err(|error| eprintln!("Could not start the engine: {error}"))
        .ok();
    Engine {
        url: format!("http://127.0.0.1:{port}"),
        child: Mutex::new(child),
    }
}

#[tauri::command]
fn engine_url(engine: tauri::State<Engine>) -> String {
    engine.url.clone()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(start_engine())
        .invoke_handler(tauri::generate_handler![engine_url])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                if let Some(mut child) = app.state::<Engine>().child.lock().unwrap().take() {
                    let _ = child.kill();
                }
            }
        });
}
