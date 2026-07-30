// Architekt Wolności — Tauri entry point.
//
// Uruchamia backend FastAPI jako child process, żeby użytkownik NIE musiał
// odpalać `uvicorn` w terminalu. Dwie ścieżki, wybierane automatycznie:
//
//   1. SIDECAR (produkcja / paczka testowa) — zamrożona binarka PyInstoller
//      zbindlowana z .app/.msi (`bundle.externalBin` w tauri.conf.json,
//      binarka budowana przez `scripts/build-backend-sidecar.sh` /
//      `scripts/windows/build-backend-sidecar.ps1` PRZED `tauri build`).
//      Samowystarczalna: tester NIE potrzebuje Pythona ani repo obok. To
//      jest ścieżka używana przez `npm run tauri:build`.
//
//   2. DEV FALLBACK — gdy sidecar nie jest zbudowany (typowe podczas
//      `npm run tauri:dev`), spadamy na stare zachowanie: uruchamiamy
//      `<repo>/.venv/bin/python -m uvicorn main:app --reload`, szukając
//      repo przez AW_REPO_ROOT → obok binarki → ~/Projects/architekt-wolnosci
//      → cwd. Zostawia hot-reload w developmencie bez zmian.
//
// AW_DISABLE_AUTOSPAWN=1 wyłącza OBIE ścieżki (np. backend już odpalony
// ręcznie w osobnym terminalu).
//
// Logi backendu (obie ścieżki) trafiają do plików w katalogu danych
// aplikacji — te same konwencje per-OS co `env_bootstrap.app_data_dir()`
// w Pythonie (macOS: `~/Library/Application Support/ArchitektWolnosci`,
// Windows: `%APPDATA%\ArchitektWolnosci`, Linux: `~/.local/share/...`) —
// NIE `/dev/null`, inaczej zgłoszenie buga testera nie ma z czego czerpać.

use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;

use tauri::{Emitter, Manager};
use tauri_plugin_shell::process::CommandEvent;
use tauri_plugin_shell::ShellExt;

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

/// Katalog danych aplikacji — MUSI zgadzać się z `env_bootstrap.app_data_dir()`
/// (Python), inaczej logi Rust i baza/JWT Pythona wylądują w różnych miejscach.
/// Override: `AW_APP_DATA_DIR` (ten sam env var po obu stronach).
fn app_data_dir() -> PathBuf {
    if let Ok(v) = std::env::var("AW_APP_DATA_DIR") {
        if !v.trim().is_empty() {
            return PathBuf::from(v);
        }
    }
    let home = std::env::var_os("HOME")
        .or_else(|| std::env::var_os("USERPROFILE"))
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."));

    #[cfg(target_os = "macos")]
    {
        home.join("Library").join("Application Support").join("ArchitektWolnosci")
    }
    #[cfg(target_os = "windows")]
    {
        std::env::var_os("APPDATA")
            .map(PathBuf::from)
            .unwrap_or_else(|| home.join("AppData").join("Roaming"))
            .join("ArchitektWolnosci")
    }
    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
    {
        std::env::var_os("XDG_DATA_HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|| home.join(".local").join("share"))
            .join("ArchitektWolnosci")
    }
}

/// Rotacja size-based: powyżej 5 MB bieżący log ląduje jako `<name>.old`
/// (poprzedni .old nadpisany). Bez tego logi rosłyby bez limitu — szczególnie
/// dev `--reload` potrafi zasypać stderr.
const LOG_ROTATE_BYTES: u64 = 5 * 1024 * 1024;

/// Diagnostyka LAUNCHERA (preflight portu, orphan-kill, wybór ścieżki spawnu)
/// do pliku `logs/launcher.log` + stderr. W zbundlowanym `.app` stderr idzie
/// w próżnię — bez pliku tester z zablokowanym portem widzi „unreachable”
/// i NIE MA z czego zrobić zgłoszenia (dokładnie ten sam argument, dla
/// którego logi backendu poszły do plików).
fn log_launcher(msg: &str) {
    eprintln!("[aw] {}", msg);
    if let Some(mut f) = open_log_file("launcher.log") {
        let ts = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);
        let _ = writeln!(f, "[{}] {}", ts, msg);
    }
}

fn open_log_file(name: &str) -> Option<File> {
    let dir = app_data_dir().join("logs");
    if let Err(e) = fs::create_dir_all(&dir) {
        eprintln!("[aw] nie mogę utworzyć katalogu logów {}: {}", dir.display(), e);
        return None;
    }
    let path = dir.join(name);
    if let Ok(meta) = fs::metadata(&path) {
        if meta.len() > LOG_ROTATE_BYTES {
            let _ = fs::rename(&path, dir.join(format!("{}.old", name)));
        }
    }
    match OpenOptions::new().create(true).append(true).open(&path) {
        Ok(f) => Some(f),
        Err(e) => {
            eprintln!("[aw] nie mogę otworzyć pliku logu {}: {}", name, e);
            None
        }
    }
}

// --- Port, PID-file i sprzątanie osieroconego backendu ----------------------
//
// Kill tylko na RunEvent::Exit nie pokrywa crash/force-quit appki: sierota
// trzyma port, nowy start nie może zbindować, a frontend PO CICHU gadałby ze
// STARĄ wersją backendu. Stąd: PID-file + preflight portu + marker /health.

fn backend_port() -> u16 {
    std::env::var("AW_BACKEND_PORT")
        .ok()
        .and_then(|v| v.trim().parse::<u16>().ok())
        .unwrap_or(8000)
}

fn pid_file_path() -> PathBuf {
    app_data_dir().join("backend.pid")
}

fn write_pid_file(pid: u32) {
    let p = pid_file_path();
    if let Err(e) = fs::write(&p, pid.to_string()) {
        eprintln!("[aw] nie mogę zapisać {}: {}", p.display(), e);
    }
}

fn remove_pid_file() {
    let _ = fs::remove_file(pid_file_path());
}

/// Usuwa PID-file TYLKO gdy zawiera NASZ pid (review 2026-07-30).
/// Bezwarunkowe `remove_pid_file()` przy wyjściu kasowało wpis obcej instancji
/// — a wtedy jej backend przestawał być śledzony i zostawał sierotą na porcie.
/// Single-instance plugin czyni to trudniejszym, ale nie niemożliwym
/// (dwa różne bundle = dwie różne instancje wg LaunchServices).
fn remove_pid_file_if_ours(pid: u32) {
    match fs::read_to_string(pid_file_path()) {
        Ok(s) if s.trim().parse::<u32>() == Ok(pid) => remove_pid_file(),
        Ok(s) => log_launcher(&format!(
            "backend.pid zawiera {} a nie nasz {} — NIE usuwam (inna instancja?)",
            s.trim(),
            pid
        )),
        Err(_) => {}
    }
}

/// Czy proces o tym PID wygląda na NASZ backend (sidecar/uvicorn)?
/// PID-y są reużywane przez OS — bez tej weryfikacji moglibyśmy ubić
/// przypadkowy proces użytkownika.
///
/// Kryterium (celowo wąskie — review 2026-07-17): sama para
/// "python"+"uvicorn" pasowała do uvicorna KAŻDEGO innego projektu, a na
/// Windows gołe "python" w tasklist ubijało dowolny python.exe o reużytym
/// PID. Teraz wymagamy naszej sygnatury: nazwa sidecara ALBO
/// uvicorn + main:app + NASZ port w linii komend.
fn cmdline_is_our_backend(cmd: &str, port: u16) -> bool {
    cmd.contains("architekt-backend")
        || (cmd.contains("uvicorn")
            && cmd.contains("main:app")
            && cmd.contains(&format!("--port {}", port)))
}

fn pid_looks_like_backend(pid: u32, port: u16) -> bool {
    #[cfg(unix)]
    {
        let out = Command::new("ps")
            .args(["-p", &pid.to_string(), "-o", "command="])
            .output();
        if let Ok(o) = out {
            let cmd = String::from_utf8_lossy(&o.stdout).to_lowercase();
            return cmdline_is_our_backend(&cmd, port);
        }
        false
    }
    #[cfg(windows)]
    {
        // tasklist zwraca tylko NAZWĘ obrazu (python.exe) — za mało, żeby
        // odróżnić nasz uvicorn od cudzego. CommandLine bierzemy z CIM.
        let out = Command::new("powershell")
            .args([
                "-NoProfile",
                "-Command",
                &format!(
                    "(Get-CimInstance Win32_Process -Filter 'ProcessId={}').CommandLine",
                    pid
                ),
            ])
            .output();
        if let Ok(o) = out {
            let cmd = String::from_utf8_lossy(&o.stdout).to_lowercase();
            if !cmd.trim().is_empty() {
                return cmdline_is_our_backend(&cmd, port);
            }
        }
        // Fallback (PowerShell niedostępny): tasklist wystarcza WYŁĄCZNIE
        // dla unikalnej nazwy sidecara — nigdy dla generycznego pythona.
        let out = Command::new("tasklist")
            .args(["/FI", &format!("PID eq {}", pid), "/FO", "CSV", "/NH"])
            .output();
        if let Ok(o) = out {
            let s = String::from_utf8_lossy(&o.stdout).to_lowercase();
            return s.contains("architekt-backend");
        }
        false
    }
}

/// Unix: SIGTERM (graceful — uvicorn domyka połączenia i SQLite), po pauzie
/// SIGKILL jako backstop. Windows: taskkill /T /F (brak odpowiednika SIGTERM
/// dla procesów konsolowych — udokumentowane ograniczenie).
fn kill_pid(pid: u32, force: bool) {
    #[cfg(unix)]
    {
        let sig = if force { "-KILL" } else { "-TERM" };
        let _ = Command::new("kill").args([sig, &pid.to_string()]).status();
    }
    #[cfg(windows)]
    {
        let pid_s = pid.to_string();
        let mut args = vec!["/PID", pid_s.as_str(), "/T"];
        if force {
            args.push("/F");
        }
        let _ = Command::new("taskkill").args(&args).status();
    }
}

fn port_in_use(port: u16) -> bool {
    let addr = format!("127.0.0.1:{}", port);
    addr.parse()
        .ok()
        .and_then(|a| TcpStream::connect_timeout(&a, Duration::from_millis(400)).ok())
        .is_some()
}

/// Surowy GET po TCP (bez zależności HTTP). None = nie da się połączyć albo
/// odpowiedź pusta; Some(body) = cokolwiek serwer odesłał.
fn http_get(port: u16, path: &str, read_timeout_ms: u64) -> Option<String> {
    let addr = format!("127.0.0.1:{}", port).parse().ok()?;
    let mut s = TcpStream::connect_timeout(&addr, Duration::from_millis(400)).ok()?;
    // 2500ms (było 1000): backend pod obciążeniem / zimny start na słabszej
    // maszynie potrafi odpowiedzieć później; partial read klasyfikował
    // wtedy NASZ backend jako obcy → Blocked → apka bez backendu.
    let _ = s.set_read_timeout(Some(Duration::from_millis(read_timeout_ms)));
    let _ = s.set_write_timeout(Some(Duration::from_millis(400)));
    let req = format!(
        "GET {} HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nConnection: close\r\n\r\n",
        path, port
    );
    s.write_all(req.as_bytes()).ok()?;
    let mut buf = Vec::new();
    let _ = s.read_to_end(&mut buf);
    if buf.is_empty() {
        return None;
    }
    Some(String::from_utf8_lossy(&buf).into_owned())
}

/// Wyciąga wartość stringowego pola JSON bez parsera JSON (nie chcemy serde
/// w ścieżce preflightu). Czysta funkcja — pokryta testami niżej.
fn json_str_field(body: &str, field: &str) -> Option<String> {
    let needle = format!("\"{}\"", field);
    let start = body.find(&needle)? + needle.len();
    let rest = &body[start..];
    let colon = rest.find(':')?;
    let after = rest[colon + 1..].trim_start();
    let mut chars = after.char_indices();
    if chars.next()?.1 != '"' {
        return None;
    }
    let mut out = String::new();
    for (_, c) in chars {
        match c {
            '"' => return Some(out),
            '\\' => continue,
            _ => out.push(c),
        }
    }
    None
}

/// Czy to odpowiedź NASZEGO backendu (marker `app` z api/routers/meta.py)?
/// Czysta funkcja nad ciałem odpowiedzi — testowalna bez sieci.
fn body_is_our_backend(body: &str) -> bool {
    body.contains("architekt-wolnosci")
}

/// Sonda /health: Some(HealthProbe) = odpowiedź HTTP, None = port nie gada HTTP.
struct HealthProbe {
    is_ours: bool,
    build_id: Option<String>,
}

fn probe_health(port: u16) -> Option<HealthProbe> {
    let body = http_get(port, "/health", 2500)?;
    Some(HealthProbe {
        is_ours: body_is_our_backend(&body),
        build_id: json_str_field(&body, "build_id"),
    })
}

/// Wynik negatywny/pusty NIE jest ostateczny przy pierwszej próbie: proces,
/// który dopiero zbindował port (uvicorn wstaje, PyInstaller się rozpakował
/// sekundę temu), może jeszcze nie serwować HTTP. Kilka prób z przerwą,
/// zanim uznamy port za OBCY i odetniemy backend całej sesji.
fn probe_health_with_retry(port: u16, attempts: u32, gap_ms: u64) -> Option<HealthProbe> {
    let mut last: Option<HealthProbe> = None;
    for i in 0..attempts {
        let probe = probe_health(port);
        if let Some(p) = &probe {
            if p.is_ours {
                return probe;
            }
        }
        last = probe;
        if i + 1 < attempts {
            std::thread::sleep(Duration::from_millis(gap_ms));
        }
    }
    last
}

/// Czekanie na GOTOWOŚĆ świeżo spawnowanego backendu (review 2026-07-30).
///
/// Poprzednio status leciał na „spawned" natychmiast po `spawn()` — a PyInstaller
/// `--onefile` na pierwszym uruchomieniu rozpakowuje się do temp (plus skan
/// Gatekeepera), realnie 3–10 s. Frontend odpalał `/health` od razu, dostawał
/// błąd sieci i PIERWSZE uruchomienie sprzedawanego pudełka pokazywało awarię.
/// Tu czekamy do `timeout_s`, sprawdzając co 500 ms.
fn wait_until_ready(port: u16, timeout_s: u64) -> Option<HealthProbe> {
    let deadline = std::time::Instant::now() + Duration::from_secs(timeout_s);
    let mut attempt: u32 = 0;
    while std::time::Instant::now() < deadline {
        attempt += 1;
        if let Some(p) = probe_health(port) {
            if p.is_ours {
                log_launcher(&format!(
                    "backend gotowy po ~{} próbach, build_id={}",
                    attempt,
                    p.build_id.clone().unwrap_or_else(|| "?".into())
                ));
                return Some(p);
            }
        }
        std::thread::sleep(Duration::from_millis(500));
    }
    None
}

enum PortState {
    Free,
    OursAlive,
    Blocked,
}

/// Preflight przed spawnem: ubij zweryfikowaną sierotę z PID-file, potem
/// oceń stan portu.
fn cleanup_stale_backend(port: u16) -> PortState {
    if let Ok(s) = fs::read_to_string(pid_file_path()) {
        if let Ok(pid) = s.trim().parse::<u32>() {
            if pid_looks_like_backend(pid, port) {
                log_launcher(&format!(
                    "backend.pid={} — osierocony backend (crash/force-quit?) — zatrzymuję",
                    pid
                ));
                kill_pid(pid, false);
                std::thread::sleep(Duration::from_millis(700));
                kill_pid(pid, true);
                std::thread::sleep(Duration::from_millis(200));
            } else {
                log_launcher(&format!(
                    "backend.pid={} nie wygląda na nasz proces (PID reużyty przez OS) — tylko usuwam plik",
                    pid
                ));
            }
        }
        remove_pid_file();
    }

    if !port_in_use(port) {
        return PortState::Free;
    }
    match probe_health_with_retry(port, 3, 1000) {
        Some(p) if p.is_ours => {
            log_launcher(&format!(
                "port {} zajęty przez DZIAŁAJĄCY backend Architekta (ręczny uvicorn?) — \
                 używam go bez spawnu. Jego build_id={} — jeśli różni się od tego, \
                 czego oczekujesz, to NIE jest backend z tej paczki.",
                port,
                p.build_id.clone().unwrap_or_else(|| "?".into())
            ));
            PortState::OursAlive
        }
        _ => {
            log_launcher(&format!(
                "port {} zajęty przez OBCY proces — backend NIE wystartuje. \
                 Zwolnij port (lsof -i :{} / netstat -ano | findstr :{}) i uruchom \
                 aplikację ponownie.",
                port, port, port
            ));
            PortState::Blocked
        }
    }
}

/// Stan procesu backendu — dokładnie jedna z dwóch ścieżek jest `Some`
/// naraz (sidecar w produkcji, dev fallback w `tauri dev` bez sidecara).
#[derive(Default)]
struct BackendHandle {
    sidecar_child: Mutex<Option<tauri_plugin_shell::process::CommandChild>>,
    dev_child: Mutex<Option<Child>>,
}

/// Nazwa eventu Tauri z aktualnym stanem backendu. Frontend nasłuchuje
/// (`listen("backend-status")`) i nie musi pollować — patrz
/// `src/src/lib/backendStatus.ts`.
pub const BACKEND_STATUS_EVENT: &str = "backend-status";

/// Wynik preflightu/spawnu — dla frontendu przez komendę `backend_startup_status`
/// ORAZ event `backend-status`. Bez tego `PortState::Blocked` kończył się
/// „normalnym" startem okna i zagadkowym błędem sieci: jedyny ślad żył
/// w stderr, którego zbundlowana `.app` nigdzie nie pokazuje.
///
/// Wartości (kontrakt z `backendStatus.ts` — trzymaj zgodnie):
///   pending           — jeszcze nie wiemy (stan początkowy)
///   starting          — proces spawnowany, czekamy na /health
///   ready             — /health odpowiada NASZYM markerem; można pracować
///   reused_existing   — port trzymał już nasz backend (ręczny uvicorn)
///   port_blocked      — port zajęty przez OBCY proces
///   spawn_failed      — ani sidecar, ani dev fallback nie wystartowały
///   unreachable       — spawn się udał, ale /health nie odpowiedział w limicie
///   autospawn_disabled— AW_DISABLE_AUTOSPAWN=1
struct BackendStartupStatus {
    status: Mutex<&'static str>,
    build_id: Mutex<Option<String>>,
}

impl Default for BackendStartupStatus {
    fn default() -> Self {
        Self {
            status: Mutex::new("pending"),
            build_id: Mutex::new(None),
        }
    }
}

/// Payload komendy/eventu. `build_id` pozwala UI pokazać, z JAKIM backendem
/// rozmawia — po 8 dniach cichego rozjazdu wersji to nie jest luksus.
#[derive(serde::Serialize, Clone)]
struct BackendStatusPayload {
    status: String,
    build_id: Option<String>,
    port: u16,
    log_dir: String,
}

#[tauri::command]
fn backend_startup_status(state: tauri::State<'_, BackendStartupStatus>) -> BackendStatusPayload {
    BackendStatusPayload {
        status: state
            .status
            .lock()
            .map(|s| s.to_string())
            .unwrap_or_else(|_| "pending".into()),
        build_id: state.build_id.lock().ok().and_then(|b| b.clone()),
        port: backend_port(),
        log_dir: app_data_dir().join("logs").display().to_string(),
    }
}

fn set_startup_status(app: &tauri::AppHandle, status: &'static str, build_id: Option<String>) {
    if let Some(s) = app.try_state::<BackendStartupStatus>() {
        if let Ok(mut guard) = s.status.lock() {
            *guard = status;
        }
        if build_id.is_some() {
            if let Ok(mut guard) = s.build_id.lock() {
                *guard = build_id.clone();
            }
        }
    }
    // Event — żeby UI reagowało od razu, bez pollingu. Błąd emitu nie może
    // przerwać startu backendu, więc tylko log.
    let payload = BackendStatusPayload {
        status: status.to_string(),
        build_id,
        port: backend_port(),
        log_dir: app_data_dir().join("logs").display().to_string(),
    };
    if let Err(e) = app.emit(BACKEND_STATUS_EVENT, payload) {
        eprintln!("[aw] nie mogę wyemitować {}: {}", BACKEND_STATUS_EVENT, e);
    }
}

// --- Ścieżka 1: sidecar (produkcja / paczka testowa) ------------------------

fn spawn_backend_sidecar(app: &tauri::AppHandle, port: u16) -> Option<tauri_plugin_shell::process::CommandChild> {
    let sidecar = match app.shell().sidecar("architekt-backend") {
        Ok(s) => s.env("AW_BACKEND_PORT", port.to_string()),
        Err(e) => {
            log_launcher(&format!(
                "sidecar 'architekt-backend' niedostępny ({}) — próbuję dev fallback (python -m uvicorn)",
                e
            ));
            return None;
        }
    };

    let (mut rx, child) = match sidecar.spawn() {
        Ok(pair) => pair,
        Err(e) => {
            log_launcher(&format!("nie udało się uruchomić sidecara: {} — próbuję dev fallback", e));
            return None;
        }
    };

    log_launcher(&format!("backend (sidecar) wystartował, pid={}", child.pid()));

    let mut stdout_log = open_log_file("backend-stdout.log");
    let mut stderr_log = open_log_file("backend-stderr.log");
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    if let Some(f) = stdout_log.as_mut() {
                        let _ = f.write_all(&bytes);
                        let _ = f.write_all(b"\n");
                    }
                }
                CommandEvent::Stderr(bytes) => {
                    if let Some(f) = stderr_log.as_mut() {
                        let _ = f.write_all(&bytes);
                        let _ = f.write_all(b"\n");
                    }
                }
                CommandEvent::Error(err) => {
                    eprintln!("[aw] błąd sidecara: {}", err);
                }
                CommandEvent::Terminated(payload) => {
                    log_launcher(&format!("backend (sidecar) zakończony: {:?}", payload));
                    break;
                }
                _ => {}
            }
        }
    });

    Some(child)
}

// --- Ścieżka 2: dev fallback (python -m uvicorn --reload z repo + venv) ----
// Bez zmian funkcjonalnych względem poprzedniej wersji (przed sidecarem) —
// tylko przeniesione i włączone jako fallback, nie jedyna ścieżka.

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

    // 3. Zapamiętana ścieżka z poprzedniego uruchomienia Z REPO (review 2026-07-30).
    //    Kluczowe dla „odpalam ikoną": z /Applications kandydat 2 daje /Applications
    //    i /, kandydat 4 (cwd) daje / (LaunchServices), a lista sztywnych ścieżek
    //    nigdy nie trafi w cudze repo. Efekt był taki, że dev fallback był
    //    z ikony STRUKTURALNIE nieosiągalny — brak sidecara = appka bez backendu
    //    i bez wyjaśnienia. Teraz każde uruchomienie, które repo ZNALAZŁO
    //    (np. `tauri dev` z korzenia), zapisuje ścieżkę do app-data.
    if let Ok(saved) = fs::read_to_string(repo_hint_path()) {
        let p = PathBuf::from(saved.trim());
        if dir_has_main_py(&p) {
            return Some(p);
        }
    }

    // 4. Typowe lokalizacje projektu u tego użytkownika.
    if let Some(home) = std::env::var_os("HOME").or_else(|| std::env::var_os("USERPROFILE")) {
        let home = PathBuf::from(home);
        for sub in ["Projects", "Desktop", "Documents", "dev", "Code", "src"] {
            let p = home.join(sub).join("architekt-wolnosci");
            if dir_has_main_py(&p) {
                return Some(p);
            }
        }
        // Repo bezpośrednio w katalogu domowym.
        let p = home.join("architekt-wolnosci");
        if dir_has_main_py(&p) {
            return Some(p);
        }
    }

    // 5. Current working directory.
    if let Ok(cwd) = std::env::current_dir() {
        if dir_has_main_py(&cwd) {
            return Some(cwd);
        }
    }

    None
}

/// Plik z zapamiętaną ścieżką repo (patrz `resolve_repo_root` krok 3).
fn repo_hint_path() -> PathBuf {
    app_data_dir().join("repo_path")
}

fn save_repo_hint(repo: &Path) {
    let p = repo_hint_path();
    if let Some(parent) = p.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let _ = fs::write(&p, repo.display().to_string());
}

/// Interpreter z venva repo. `None` = brak venva.
///
/// Świadomie BEZ fallbacku do gołego `python3` na PATH (review 2026-07-30):
/// aplikacja GUI na macOS dziedziczy minimalny PATH z `launchd`
/// (`/usr/bin:/bin:/usr/sbin:/sbin`) — bez Homebrew, bez pyenv. Trafialiśmy więc
/// w `/usr/bin/python3` bez zainstalowanych zależności; `spawn()` zwracał Ok,
/// proces natychmiast umierał na `ModuleNotFoundError: uvicorn`, a launcher
/// raportował „wystartował". Lepszy jawny brak niż fałszywy sukces.
fn resolve_python(repo: &Path) -> Option<PathBuf> {
    let candidates = [
        repo.join(".venv").join("bin").join("python"),
        repo.join("venv").join("bin").join("python"),
        repo.join(".venv").join("bin").join("python3"),
        repo.join("venv").join("bin").join("python3"),
        // Windows
        repo.join(".venv").join("Scripts").join("python.exe"),
        repo.join("venv").join("Scripts").join("python.exe"),
    ];
    candidates.iter().find(|c| c.is_file()).cloned()
}

fn spawn_backend_dev(port: u16) -> Option<Child> {
    let repo = match resolve_repo_root() {
        Some(r) => r,
        None => {
            log_launcher(
                "dev fallback: nie znaleziono repo (main.py). Z ikony to normalne — \
                 paczka ma używać sidecara. Jeśli chcesz dev fallback, ustaw AW_REPO_ROOT \
                 albo uruchom raz `npm run tauri:dev` z korzenia repo (ścieżka zostanie \
                 zapamiętana w app-data/repo_path).",
            );
            return None;
        }
    };
    save_repo_hint(&repo);

    let python = match resolve_python(&repo) {
        Some(p) => p,
        None => {
            log_launcher(&format!(
                "dev fallback: repo znalezione ({}), ale brak venva (.venv/bin/python \
                 ani venv/bin/python). Utwórz: python3 -m venv .venv && \
                 .venv/bin/pip install -r requirements.txt",
                repo.display()
            ));
            return None;
        }
    };

    log_launcher(&format!(
        "dev fallback: {} -m uvicorn main:app (cwd={})",
        python.display(),
        repo.display()
    ));

    let stdout_stdio = open_log_file("backend-stdout.log").map(Stdio::from).unwrap_or_else(Stdio::null);
    let stderr_stdio = open_log_file("backend-stderr.log").map(Stdio::from).unwrap_or_else(Stdio::null);

    let mut cmd = Command::new(&python);
    cmd.arg("-m")
        .arg("uvicorn")
        .arg("main:app")
        // BEZ --reload (review 2026-07-30). Reloader uvicorna to supervisor +
        // worker: zapisywaliśmy PID supervisora, po 400 ms robiliśmy SIGKILL,
        // a worker (spawn multiprocessing, cmdline `python -c from
        // multiprocessing.spawn ...`) NIE pasował do cmdline_is_our_backend
        // i dziedziczył socket. Efekt: nieśmiertelna sierota trzymająca port,
        // rozpoznawana potem jako „nasz działający backend" (OursAlive) —
        // czyli appka po cichu gadała ze starym kodem. Hot-reload przy pracy
        // nad backendem: AW_DISABLE_AUTOSPAWN=1 + własny `uvicorn --reload`
        // w terminalu (launcher rozpozna go i użyje bez spawnu).
        .arg("--host")
        .arg("127.0.0.1")
        .arg("--port")
        .arg(port.to_string())
        .current_dir(&repo)
        .stdout(stdout_stdio)
        .stderr(stderr_stdio);

    match cmd.spawn() {
        Ok(child) => {
            log_launcher(&format!("backend (dev fallback) wystartował, pid={}", child.id()));
            Some(child)
        }
        Err(e) => {
            log_launcher(&format!("nie udało się uruchomić dev fallback: {}", e));
            None
        }
    }
}

/// Preflight → spawn → czekanie na gotowość. Woływane z osobnego wątku, więc
/// wolno tu blokować. Każdy etap raportuje stan przez `set_startup_status`
/// (komenda + event `backend-status`), żeby UI nigdy nie zostało z samym
/// „Failed to fetch" bez przyczyny.
fn start_backend_supervised(app: tauri::AppHandle) {
    let port = backend_port();

    match cleanup_stale_backend(port) {
        PortState::OursAlive => {
            let build_id = probe_health(port).and_then(|p| p.build_id);
            set_startup_status(&app, "reused_existing", build_id);
            return;
        }
        PortState::Blocked => {
            set_startup_status(&app, "port_blocked", None);
            return;
        }
        PortState::Free => {}
    }

    set_startup_status(&app, "starting", None);

    let spawned = {
        let state = app.state::<BackendHandle>();
        if let Some(child) = spawn_backend_sidecar(&app, port) {
            write_pid_file(child.pid());
            if let Ok(mut g) = state.sidecar_child.lock() {
                *g = Some(child);
            }
            true
        } else if let Some(child) = spawn_backend_dev(port) {
            write_pid_file(child.id());
            if let Ok(mut g) = state.dev_child.lock() {
                *g = Some(child);
            }
            true
        } else {
            false
        }
    };

    if !spawned {
        log_launcher(
            "UWAGA: backend nie wystartował żadną ze ścieżek (sidecar ani dev fallback). \
             Najczęstsza przyczyna w paczce: brak zbudowanej binarki sidecara — \
             uruchom ./scripts/build-backend-sidecar.sh i przebuduj paczkę.",
        );
        set_startup_status(&app, "spawn_failed", None);
        return;
    }

    // Gotowość, nie „spawn się udał". PyInstaller --onefile na zimnym starcie
    // rozpakowuje się do temp (+ skan Gatekeepera) — realnie 3–10 s, bywa więcej
    // na wolnym dysku. 45 s to sufit dla pierwszego uruchomienia paczki.
    let ready_timeout = std::env::var("AW_BACKEND_READY_TIMEOUT_S")
        .ok()
        .and_then(|v| v.trim().parse::<u64>().ok())
        .unwrap_or(45);

    match wait_until_ready(port, ready_timeout) {
        Some(p) => set_startup_status(&app, "ready", p.build_id),
        None => {
            log_launcher(&format!(
                "backend spawnowany, ale /health nie odpowiedział w {} s — \
                 sprawdź logs/backend-stderr.log (najczęściej brakujący \
                 --hidden-import w buildzie sidecara albo padnięty import).",
                ready_timeout
            ));
            set_startup_status(&app, "unreachable", None);
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        // MUSI być pierwszy plugin (wymóg tauri-plugin-single-instance).
        // Druga instancja kończy się natychmiast, a my tylko podnosimy okno
        // już działającej — zamiast pozwolić jej ubić backend pierwszej
        // (review 2026-07-30).
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            log_launcher(
                "druga instancja aplikacji — podnoszę istniejące okno, \
                 backend pierwszej instancji zostaje nietknięty",
            );
            if let Some(w) = app.get_webview_window("main") {
                let _ = w.unminimize();
                let _ = w.show();
                let _ = w.set_focus();
            }
        }))
        .plugin(tauri_plugin_shell::init())
        .manage(BackendHandle::default())
        .manage(BackendStartupStatus::default())
        .invoke_handler(tauri::generate_handler![
            store_llm_key, get_llm_key, clear_llm_key, backend_startup_status
        ])
        .setup(|app| {
            let app_handle = app.handle().clone();
            if std::env::var("AW_DISABLE_AUTOSPAWN").is_ok() {
                log_launcher("AW_DISABLE_AUTOSPAWN ustawione — backend NIE jest auto-uruchamiany");
                set_startup_status(&app_handle, "autospawn_disabled", None);
                return Ok(());
            }

            // CAŁY preflight + spawn + czekanie na gotowość idzie na WŁASNY WĄTEK
            // (review 2026-07-30). Wcześniej działo się to synchronicznie tutaj,
            // a `setup` biegnie na wątku głównym PRZED wejściem w event loop:
            // ścieżka „port zajęty" kosztowała 700+200 ms kill, 400 ms
            // port_in_use i 3×(400+2500)+2×1000 ms sondowania /health ≈ 13 s
            // zawieszonego, białego okna. Okno ma się pokazać natychmiast,
            // a stan backendu dojechać eventem `backend-status`.
            std::thread::spawn(move || {
                start_backend_supervised(app_handle);
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Architekt Wolnosci")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                if let Some(h) = app.try_state::<BackendHandle>() {
                    // Graceful: najpierw SIGTERM (uvicorn domyka połączenia
                    // i SQLite w locie — bez ryzyka urwanego zapisu), krótka
                    // pauza, dopiero potem twardy kill jako backstop.
                    // Sleepy przy wyjściu blokują WĄTEK GŁÓWNY (beach ball na
                    // do widzenia) — trzymamy je krótko: TERM + ≤400ms na
                    // graceful zejście uvicorna/SQLite, potem twardy kill.
                    let mut our_pid: Option<u32> = None;
                    if let Ok(mut guard) = h.sidecar_child.lock() {
                        if let Some(child) = guard.take() {
                            let pid = child.pid();
                            our_pid = Some(pid);
                            kill_pid(pid, false);
                            std::thread::sleep(Duration::from_millis(400));
                            let _ = child.kill(); // no-op jeśli już się zamknął
                            log_launcher(&format!("backend (sidecar, pid={}) zatrzymany przy wyjściu", pid));
                        }
                    }
                    if let Ok(mut guard) = h.dev_child.lock() {
                        if let Some(mut child) = guard.take() {
                            let pid = child.id();
                            our_pid = Some(pid);
                            kill_pid(pid, false);
                            // do ~0.4 s na czyste zejście, potem kill
                            let mut exited = false;
                            for _ in 0..4 {
                                if let Ok(Some(_)) = child.try_wait() {
                                    exited = true;
                                    break;
                                }
                                std::thread::sleep(Duration::from_millis(100));
                            }
                            if !exited {
                                let _ = child.kill();
                                let _ = child.wait();
                            }
                            log_launcher(&format!("backend (dev fallback, pid={}) zatrzymany przy wyjściu", pid));
                        }
                    }
                    // Tylko NASZ wpis — patrz remove_pid_file_if_ours.
                    if let Some(pid) = our_pid {
                        remove_pid_file_if_ours(pid);
                    }
                }
            }
        });
}

// ── Testy jednostkowe ───────────────────────────────────────────────────────
// Czyste funkcje decydujące o tym, czy ubijemy PROCES UŻYTKOWNIKA i czy uznamy
// port za nasz. Wcześniej 660 linii launchera nie miało ani jednego testu,
// mimo że `cmdline_is_our_backend` to funkcja nad stringiem (review 2026-07-30).
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nasz_sidecar_rozpoznany_po_nazwie() {
        assert!(cmdline_is_our_backend(
            "/applications/freedom architect.app/contents/macos/architekt-backend",
            8000
        ));
    }

    #[test]
    fn nasz_uvicorn_rozpoznany_po_pelnej_sygnaturze() {
        assert!(cmdline_is_our_backend(
            "/repo/.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000",
            8000
        ));
    }

    #[test]
    fn cudzy_uvicorn_nie_jest_nasz() {
        // Kluczowy przypadek: uvicorn INNEGO projektu na innym porcie.
        // Kryterium „python + uvicorn" ubijało tu cudzy proces.
        assert!(!cmdline_is_our_backend(
            "/other/.venv/bin/python -m uvicorn app.main:app --port 9000",
            8000
        ));
        // Ten sam port, ale inna aplikacja — też nie nasz.
        assert!(!cmdline_is_our_backend(
            "/other/.venv/bin/python -m uvicorn other:app --host 127.0.0.1 --port 8000",
            8000
        ));
        // Gołe python.exe o reużytym PID — nigdy nie ubijamy.
        assert!(!cmdline_is_our_backend("python.exe", 8000));
        assert!(!cmdline_is_our_backend("", 8000));
    }

    #[test]
    fn nasz_uvicorn_na_innym_porcie_nie_jest_nasz_dla_tego_portu() {
        assert!(!cmdline_is_our_backend(
            "python -m uvicorn main:app --port 8001",
            8000
        ));
    }

    #[test]
    fn marker_backendu_w_ciele_odpowiedzi() {
        assert!(body_is_our_backend(
            "HTTP/1.1 200 OK\r\n\r\n{\"status\":\"alive\",\"app\":\"architekt-wolnosci\"}"
        ));
        assert!(!body_is_our_backend("HTTP/1.1 200 OK\r\n\r\n{\"app\":\"grafana\"}"));
        assert!(!body_is_our_backend(""));
    }

    #[test]
    fn build_id_wyciagany_z_health() {
        let body = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n\
                    {\"status\":\"alive\",\"app\":\"architekt-wolnosci\",\
                    \"build_id\":\"a1b2c3d-202607301415\",\"built_at\":\"\"}";
        assert_eq!(
            json_str_field(body, "build_id").as_deref(),
            Some("a1b2c3d-202607301415")
        );
        assert_eq!(json_str_field(body, "built_at").as_deref(), Some(""));
        assert_eq!(json_str_field(body, "nie_ma_takiego"), None);
    }

    #[test]
    fn build_id_z_dirty_suffixem_i_spacjami() {
        assert_eq!(
            json_str_field("{\"build_id\" :  \"abc-1-dirty\"}", "build_id").as_deref(),
            Some("abc-1-dirty")
        );
    }

    #[test]
    fn json_str_field_nie_wybucha_na_smieciach() {
        // Pole liczbowe (nie string) → None, nie panic.
        assert_eq!(json_str_field("{\"build_id\": 42}", "build_id"), None);
        // Niedomknięty string → None.
        assert_eq!(json_str_field("{\"build_id\": \"abc", "build_id"), None);
        assert_eq!(json_str_field("", "build_id"), None);
    }
}
