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
import re
import secrets
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

_SEAL_VERSION = 1
# Wersja ALGORYTMU fingerprinta (osobna od wersji formatu pliku).
#   1 — system|node|machine|hex(uuid.getnode())  [niestabilny getnode/hostname]
#   2 — system|stable_machine_id|machine         [IOPlatformUUID/MachineGuid/machine-id]
# Zmiana algorytmu BEZ migracji = każdy istniejący użytkownik dostaje po
# update fałszywe "locked". Stąd `_legacy_fingerprints()` + auto re-seal
# w `_compute_check()` — zamiast blokady przepisujemy pieczęć na nowy algorytm,
# zachowując created_at.
_FP_VERSION = 2

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
      • platform.machine() — architektura (np. "arm64")

    UWAGA: świadomie BEZ uuid.getnode() (MAC-based node id). Empirycznie
    niestabilny per-proces na macOS (Private Wi-Fi Address / brak realnego
    MAC → losowy 48-bit fallback per wywołanie, zob. dokumentacja `uuid`
    stdlib) — co realnie blokowało legalnego, jedynego użytkownika na jego
    własnej maszynie po wygaśnięciu 5s cache'u (żądanie N: "ok", żądanie
    N+1 kilka sekund później: inny losowy node id → "locked"). Dla miękkiej
    bariery przeciw leniwemu kopiowaniu folderu wystarczy hostname +
    system + architektura; fałszywe blokady realnego usera są gorsze niż
    nieco słabszy fingerprint.
    """
    parts = [
        platform.system(),
        _stable_machine_id(),
        platform.machine(),
    ]
    raw = "|".join(p or "" for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _legacy_fingerprints() -> list[str]:
    """Fingerprinty wg HISTORYCZNYCH algorytmów (do migracji, nie do zapisu).

    v1 zawierał uuid.getnode() — jeśli MAC jest dziś niedostępny, getnode
    zwraca wartość losową i v1 się nie odtworzy; wtedy migracja się nie uda
    i użytkownik przejdzie przez `tools.device_reset` (stan sprzed fixa,
    nie regresja). Gdy MAC jest stabilny — typowy przypadek — user po update
    dostaje ciche przepięcie zamiast fałszywego "locked"."""
    out: list[str] = []
    try:
        raw_v1 = "|".join(
            p or ""
            for p in (
                platform.system(),
                platform.node(),
                platform.machine(),
                format(uuid.getnode(), "x"),
            )
        )
        out.append(hashlib.sha256(raw_v1.encode("utf-8")).hexdigest())
    except Exception:  # noqa: BLE001 — migracja jest best-effort
        pass
    return out


def _stable_machine_id() -> str:
    """Identyfikator maszyny odporny na zmiany hostname/mDNS.

    EMPIRIA (2026-07-07, MacBook Pro Patryka): platform.node() (hostname)
    okazał się NIESTABILNY między kolejnymi uruchomieniami tej samej appki
    na tej samej maszynie (obserwowane 3 różne fingerprinty w ciągu kilku
    minut) — najpewniej macOS dopisuje/zmienia sufiks Bonjour (.local,
    -2.local...) przy konfliktach mDNS. To dawało fałszywe "locked" i
    blokowało Business Mode bez żadnej realnej zmiany sprzętu.

    Per-OS (ta sama klasa false-locka co macOS dotyczy hostname wszędzie —
    Windows rename/dołączenie do domeny, Linux DHCP/cloud-init):
      • macOS   — IOPlatformUUID (ioreg; stały per-urządzenie, niezależny od sieci)
      • Windows — MachineGuid (HKLM\\SOFTWARE\\Microsoft\\Cryptography, winreg)
      • Linux   — /etc/machine-id (fallback /var/lib/dbus/machine-id)
    Fallback wszędzie: TRWAŁY losowy ID zapisany w katalogu pieczęci
    (`machine.id`) — NIE platform.node(), który przywracałby dokładnie tę
    klasę false-locków (mDNS/DHCP/rename), którą ten moduł naprawia.

    ZNANE OGRANICZENIE (świadome): /etc/machine-id jest IDENTYCZNY w
    sklonowanych VM-kach/obrazach docker zbudowanych z jednego wzorca —
    tam seal przepuści kopię. Dla miękkiej bariery przeciw leniwemu
    kopiowaniu folderu na fizycznych maszynach użytkowników to akceptowalny
    kompromis; twardsze związanie (dmi product_uuid) wymaga roota i nie
    wchodzi w model "lokalna appka bez uprawnień".

    Memoizacja per-proces: ID sprzętu nie zmienia się w trakcie życia
    procesu, a bez niej każde wygaśnięcie 5s cache'u seal-checka odpalałoby
    subprocess ioreg na ścieżce requestu.
    """
    global _MACHINE_ID_CACHE
    if _MACHINE_ID_CACHE is None:
        _MACHINE_ID_CACHE = _read_machine_id()
    return _MACHINE_ID_CACHE


_MACHINE_ID_CACHE: str | None = None


def _read_machine_id() -> str:
    system = platform.system()
    try:
        if system == "Darwin":
            out = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True,
                text=True,
                timeout=2,
            ).stdout
            # Format: `"IOPlatformUUID" = "XXXXXXXX-..."` — regex zamiast
            # split('"')[-2], który cicho zwracał śmieci przy zmianie formatu.
            m = re.search(r'"IOPlatformUUID"\s*=\s*"([0-9A-Fa-f-]+)"', out)
            if m:
                return m.group(1)
        elif system == "Windows":
            import winreg  # stdlib, tylko Windows

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
            ) as key:
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                if isinstance(guid, str) and guid.strip():
                    return guid.strip()
        elif system == "Linux":
            for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                try:
                    mid = Path(p).read_text(encoding="utf-8").strip()
                    if mid:
                        return mid
                except OSError:
                    continue
    except Exception:  # noqa: BLE001 — brak ioreg/rejestru nie może wywalić startu
        pass
    return _persisted_random_id()


def _persisted_random_id() -> str:
    """Ostatnia linia obrony: losowy ID wygenerowany RAZ i utrwalony w
    katalogu pieczęci. Stabilny między uruchomieniami (w przeciwieństwie do
    platform.node()) i per-instalacja unikalny. Żyje POZA folderem aplikacji
    (jak pieczęć), więc kopia samego folderu go nie przenosi. Jeśli nawet
    zapis się nie uda (RO filesystem), degradujemy do platform.node() —
    świadomie, z logiem."""
    p = _seal_dir() / "machine.id"
    try:
        mid = p.read_text(encoding="utf-8").strip()
        if mid:
            return mid
    except OSError:
        pass
    mid = secrets.token_hex(16)
    try:
        _seal_dir().mkdir(parents=True, exist_ok=True)
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, mid.encode("utf-8"))
        finally:
            os.close(fd)
        return mid
    except FileExistsError:
        # wyścig z innym procesem — czytamy to, co zapisał zwycięzca
        try:
            existing = p.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        except OSError:
            pass
        return mid
    except OSError as e:
        logger.warning(
            "device_seal: nie mogę utrwalić machine.id (%s) — degraduję do "
            "platform.node(); fingerprint może być niestabilny między startami.",
            e,
        )
        return platform.node()


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


def _write_seal(fingerprint: str, *, created_at: float | None = None) -> None:
    """`created_at`: przy migracji algorytmu zachowujemy ORYGINALNY czas
    utworzenia pieczęci — re-seal to nie nowa instalacja."""
    d = _seal_dir()
    d.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": _SEAL_VERSION,
        "fp_version": _FP_VERSION,
        "fingerprint": fingerprint,
        "created_at": created_at if created_at is not None else time.time(),
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
        # Opportunistyczny upgrade metadanych (fp_version) przy okazji zgodności.
        if int(existing.get("fp_version") or 1) < _FP_VERSION:
            _write_seal(current, created_at=created_at)
        return SealCheck("ok", current, sealed_fp, created_at)

    # MIGRACJA: pieczęć zapisana STARYM algorytmem na TEJ SAMEJ maszynie
    # nie jest kopią — to nasz własny update. Przepisujemy na bieżący
    # algorytm zamiast fałszywego "locked" po aktualizacji aplikacji.
    if sealed_fp and sealed_fp in _legacy_fingerprints():
        _write_seal(current, created_at=created_at)
        logger.info(
            "device_seal: pieczęć zmigrowana ze starego algorytmu fingerprinta "
            "(fp_version→%d) — ta sama maszyna, bez blokady.",
            _FP_VERSION,
        )
        return SealCheck("ok", current, current, created_at)

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
