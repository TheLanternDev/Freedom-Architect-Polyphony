"""Stempel builda — tożsamość *tego konkretnego* artefaktu backendu.

Ten plik jest WERSJONOWANYM FALLBACKIEM (wartości „dev"). Przy zamrażaniu
paczki `scripts/build-backend-sidecar.sh` / `scripts/windows/build-backend-sidecar.ps1`
NADPISUJE go wygenerowanymi wartościami, PyInstaller wciąga nadpisaną wersję
do binarki (`--collect-submodules config`), a build script przywraca fallback
po zakończeniu — żeby drzewo źródeł nie zostało brudne.

Po co to istnieje (review 2026-07-30): binarka sidecara jest gitignorowana,
`npm run tauri:build` jej nie odbudowywał, a `/health` zwracał hardkod
`version: "3.3"`. Efekt: appka odpalona z ikony przez 8 dni serwowała
zamrożony backend STARSZY od kodu w repo i nie było jak tego zauważyć.
`build_id` w `/health` czyni rozjazd widocznym; `check-sidecar-fresh.mjs`
czyni go niemożliwym.

`build_id` w dev = "dev" (uruchomienie z repo, kod = to, co widzisz w edytorze).
"""

from __future__ import annotations

# Nadpisywane przy freeze: krótki hash gita + znacznik czasu, np. "a1b2c3d-202607301415".
BUILD_ID: str = "dev"
# ISO-8601 UTC. W dev pusty — źródłem prawdy jest mtime plików, nie stempel.
BUILT_AT: str = ""
# Pełny rev gita, z którego zamrożono binarkę ("" w dev).
GIT_REV: str = ""
# True tylko w zamrożonej paczce — odróżnia „dev z repo" od „artefakt builda".
FROZEN_BUILD: bool = False


def build_info() -> dict[str, object]:
    """Payload do `/health` — jedno miejsce, żeby kształt nie rozjechał się z konsumentami."""
    return {
        "build_id": BUILD_ID,
        "built_at": BUILT_AT,
        "git_rev": GIT_REV,
        "frozen_build": FROZEN_BUILD,
    }
