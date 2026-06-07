"""Endpointy administracyjne (`/admin/*`) — ścieżka uprzywilejowana.

Wydzielone z `main.py` (tech-debt punkt 4): skupienie tras admin w jednym
module zmniejsza powierzchnię ataku i ułatwia audyt — każdy endpoint tutaj
MUSI przejść przez `_require_admin` (fail-closed na brak/zły `ARCHITEKT_ADMIN_TOKEN`).

UWAGA bezpieczeństwo: te trasy mają WŁASNĄ autoryzację bearer-tokenem i są
celowo pomijane przez `architekt_http_guard` (`_admin_self_auth_paths`), żeby
admin token nie kolidował z `Authorization` używanym do JWT (P0-A1). Auth jest
więc egzekwowane wyłącznie tutaj — nie osłabiać `_require_admin`.

Globalne z `main.py` (`_run_phase2_startup_tasks`, `get_db`, `DB_AVAILABLE`,
`COUNCIL`, `RADA_AVAILABLE`, `repo`) sięgamy lazy przez `import main as m`
WEWNĄTRZ handlerów — ten sam wzorzec co `api/routers/meta.py`, żeby uniknąć
cyklicznego importu przy ładowaniu modułu.
"""

from __future__ import annotations

import hmac
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from db import get_db  # `db` nie importuje `main` → brak cyklu (jak w main.py)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(authorization: Optional[str]) -> None:
    """Fail-closed: token zawsze wymagany; brak → 403, zły → 401.

    Stała ścieżka dla wszystkich tras admin — jedno miejsce do audytu auth.
    """
    admin_tok = (os.getenv("ARCHITEKT_ADMIN_TOKEN") or "").strip()
    if not admin_tok:
        raise HTTPException(
            status_code=403,
            detail="ARCHITEKT_ADMIN_TOKEN nie ustawiony — endpoint /admin wyłączony.",
        )
    auth = (authorization or "").strip()
    if not hmac.compare_digest(auth, f"Bearer {admin_tok}"):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing Authorization bearer for admin",
        )


@router.post("/trigger-followups")
async def admin_trigger_followups(
    authorization: Optional[str] = Header(None),
):
    """
    Idempotentny „kopniak" Fazy 2: przeterminowane follow-upy + synchronizacja projektów.

    Wymaga nagłówka `Authorization: Bearer <ARCHITEKT_ADMIN_TOKEN>`.
    Bez ustawionego tokenu endpoint jest wyłączony (fail-closed).
    """
    _require_admin(authorization)

    import main as m

    await m._run_phase2_startup_tasks()
    return {"ok": True}


@router.post("/rebuild-evolution")
async def admin_rebuild_evolution(
    authorization: Optional[str] = Header(None),
    db=Depends(get_db),
):
    """Przebudowuje rolling notatki ewolucyjne dla wszystkich agentów.

    Wymaga nagłówka `Authorization: Bearer <ARCHITEKT_ADMIN_TOKEN>`.
    Bez ustawionego tokenu endpoint jest wyłączony (fail-closed).
    """
    _require_admin(authorization)

    import main as m

    if not m.DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="DB niedostępna")

    try:
        from core.agent_learner import run_full_evolution_cycle

        agent_names = [a.name for a in m.COUNCIL] if m.RADA_AVAILABLE else []
        results = await run_full_evolution_cycle(db, m.repo, agent_names)
        await db.commit()
        return {"ok": True, "agents_updated": list(results.keys())}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("rebuild-evolution failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
