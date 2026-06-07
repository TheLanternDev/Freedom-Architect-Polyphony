"""
Device Seal — miękkie powiązanie instalacji Architekta z jedną maszyną.

CEL (uzgodniony z użytkownikiem):
  Zatrzymać *leniwe* kopiowanie całego katalogu aplikacji (pendrive / chmura /
  skopiowany folder) na inny komputer. Przy pierwszym uruchomieniu zapisujemy
  "pieczęć" z fingerprintem maszyny. Każdy kolejny start weryfikuje zgodność;
  jeśli pieczęć została wygenerowana na innej maszynie → instalacja jest
  zablokowana (status "locked").

ŚWIADOME OGRANICZENIE (nie udajemy, że to twarda ochrona):
  • To jest enforcement PO STRONIE KLIENTA na maszynie użytkownika. Cały kod
    żyje na komputerze, który posiada (potencjalny) atakujący. Zdeterminowana
    osoba usunie ten moduł z bundla albo podmieni fingerprint. To NIE jest DRM
    nie do złamania — to bariera przeciw przypadkowemu/leniwemu kopiowaniu.
  • To NIE jest izolacja danych. Prywatność danych zapewnia auth (JWT per-user)
    + RLS w Postgresie. Device seal nie chroni ani jednego bajtu danych.

PIECZĘĆ ŻYJE POZA KATALOGIEM APLIKACJI:
  Plik trafia do ~/.architekt-wolnosci/device.seal (katalog domowy użytkownika),
  a NIE do folderu z kodem. Dzięki temu skopiowanie samego folderu aplikacji na
  pendrive NIE zabiera pieczęci — na nowej maszynie pieczęci brak → tam tworzy
  się nowa pieczęć dla nowego fingerprintu, a oryginalna maszyna dalej działa.
  Klucz: blokada wyzwala się, gdy pieczęć Z folderu/chmury (jeśli ktoś ją tam
  ręcznie wrzuci) lub przenoszona pieczęć NIE pasuje do bieżącej maszyny.

ODZYSKIWANIE (wymiana sprzętu / reinstalacja OS):
  `python -m tools.device_reset` — usuwa pieczęć, pozwalając przypisać nową
  maszynę. Patrz tools/device_reset.py.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

_SEAL_VERSION = 1

# Status weryfikacji pieczęci.
#   ok        — pieczęć pasuje do tej maszyny (lub właśnie ją utworzono)
#   locked    — pieczęć istnieje, ale pochodzi z INNEJ maszyny → blokada
#   disabled  — mechanizm wyłączony env-em (AW_DEVICE_BINDING=0)
SealStatus = Literal["ok", "locked", "disabled"]


def device_binding_enabled() -> bool:
    """Device binding domyślnie WŁĄCZONE. Wyłącz: AW_DEVICE_BINDING=0.

    Wyłączenie bywa potrzebne w CI/testach i w deploymencie z centralnym
    backendem (gdzie binding nie ma sensu — wiele maszyn klienckich).
    """
    return os.getenv("AW_DEVICE_BINDING", "1").strip().lower() not in ("0", "false", "no")


def _seal_dir() -> Path:
    """Katalog pieczęci POZA folderem aplikacji.

    Nadpisywalny env-em AW_DEVICE_SEAL_DIR (przydatne w testach — izolacja
    od realnej pieczęci użytkownika).
    """
    override = (os.getenv("AW_DEVICE_SEAL_DIR") or "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".architekt-wolnosci"


def _seal_path() -> Path:
    return _seal_dir() / "device.seal"


def _machine_fingerprint() -> str:
    """Stabilny-na-tej-maszynie, różny-między-maszynami odcisk.

    Składowe:
      • platform.system()  — np. "Darwin" / "Windows" / "Linux"
      • platform.node()    — hostname
      • uuid.getnode()     — MAC-based 48-bit node id (stabilny na maszynie)
      • platform.machine() — architektura (np. "arm64")

    Świadomie NIE używamy niczego, co zmienia się przy zwykłej aktualizacji
    aplikacji. uuid.getnode() bywa losowy gdy MAC niedostępny — wtedy
    fingerprint per-uruchomienie byłby niestabilny; akceptujemy to jako rzadki
    edge case (lepiej fałszywie "locked" niż fałszywie "ok"; reset jest tani).
    """
    parts = [
        platform.system(),
        platform.node(),
        platform.machine(),
        format(uuid.getnode(), "x"),
    ]
    raw = "|".join(p or "" for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SealCheck:
    status: SealStatus
    fingerprint_current: str
    fingerprint_sealed: str | None
    created_at: float | None


def _read_seal() -> dict | None:
    p = _seal_path()
    try:
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return data
    except Exception as e:  # noqa: BLE001 — uszkodzona pieczęć traktujemy jak brak
        logger.warning("device_seal: nie udało się odczytać pieczęci (%s) — traktuję jak brak", e)
        return None


def _write_seal(fingerprint: str) -> None:
    d = _seal_dir()
    d.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": _SEAL_VERSION,
        "fingerprint": fingerprint,
        "created_at": time.time(),
        "platform": platform.system(),
        "node": platform.node(),
    }
    tmp = _seal_path().with_suffix(".seal.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_seal_path())  # atomowy zapis
    try:
        os.chmod(_seal_path(), 0o600)  # tylko właściciel
    except OSError:
        pass


# Cache per-proces: device-gate woła to przy KAŻDYM żądaniu HTTP. Pieczęć i
# fingerprint nie zmieniają się w trakcie życia procesu (reset CLI i tak wymaga
# restartu aplikacji, by wpłynąć na ruch). Krótki TTL zostawia furtkę na zmianę
# bez kosztu I/O na każdy request.
_CACHE: dict[str, object] = {"check": None, "ts": 0.0}
_CACHE_TTL_SEC = 5.0


def ensure_and_verify(*, use_cache: bool = True) -> SealCheck:
    """Główny punkt wejścia. Wywoływany przy starcie i z /device/status.

    • binding wyłączony → status "disabled".
    • brak pieczęci    → tworzymy ją dla bieżącej maszyny → "ok" (first-run).
    • pieczęć pasuje   → "ok".
    • pieczęć z innej maszyny → "locked".
    """
    if use_cache:
        cached = _CACHE.get("check")
        ts = float(_CACHE.get("ts") or 0.0)
        if isinstance(cached, SealCheck) and (time.time() - ts) < _CACHE_TTL_SEC:
            return cached

    chk = _compute_check()
    _CACHE["check"] = chk
    _CACHE["ts"] = time.time()
    return chk


def _compute_check() -> SealCheck:
    current = _machine_fingerprint()

    if not device_binding_enabled():
        return SealCheck("disabled", current, None, None)

    existing = _read_seal()
    if existing is None:
        _write_seal(current)
        logger.info("device_seal: utworzono pieczęć dla tej maszyny (first-run).")
        return SealCheck("ok", current, current, time.time())

    sealed_fp = str(existing.get("fingerprint") or "")
    created_at = existing.get("created_at")
    created_at = float(created_at) if isinstance(created_at, (int, float)) else None

    if sealed_fp and sealed_fp == current:
        return SealCheck("ok", current, sealed_fp, created_at)

    logger.warning(
        "device_seal: pieczęć NIE pasuje do tej maszyny — instalacja zablokowana "
        "(sealed=%s… current=%s…). Kopia na inny komputer? Reset: python -m tools.device_reset",
        sealed_fp[:8],
        current[:8],
    )
    return SealCheck("locked", current, sealed_fp or None, created_at)


def _bust_cache() -> None:
    _CACHE["check"] = None
    _CACHE["ts"] = 0.0


def reset_seal() -> bool:
    """Usuwa pieczęć (ścieżka odzyskiwania). Zwraca True gdy plik istniał."""
    p = _seal_path()
    try:
        if p.exists():
            p.unlink()
            _bust_cache()
            logger.info("device_seal: pieczęć usunięta — następny start przypisze nową maszynę.")
            return True
        return False
    except OSError as e:
        logger.error("device_seal: nie udało się usunąć pieczęci: %s", e)
        raise


def rebind_to_current() -> str:
    """Przepisuje pieczęć na bieżącą maszynę (reset + nowy seal). Zwraca fingerprint."""
    fp = _machine_fingerprint()
    _write_seal(fp)
    _bust_cache()
    logger.info("device_seal: pieczęć przepięta na bieżącą maszynę.")
    return fp
