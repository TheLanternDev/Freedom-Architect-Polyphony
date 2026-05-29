"""Ładowanie zakodowanych sekretów paczki beta sponsorowanej (bez pliku .env)."""
from __future__ import annotations

import base64
import os


def encode_value(value: str, salt: int) -> str:
    raw = value.encode("utf-8")
    xored = bytes(b ^ salt for b in raw)
    return base64.b64encode(xored).decode("ascii")


def apply_payload(blobs: dict[str, str], salt: int) -> None:
    """Dekoduje bloby XOR+base64 i ustawia os.environ (tylko paczka sponsorowana)."""
    for key, blob in blobs.items():
        if not blob:
            continue
        raw = base64.b64decode(blob.encode("ascii"))
        plain = bytes(b ^ salt for b in raw).decode("utf-8")
        os.environ[key] = plain


def apply_sponsor_secrets_if_marked(repo_root) -> bool:
    """Gdy istnieje BETA_SPONSOR.marker — wczytaj config/sponsor_payload.py z dysku."""
    import importlib.util
    from pathlib import Path

    root = Path(repo_root)
    if not (root / "BETA_SPONSOR.marker").is_file():
        return False
    payload_path = root / "config" / "sponsor_payload.py"
    if not payload_path.is_file():
        return False
    spec = importlib.util.spec_from_file_location("_aw_sponsor_payload", payload_path)
    if spec is None or spec.loader is None:
        return False
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    apply_payload(mod.BLOBS, mod.SALT)
    return True
