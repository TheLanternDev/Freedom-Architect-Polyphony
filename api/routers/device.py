"""
Device binding — status pieczęci urządzenia (miękkie powiązanie z maszyną).

GET /device/status jest PUBLICZNY (bez auth): SPA musi móc sprawdzić, czy
instalacja nie jest zablokowana, ZANIM pokaże ekran logowania. Endpoint nie
ujawnia pełnych fingerprintów — tylko skrócone prefiksy do diagnostyki.
"""

from __future__ import annotations

from fastapi import APIRouter

from core.device_seal import ensure_and_verify

router = APIRouter(prefix="/device", tags=["device"])


@router.get("/status")
async def device_status() -> dict[str, object]:
    chk = ensure_and_verify()
    return {
        "status": chk.status,  # "ok" | "locked" | "disabled"
        "locked": chk.status == "locked",
        "binding_enabled": chk.status != "disabled",
        "fingerprint_current": chk.fingerprint_current[:12],
        "fingerprint_sealed": (chk.fingerprint_sealed[:12] if chk.fingerprint_sealed else None),
        "created_at": chk.created_at,
    }
