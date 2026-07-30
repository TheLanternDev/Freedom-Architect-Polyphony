"""Cache SHA256(brief+agent) → odpowiedź.

Polityka dwutorowa:
- `personal_v1` (dane intymne: Cień, ciało, emocje) → **tylko in-memory**, bez dysku.
- `business_fa2` → plik szyfrowany Fernet (klucz w ~/.architekt/cache.key, 0600).
Klucz prefiksu agenta steruje wyborem: "fa2:..." → dysk; reszta → RAM.
TTL i znaczniki czasu zapobiegają zwracaniu starych „insightów" jako świeżych.
"""
from __future__ import annotations
import hashlib, json, logging, os, tempfile, time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_TTL = int(os.getenv("AW_CACHE_TTL", "86400"))  # 24h personal
_FA2_TTL = int(os.getenv("AW_FA2_CACHE_TTL", "604800"))  # 7d fa2
_DISABLED = os.getenv("DISABLE_CACHE", "").lower() in ("1","true","yes")

# in-memory dla personal_v1 (RAM-only, plaintext nigdy nie ląduje na dysku)
_mem: dict[str, tuple[float, str]] = {}

# dysk dla FA2 (szyfrowany)
_HOME = Path.home() / ".architekt"
_HOME.mkdir(parents=True, exist_ok=True, mode=0o700)
_KEY_FILE = _HOME / "cache.key"
_DISK_FILE = _HOME / "fa2_cache.bin"

try:
    from cryptography.fernet import Fernet, InvalidToken
    _HAVE_FERNET = True
except Exception:
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore
    _HAVE_FERNET = False

def _fernet() -> Optional["Fernet"]:
    """Klucz szyfrujący cache FA2 — tworzony przy pierwszym użyciu.

    Zapis przez temp + `os.replace` (review 2026-07-30). Poprzednia wersja
    (`O_EXCL`, potem `os.write`) domykała TOCTOU na uprawnieniach, ale otwierała
    NOWE okno: proces B dostawał `FileExistsError`, szedł do
    `Fernet(_KEY_FILE.read_bytes())` i przy pustym pliku (A jeszcze nie zapisał)
    dostawał `ValueError` — a `_save_disk`/`_load_disk` łapią tylko `OSError`,
    więc wyjątek leciał w górę ze ścieżki requestu. `os.replace` jest atomowy:
    plik pod docelową nazwą albo nie istnieje, albo jest kompletny.
    """
    if not _HAVE_FERNET:
        return None
    if not _KEY_FILE.exists():
        tmp = None
        try:
            fd, tmp = tempfile.mkstemp(dir=str(_HOME), prefix=".cache-key-", suffix=".tmp")
            try:
                os.write(fd, Fernet.generate_key())
            finally:
                os.close(fd)
            os.chmod(tmp, 0o600)
            # Nie nadpisujemy klucza, jeśli inny proces zdążył pierwszy —
            # nadpisanie unieważniłoby cache zapisany jego kluczem.
            if not _KEY_FILE.exists():
                os.replace(tmp, _KEY_FILE)
                tmp = None
        except OSError as e:
            logger.warning("cache: nie mogę utworzyć klucza szyfrującego (%s) — cache FA2 wyłączony.", e)
            return None
        finally:
            if tmp:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
    try:
        return Fernet(_KEY_FILE.read_bytes())
    except (OSError, ValueError) as e:
        # Uszkodzony/obcięty klucz nie może wywalić requestu — cache jest
        # optymalizacją, nie warunkiem odpowiedzi Rady.
        logger.warning("cache: klucz %s nieczytelny (%s) — cache FA2 wyłączony.", _KEY_FILE, e)
        return None

_disk: dict[str, tuple[float, str]] = {}
_disk_loaded = False

def _load_disk() -> None:
    global _disk_loaded
    if _disk_loaded: return
    _disk_loaded = True
    f = _fernet()
    if f is None or not _DISK_FILE.exists(): return
    try:
        raw = f.decrypt(_DISK_FILE.read_bytes())
        _disk.update({k: tuple(v) for k, v in json.loads(raw).items()})
    except (InvalidToken, json.JSONDecodeError, OSError):
        pass

def _save_disk() -> None:
    f = _fernet()
    if f is None: return
    try:
        _DISK_FILE.write_bytes(f.encrypt(json.dumps(_disk).encode()))
        try:
            _DISK_FILE.chmod(0o600)
        except OSError as e:
            logger.warning("cache: nie udało się ustawić 0600 na %s (%s) — szyfrowany cache może być czytelny dla innych.", _DISK_FILE, e)
    except OSError:
        pass

def _key(brief: str, agent: str) -> str:
    return hashlib.sha256(f"{brief}|{agent}".encode()).hexdigest()

def _is_fa2(agent: str) -> bool:
    return agent.startswith("fa2:")

def cache_get(brief: str, agent: str) -> Optional[str]:
    if _DISABLED or _skip_ctx.get(): return None
    k = _key(brief, agent)
    store = _disk if _is_fa2(agent) else _mem
    if _is_fa2(agent): _load_disk()
    entry = store.get(k)
    if not entry: return None
    ts, value = entry
    ttl = _FA2_TTL if _is_fa2(agent) else _DEFAULT_TTL
    if time.time() - ts > ttl:
        store.pop(k, None)
        if _is_fa2(agent): _save_disk()
        return None
    return value

def cache_set(brief: str, agent: str, value: str) -> None:
    if _DISABLED: return
    k = _key(brief, agent)
    entry = (time.time(), value)
    if _is_fa2(agent):
        _load_disk(); _disk[k] = entry; _save_disk()
    else:
        _mem[k] = entry

def cache_age(brief: str, agent: str) -> Optional[float]:
    store = _disk if _is_fa2(agent) else _mem
    if _is_fa2(agent): _load_disk()
    entry = store.get(_key(brief, agent))
    return None if not entry else time.time() - entry[0]

import contextvars as _cvars
_skip_ctx: _cvars.ContextVar[bool] = _cvars.ContextVar("cache_skip", default=False)

def cache_skip_set(skip: bool) -> object:
    return _skip_ctx.set(skip)

def cache_skip_reset(tok) -> None:
    _skip_ctx.reset(tok)

def cache_clear(prefix: str | None = None) -> int:
    """Czyści cache. prefix='fa2:' → tylko FA2; 'personal' → tylko RAM; None → wszystko."""
    n = 0
    if prefix in (None, "personal", "mem"):
        n += len(_mem); _mem.clear()
    if prefix in (None, "fa2", "fa2:", "disk"):
        _load_disk(); n += len(_disk); _disk.clear(); _save_disk()
    return n
