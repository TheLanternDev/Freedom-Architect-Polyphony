from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import OUTPUT_DIR

CACHE_PATH = OUTPUT_DIR / ".prompt_cache.json"
TTL_DAYS = 7


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _is_expired(ts: str) -> bool:
    age = datetime.now(timezone.utc) - _parse_ts(ts)
    return age.days >= TTL_DAYS


def cache_key_generate(
    prompt: str,
    *,
    resolution: str,
    duration: int,
    aspect_ratio: str,
) -> str:
    raw = f"{prompt}|{resolution}|{duration}|{aspect_ratio}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cache_key_edit(prompt: str, video_source: str) -> str:
    """Edit nie ma resolution/duration — klucz = prompt + hash źródła wideo."""
    src_hash = hashlib.sha256(video_source[:4096].encode("utf-8", errors="replace")).hexdigest()[:16]
    raw = f"{prompt}|edit|{src_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_raw() -> dict[str, Any]:
    if not CACHE_PATH.is_file():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_raw(data: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def lookup(key: str) -> dict[str, Any] | None:
    entry = _load_raw().get(key)
    if not entry:
        return None
    if _is_expired(entry.get("ts", "")):
        return None
    if not entry.get("video_url"):
        return None
    local = entry.get("local_path")
    if local and not Path(local).is_file():
        entry = dict(entry)
        entry["local_path"] = None
        return entry
    return entry


def store(
    key: str,
    *,
    video_url: str,
    local_path: str | None = None,
    session_id: str | None = None,
    iteration_id: str | None = None,
) -> None:
    data = _load_raw()
    data[key] = {
        "video_url": video_url,
        "local_path": local_path,
        "session_id": session_id,
        "iteration_id": iteration_id,
        "ts": _now_iso(),
    }
    _save_raw(data)


def update_meta(key: str, *, session_id: str, iteration_id: str, local_path: str | None = None) -> None:
    data = _load_raw()
    if key not in data:
        return
    data[key]["session_id"] = session_id
    data[key]["iteration_id"] = iteration_id
    if local_path:
        data[key]["local_path"] = local_path
    _save_raw(data)


def list_entries(*, include_expired: bool = False) -> list[tuple[str, dict[str, Any]]]:
    data = _load_raw()
    out: list[tuple[str, dict[str, Any]]] = []
    for key, entry in sorted(data.items(), key=lambda x: x[1].get("ts", ""), reverse=True):
        expired = _is_expired(entry.get("ts", ""))
        if expired and not include_expired:
            continue
        out.append((key, {**entry, "expired": expired}))
    return out


def clear(*, expired_only: bool = False) -> int:
    data = _load_raw()
    if not expired_only:
        count = len(data)
        _save_raw({})
        return count
    kept: dict[str, Any] = {}
    removed = 0
    for key, entry in data.items():
        if _is_expired(entry.get("ts", "")):
            removed += 1
        else:
            kept[key] = entry
    _save_raw(kept)
    return removed


def purge_expired() -> int:
    return clear(expired_only=True)
