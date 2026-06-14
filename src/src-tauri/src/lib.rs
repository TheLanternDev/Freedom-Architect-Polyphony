// Architekt Wolności — Tauri entry point.
//
// Auto-spawns the FastAPI backend (uvicorn main:app on 127.0.0.1:8000)
// when the desktop app starts, so the user does NOT need to launch
// `uvicorn` in a terminal. The child process is killed when the window
// closes / app exits.
//
// Resolution order for the repository root (must contain `main.py`):
//   1. env var AW_REPO_ROOT  (explicit override — production-friendly)
//   2. ../..   relative to the .app/Contents/MacOS executable (dev cargo run)
//   3. ~/Projects/architekt-wolnosci
//   4. current working directory
//
// Python interpreter selection (first that exists):
//   <repo>/.venv/bin/python  →  <repo>/venv/bin/python  →  `python3` on PATH

use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use tauri::Manager;

const KEYRING_SERVICE: &str = "architekt-wolnosci";
const KEYRING_USER: &str = "anthropic-api-key";

#[tauri::command]
fn store_llm_key(key: String) -> Result<(), String> {
    let trimmed = key.trim();
    if trimmed.is_empty() {
        return clear_llm_key();
    }
    let entry = keyring::Entry::new(KEYRING_SERVICE, KEYRING_USER).map_err(|e| e.to_string())?;
    entry.set_password(trimmed).map_err(|e| e.to_string())
}

#[tauri::command]
fn get_llm_key() -> Result<Option<String>, String> {
    let entry = keyring::Entry::new(KEYRING_SERVICE, KEYRING_USER).map_err(|e| e.to_string())?;
    match entry.get_password() {
        Ok(p) => {
            let t = p.trim().to_string();
            if t.is_empty() {
                Ok(None)
            } else {
                Ok(Some(t))
            }
        }
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(e.to_string()),
    }
}

#[tauri::command]
fn clear_llm_key() -> Result<(), String> {
    let entry = keyring::Entry::new(KEYRING_SERVICE, KEYRING_USER).map_err(|e| e.to_string())?;
    match entry.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(e) => Err(e.to_string()),
    }
}

struct BackendHandle(Mutex<Option<Child>>);

fn dir_has_main_py(p: &Path) -> bool {
    p.join("main.py").is_file()
}

fn resolve_repo_root() -> Option<PathBuf> {
    // 1. Explicit override.
    if let Ok(v) = std::env::var("AW_REPO_ROOT") {
        let p = PathBuf::from(v);
        if dir_has_main_py(&p) {
            return Some(p);
        }
    }

    // 2. Relative to executable (dev: target/debug, prod: .app/Contents/MacOS).
    if let Ok(exe) = std::env::current_exe() {
        let candidates = [
            exe.parent().and_then(|p| p.parent()).and_then(|p| p.parent()),
            exe.parent().and_then(|p| p.parent()).and_then(|p| p.parent()).and_then(|p| p.parent()),
            exe.parent().and_then(|p| p.parent()).and_then(|p| p.parent()).and_then(|p| p.parent()).and_then(|p| p.parent()),
        ];
        for c in candidates.iter().flatten() {
            if dir_has_main_py(c) {
                return Some(c.to_path_buf());
            }
        }
    }

    // 3. Common project location for this user.
    if let Some(home) = std::env::var_os("HOME") {
        let p = PathBuf::from(home).join("Projects").join("architekt-wolnosci");
        if dir_has_main_py(&p) {
            return Some(p);
        }
    }

    // 4. Current working directory.
    if let Ok(cwd) = std::env::current_dir() {
        if dir_has_main_py(&cwd) {
            return Some(cwd);
        }
    }

    None
}

fn resolve_python(repo: &Path) -> PathBuf {
    let candidates = [
        repo.join(".venv").join("bin").join("python"),
        repo.join("venv").join("bin").join("python"),
        repo.join(".venv").join("bin").join("python3"),
        repo.join("venv").join("bin").join("python3"),
    ];
    for c in candidates.iter() {
        if c.is_file() {
            return c.clone();
        }
    }
    PathBuf::from("python3")
}

fn spawn_backend() -> Option<Child> {
    // Allow user to fully disable the auto-spawn (e.g. when running uvicorn
    // manually with --reload during development).
    if std::env::var("AW_DISABLE_AUTOSPAWN").is_ok() {
        eprintln!("[aw] AW_DISABLE_AUTOSPAWN set — skipping backend autospawn");
        return None;
    }

    let repo = match resolve_repo_root() {
        Some(r) => r,
        None => {
            eprintln!("[aw] could not locate repo root (main.py) — backend will NOT auto-start");
            return None;
        }
    };
    let python = resolve_python(&repo);

    eprintln!("[aw] starting backend: {} -m uvicorn main:app  (cwd={})", python.display(), repo.display());

    let mut cmd = Command::new(&python);
    cmd.arg("-m")
        .arg("uvicorn")
        .arg("main:app")
        .arg("--host")
        .arg("127.0.0.1")
        .arg("--port")
        .arg("8000")
        .current_dir(&repo)
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    match cmd.spawn() {
        Ok(child) => {
            eprintln!("[aw] backend spawned, pid={}", child.id());
            Some(child)
        }
        Err(e) => {
            eprintln!("[aw] failed to spawn backend: {}", e);
            None
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let backend = spawn_backend();
    let handle = BackendHandle(Mutex::new(backend));

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(handle)
        .invoke_handler(tauri::generate_handler![store_llm_key, get_llm_key, clear_llm_key])
        .build(tauri::generate_context!())
        .expect("error while building Architekt Wolnosci")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                if let Some(h) = app.try_state::<BackendHandle>() {
                    if let Ok(mut guard) = h.0.lock() {
                        if let Some(mut child) = guard.take() {
                            let _ = child.kill();
                            let _ = child.wait();
                            eprintln!("[aw] backend terminated on app exit");
                        }
                    }
                }
            }
        });
}
