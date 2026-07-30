"""
Ładowanie zmiennych z pliku `.env` przed resztą aplikacji (FastAPI / agenci).

JEDYNE źródło prawdy sekretów/kluczy API: `.env` w korzeniu repozytorium.
`src/.env` służy WYŁĄCZNIE frontendowi (Vite/Tauri) i powinien zawierać tylko
zmienne `VITE_*`; uzupełnia jedynie klucze nadal puste po korzeniowym `.env`.

Nadpisanie jawne: `AW_ENV_FILE=/ścieżka/do/pliku` (tylko ten plik, jeśli istnieje).

`python-dotenv` z `override=False` nie nadpisuje istniejących kluczy — nawet
gdy wartość w środowisku to pusty string po `export ANTHROPIC_API_KEY=`.
Ten moduł wypełnia tylko brakujące lub „puste” (same białe znaki) zmienne.

--- Tryb "boxed" (paczka desktop, PyInstaller sidecar) ---

Gdy `sys.frozen` jest ustawione (PyInstaller `--onefile`), nie ma repozytorium
ani `venv` obok binarki, `Path(__file__).resolve().parent` wskazuje na
efemeryczny katalog ekstrakcji (`_MEIPASS`, znika po zamknięciu procesu), i nie
ma terminala, w którym tester mógłby ręcznie wpisać `.env`. W tym trybie
`load_repo_env()` dodatkowo:

  1. czyta `config.env` w katalogu danych aplikacji per-OS, TRWAŁYM między
     uruchomieniami (patrz `app_data_dir()` — macOS:
     `~/Library/Application Support/ArchitektWolnosci`, Windows:
     `%APPDATA%\\ArchitektWolnosci`, Linux: `~/.local/share/ArchitektWolnosci`);
  2. jeśli `ARCHITEKT_JWT_SECRET` nadal brakuje po wszystkich źródłach —
     generuje losowy sekret (32 losowe bajty) i zapisuje go trwale do
     **osobnego** pliku `jwt.secret` przez `O_CREAT|O_EXCL` (atomowo — patrz
     `_ensure_jwt_secret`). Bez sekretu logowanie kończy się 500 (`auth.py`
     jest fail-closed), a bez trwałego zapisu każdy restart generowałby nowy
     i wylogowywał użytkownika;
  3. ustawia domyślne `ARCHITEKT_DB_PATH` / `COST_LOG_PATH` / `EVENTS_LOG_PATH`
     w tym samym katalogu danych zamiast w katalogu ekstrakcji PyInstallera —
     inaczej baza i logi kosztów znikałyby po każdym restarcie.

Klucz LLM (Anthropic/xAI) w trybie boxed **nie** przechodzi przez ten plik —
UI zapisuje go w Keychainie/Credential Managerze systemu operacyjnego
(`store_llm_key` / `get_llm_key` w `src-tauri/src/lib.rs`) i wysyła
per-request nagłówkiem `X-LLM-Key` (patrz `api/http_guard.py`,
`config/llm_providers.py`). `config.env` w app-data służy wyłącznie do
JWT secret / ścieżek danych / ew. zaawansowanych override'ów — nigdy do
kluczy dostawców LLM.
"""

from __future__ import annotations

import os
import secrets
import sys
import time
from pathlib import Path


def repo_root() -> Path:
    """Katalog główny repozytorium (rodzic `env_bootstrap.py`).

    W trybie frozen (PyInstaller `--onefile`) to jest katalog ekstrakcji
    (`_MEIPASS`) — efemeryczny, NIE używaj go do niczego, co ma przeżyć
    restart procesu. Do tego służy `app_data_dir()`.
    """
    return Path(__file__).resolve().parent


def is_frozen() -> bool:
    """True wewnątrz zamrożonej binarki PyInstaller (sidecar desktop)."""
    return bool(getattr(sys, "frozen", False))


def app_data_dir() -> Path:
    """Katalog danych aplikacji, trwały między uruchomieniami — per OS.

    Override: `AW_APP_DATA_DIR` (testy / uruchomienia niestandardowe).
    """
    override = (os.getenv("AW_APP_DATA_DIR") or "").strip()
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform.startswith("win"):
        base = Path(os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.getenv("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / "ArchitektWolnosci"


def resolve_dotenv_paths() -> list[Path]:
    """Kolejność ładowania: AW_ENV_FILE → .env (źródło prawdy) → src/.env (tylko VITE_*)."""
    explicit = os.getenv("AW_ENV_FILE", "").strip()
    if explicit:
        p = Path(explicit).expanduser()
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        return [p] if p.is_file() else []

    root = repo_root()
    paths: list[Path] = []
    primary = root / ".env"  # JEDYNE źródło prawdy sekretów/kluczy API (override=False → wygrywa)
    if primary.is_file():
        paths.append(primary)
    src_env = root / "src" / ".env"  # tylko VITE_* dla Vite/Tauri; uzupełnia brakujące
    if src_env.is_file():
        paths.append(src_env)
    return paths


def _fill_missing_from_dotenv(env_path: Path) -> None:
    """Wypełnia `os.environ` wartościami z `env_path` — tylko brakujące/puste klucze."""
    try:
        from dotenv import dotenv_values
    except ImportError:
        return
    try:
        vals = dotenv_values(env_path)
    except OSError:
        return
    for key, val in vals.items():
        if val is None:
            continue
        cur = os.environ.get(key)
        if cur is None or (isinstance(cur, str) and not cur.strip()):
            os.environ[key] = val


def _apply_boxed_defaults(*, read_dotenv: bool = True) -> None:
    """Tryb boxed (frozen sidecar): `config.env` + JWT secret + ścieżki danych
    poza katalogiem ekstrakcji. No-op poza trybem frozen.

    `read_dotenv=False` (gdy `AW_DISABLE_DOTENV=1`) pomija CZYTANIE `config.env`,
    ale nadal ustawia ścieżki danych i sekret — bez nich paczka nie ma jak
    wystartować. Review 2026-07-30: wcześniej `config.env` był czytany
    bezwarunkowo, czyli flaga „nie czytaj dotenv" czytała dotenv.
    """
    if not is_frozen():
        return

    data_dir = app_data_dir()
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "data").mkdir(exist_ok=True)
        (data_dir / "logs").mkdir(exist_ok=True)
    except OSError:
        pass

    config_env = data_dir / "config.env"
    if read_dotenv and config_env.is_file():
        _fill_missing_from_dotenv(config_env)

    # Boxed = dedykowany profil `AW_ENV=boxed` (api/settings.py: is_boxed/
    # security_hardened). NIE "produkcja" infrastrukturalnie (bez preflightu
    # Postgres/Redis/CORS — lokalny SQLite, jeden user), ale bramki
    # BEZPIECZEŃSTWA (BYOK fail-closed, brak /docs, zakaz AW_INSECURE_NO_AUTH)
    # działają jak w produkcji. Historia: wcześniejsze `development` naprawiało
    # crash (Tauri release ma NODE_ENV=production → ProductionConfigError bez
    # AW_CORS_ORIGINS), ale degradowało CAŁĄ posturę bezpieczeństwa do dev.
    #
    # RATCHET (zamknięcie furtki z review 2026-07-17): w zamrożonej paczce
    # AW_ENV może iść tylko W GÓRĘ. `production` z config.env wygrywa
    # (świadome zaostrzenie), ale `development`/cokolwiek innego NIE MOŻE
    # wyłączyć postury sprzedawanego pudełka jednym wpisem w plaintextowym
    # pliku (env-fallback klucza LLM, /docs, AW_INSECURE_NO_AUTH). Kto
    # świadomie potrzebuje dev — uruchamia repo, nie paczkę.
    _env = (os.environ.get("AW_ENV") or "").strip().lower()
    if _env not in ("production", "prod", "boxed"):
        if _env:
            print(
                f"[env_bootstrap] AW_ENV={_env!r} niedozwolone w paczce boxed — "
                "wymuszam 'boxed' (dozwolone: production/boxed).",
                file=sys.stderr,
            )
        os.environ["AW_ENV"] = "boxed"

    os.environ.setdefault("ARCHITEKT_DB_PATH", str(data_dir / "data" / "architekt.db"))
    os.environ.setdefault("COST_LOG_PATH", str(data_dir / "data" / "cost_log.jsonl"))
    os.environ.setdefault("EVENTS_LOG_PATH", str(data_dir / "data" / "events.jsonl"))

    if not (os.environ.get("ARCHITEKT_JWT_SECRET") or "").strip():
        secret = _ensure_jwt_secret(data_dir)
        if secret:
            os.environ["ARCHITEKT_JWT_SECRET"] = secret


def _ensure_jwt_secret(data_dir: Path) -> str | None:
    """Zwraca trwały sekret podpisujący sesje; tworzy go atomowo przy pierwszym uruchomieniu.

    DLACZEGO OSOBNY PLIK, NIE APPEND DO `config.env` (review 2026-07-30):
    poprzednia wersja przy dwóch równoległych first-runach generowała DWA
    sekrety i dopisywała OBA. Każdy proces zostawał ze swoim w pamięci, więc
    tokeny wydane przez jeden były odrzucane przez drugi — a komentarz w kodzie
    uspokajał, że „od następnego startu będzie ten sam". Dopisywanie do pliku
    nie ma żadnej semantyki wykluczania.

    Teraz: `O_CREAT | O_EXCL` na dedykowanym `jwt.secret` — dokładnie ten sam
    wzorzec, który ten projekt już stosuje w `core/device_seal._persisted_random_id`.
    Zwycięzca wyścigu zapisuje, przegrany dostaje `FileExistsError` i CZYTA
    to, co zapisał zwycięzca. Oba procesy kończą z tym samym sekretem
    natychmiast, nie „od następnego razu".

    Kompatybilność w tył: jeśli sekret leży już w `config.env` (paczki zbudowane
    przed tą zmianą), zostaje uszanowany — `_fill_missing_from_dotenv` wczytał go
    wcześniej, więc tu nawet nie dojdziemy.
    """
    path = data_dir / "jwt.secret"

    # Ktoś (poprzednie uruchomienie) już go utworzył.
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except OSError:
        pass

    new_secret = secrets.token_hex(32)
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        # 0600 od chwili powstania (os.open z mode, nie open()+chmod — bez okna
        # world-readable). Na Windows `mode` to no-op; realną ochroną jest tam
        # ACL profilu użytkownika na %APPDATA% (per-user by default) — nie
        # udajemy, że 0600 cokolwiek tam robi.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, new_secret.encode("utf-8"))
        finally:
            os.close(fd)
        return new_secret
    except FileExistsError:
        # Wyścig — czytamy sekret zwycięzcy. Retry, bo zwycięzca mógł jeszcze
        # nie zdążyć z `os.write` między naszym O_EXCL i tym odczytem.
        for _ in range(50):  # ~0.5 s
            try:
                existing = path.read_text(encoding="utf-8").strip()
                if existing:
                    return existing
            except OSError:
                pass
            time.sleep(0.01)
        print(
            f"[env_bootstrap] UWAGA: {path} istnieje, ale jest pusty — "
            "inny proces przerwał zapis. Używam sekretu tylko na czas tego procesu.",
            file=sys.stderr,
        )
        return new_secret
    except OSError as e:
        # Sekret działa do końca TEGO procesu, ale bez zapisu na dysk kolejny
        # restart wygeneruje nowy — czyli wyloguje użytkownika. Logger aplikacji
        # może nie być jeszcze skonfigurowany, więc stderr.
        print(
            f"[env_bootstrap] UWAGA: nie udało się zapisać {path} ({e}) — "
            "ARCHITEKT_JWT_SECRET nie przetrwa restartu aplikacji.",
            file=sys.stderr,
        )
        return new_secret


def load_repo_env() -> None:
    dotenv_enabled = os.getenv("AW_DISABLE_DOTENV", "").strip().lower() not in (
        "1",
        "true",
        "yes",
    )
    if dotenv_enabled:
        for env_path in resolve_dotenv_paths():
            _fill_missing_from_dotenv(env_path)

        try:
            from config.sponsor_runtime_loader import apply_sponsor_secrets_if_marked

            apply_sponsor_secrets_if_marked(repo_root())
        except ImportError:
            pass

    # Wołane ZAWSZE (no-op poza trybem frozen), bo bez ścieżek danych i sekretu
    # paczka nie wystartuje. `AW_DISABLE_DOTENV` honorowane w środku: wyłącza
    # CZYTANIE plików .env, nie ustawianie defaultów.
    _apply_boxed_defaults(read_dotenv=dotenv_enabled)
