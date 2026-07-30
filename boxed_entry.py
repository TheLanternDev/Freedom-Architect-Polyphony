"""Punkt wejścia dla zamrożonej binarki sidecar (PyInstaller) — paczka desktop.

NIE używać do developmentu — tam nadal `uvicorn main:app --reload`
(patrz INSTALL.md). Ten plik jest celem builda:

    pyinstaller ... boxed_entry.py    (patrz scripts/build-backend-sidecar.sh
                                        i scripts/windows/build-backend-sidecar.ps1)

Wynikowa binarka (`architekt-backend-<target-triple>[.exe]`) jest sidecar-em
Tauri zadeklarowanym w `src/src-tauri/tauri.conf.json` → `bundle.externalBin`
i uruchamianym przez `src/src-tauri/src/lib.rs` (`app.shell().sidecar(...)`).

Świadomie BEZ `--reload` i BEZ multi-workera: PyInstaller `--onefile` nie
potrafi re-spawnować własnego modułu jako subproces — `--reload`/worker
uvicorna próbowałby `python -m uvicorn main:app`, czego w zamrożonej binarce
po prostu nie ma (jest jedna statycznie zlinkowana binarka, nie interpreter +
pliki źródłowe). Jeden proces, jeden worker — wystarczające dla pudełka
jednoosobowego (BYOK, single-tenant, local-first).
"""

from __future__ import annotations

import os


def _port() -> int:
    try:
        return int(os.environ.get("AW_BACKEND_PORT", "8000") or "8000")
    except ValueError:
        return 8000


_UVICORN_LEVELS = {"critical", "error", "warning", "info", "debug", "trace"}


def _log_level() -> str:
    """Walidacja AW_LOG_LEVEL: uvicorn przyjmuje TYLKO małe litery z listy —
    `AW_LOG_LEVEL=INFO` wywalałoby KeyError na starcie paczki."""
    lvl = (os.environ.get("AW_LOG_LEVEL") or "info").strip().lower()
    if lvl not in _UVICORN_LEVELS:
        import sys

        print(f"[boxed_entry] AW_LOG_LEVEL={lvl!r} nieznany — używam 'info'",
              file=sys.stderr)
        return "info"
    return lvl


def main() -> None:
    import uvicorn

    # Import obiektu `app` (nie stringa "main:app"): uvicorn potrafiłby
    # zresolvować string-factory nawet pod PyInstaller, ale bezpośredni
    # import jest przewidywalny i jednoznacznie uruchamia
    # `env_bootstrap.load_repo_env()` (gałąź frozen) przy imporcie `main.py`,
    # zanim uvicorn zacznie cokolwiek serwować.
    from main import app

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=_port(),
        log_level=_log_level(),
    )


if __name__ == "__main__":
    main()
