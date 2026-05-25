"""Cache SHA256(brief+agent) → odpowiedź.

Polityka dwutorowa:
- `personal_v1` (dane intymne: Cień, ciało, emocje) → **tylko in-memory**, bez dysku.
- `business_fa2` → plik szyfrowany Fernet (klucz w ~/.architekt/cache.key, 0600).
Klucz prefiksu agenta steruje wyborem: "fa2:..." → dysk; reszta → RAM.
TTL i znaczniki czasu zapobiegają zwracaniu starych „insightów" jako świeżych.
"""
from __future__ import annotations
import hashlib, json, os, time
from pathlib import Path
from typing import Optional

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
    if not _HAVE_FERNET:
        return None
    if not _KEY_FILE.exists():
        _KEY_FILE.write_bytes(Fernet.generate_key())
        try: _KEY_FILE.chmod(0o600)
        except Exception: pass
    return Fernet(_KEY_FILE.read_bytes())

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
        try: _DISK_FILE.chmod(0o600)
        except Exception: pass
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
