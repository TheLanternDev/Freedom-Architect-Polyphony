"""Faza 5: eksport zobowiązań i milestones do Notion, Todoist, Google Calendar."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


# ── Modele konfiguracji ──────────────────────────────────────────────────────


class NotionConfig(BaseModel):
    api_key: str = Field(..., min_length=10)
    database_id: str = Field(..., min_length=10)


class TodoistConfig(BaseModel):
    api_key: str = Field(..., min_length=10)
    project_id: Optional[str] = None


class CalendarConfig(BaseModel):
    calendar_id: str = Field(default="primary")
    credentials_json: Optional[str] = None


class ExportRequest(BaseModel):
    commitment_ids: list[int] = Field(default_factory=list)
    dream_id: Optional[str] = None


# ── Konfiguracja z ENV (nie przechowujemy sekretów w DB) ─────────────────────


def _notion_key() -> str:
    return (os.getenv("NOTION_API_KEY") or "").strip()


def _todoist_key() -> str:
    return (os.getenv("TODOIST_API_KEY") or "").strip()


def _gcal_id() -> str:
    return (os.getenv("GCAL_CALENDAR_ID") or "primary").strip()


def _guard_integrations_demo(request: Request) -> None:
    """Blokuje integracje dla sesji demo (tenant demo_*)."""
    from api.services.demo_guard import ensure_not_demo_blocked_route

    tenant_id = getattr(request.state, "architekt_tenant_id", None)
    ensure_not_demo_blocked_route(
        str(tenant_id) if tenant_id else None,
        "integracje",
    )


# ── Status integracji ────────────────────────────────────────────────────────


@router.get("/status")
async def integrations_status(request: Request):
    _guard_integrations_demo(request)
    """Zwraca, które integracje są skonfigurowane (nie ujawnia kluczy)."""
    return {
        "notion": {"configured": bool(_notion_key())},
        "todoist": {"configured": bool(_todoist_key())},
        "google_calendar": {
            "configured": bool(os.getenv("GCAL_CREDENTIALS_JSON")),
            "calendar_id": _gcal_id(),
        },
    }


# ── Notion ───────────────────────────────────────────────────────────────────


async def _notion_create_page(api_key: str, database_id: str, properties: dict) -> dict:
    import httpx

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            "https://api.notion.com/v1/pages",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
            json={"parent": {"database_id": database_id}, "properties": properties},
        )
        r.raise_for_status()
        return r.json()


@router.post("/notion/export")
async def export_to_notion(request: Request, req: ExportRequest):
    _guard_integrations_demo(request)
    api_key = _notion_key()
    db_id = (os.getenv("NOTION_DATABASE_ID") or "").strip()
    if not api_key or not db_id:
        raise HTTPException(400, "NOTION_API_KEY i NOTION_DATABASE_ID wymagane w ENV.")

    from db import get_db, repo

    results = []
    async for db in get_db():
        for cid in req.commitment_ids:
            rows = await repo.list_commitments_due(db, within_hours=8760)
            row = next((r for r in rows if r["id"] == cid), None)
            if not row:
                results.append({"commitment_id": cid, "ok": False, "error": "poza horyzontem follow-up"})
                continue
            props = {
                "Name": {"title": [{"text": {"content": row["text"][:200]}}]},
                "Status": {"select": {"name": row["status"]}},
            }
            if row.get("due_at"):
                props["Due"] = {"date": {"start": row["due_at"][:10]}}
            try:
                page = await _notion_create_page(api_key, db_id, props)
                results.append({"commitment_id": cid, "notion_page_id": page.get("id"), "ok": True})
            except Exception as e:
                results.append({"commitment_id": cid, "ok": False, "error": str(e)})

    return {"exported": results}


# ── Todoist ──────────────────────────────────────────────────────────────────


async def _todoist_create_task(api_key: str, content: str, due_string: str | None, project_id: str | None) -> dict:
    import httpx

    body: dict[str, Any] = {"content": content}
    if due_string:
        body["due_string"] = due_string
    if project_id:
        body["project_id"] = project_id

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            "https://api.todoist.com/rest/v2/tasks",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
        )
        r.raise_for_status()
        return r.json()


@router.post("/todoist/export")
async def export_to_todoist(request: Request, req: ExportRequest):
    _guard_integrations_demo(request)
    api_key = _todoist_key()
    if not api_key:
        raise HTTPException(400, "TODOIST_API_KEY wymagany w ENV.")

    project_id = (os.getenv("TODOIST_PROJECT_ID") or "").strip() or None
    from db import get_db, repo

    results = []
    async for db in get_db():
        for cid in req.commitment_ids:
            rows = await repo.list_commitments_due(db, within_hours=8760)
            row = next((r for r in rows if r["id"] == cid), None)
            if not row:
                results.append({"commitment_id": cid, "ok": False, "error": "poza horyzontem follow-up"})
                continue
            due = row.get("due_at", "")[:10] if row.get("due_at") else None
            try:
                task = await _todoist_create_task(api_key, row["text"][:500], due, project_id)
                results.append({"commitment_id": cid, "todoist_task_id": task.get("id"), "ok": True})
            except Exception as e:
                results.append({"commitment_id": cid, "ok": False, "error": str(e)})

    return {"exported": results}


# ── Google Calendar ──────────────────────────────────────────────────────────


@router.post("/gcal/export")
async def export_to_gcal(request: Request, req: ExportRequest):
    _guard_integrations_demo(request)
    creds_json = (os.getenv("GCAL_CREDENTIALS_JSON") or "").strip()
    if not creds_json:
        raise HTTPException(400, "GCAL_CREDENTIALS_JSON wymagany w ENV (service account JSON).")

    calendar_id = _gcal_id()
    from db import get_db, repo

    results = []
    async for db in get_db():
        for cid in req.commitment_ids:
            rows = await repo.list_commitments_due(db, within_hours=8760)
            row = next((r for r in rows if r["id"] == cid), None)
            if not row:
                results.append({"commitment_id": cid, "ok": False, "error": "poza horyzontem follow-up"})
                continue
            due = row.get("due_at") or row.get("follow_up_at")
            if not due:
                results.append({"commitment_id": cid, "ok": False, "error": "brak daty"})
                continue
            try:
                event = await _gcal_insert_event(creds_json, calendar_id, row["text"][:200], due[:10])
                results.append({"commitment_id": cid, "gcal_event_id": event.get("id"), "ok": True})
            except Exception as e:
                results.append({"commitment_id": cid, "ok": False, "error": str(e)})

    return {"exported": results}


async def _gcal_insert_event(creds_json: str, calendar_id: str, summary: str, date_str: str) -> dict:
    import httpx

    creds = json.loads(creds_json)
    token = await _get_gcal_access_token(creds)

    event_body = {
        "summary": f"[AW] {summary}",
        "start": {"date": date_str},
        "end": {"date": date_str},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=event_body,
        )
        r.raise_for_status()
        return r.json()


async def _get_gcal_access_token(creds: dict) -> str:
    """Minimal JWT assertion → access_token for service account."""
    import base64
    import hashlib
    import hmac
    import time

    import httpx

    now = int(time.time())
    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()).rstrip(b"=")
    claim = base64.urlsafe_b64encode(
        json.dumps(
            {
                "iss": creds["client_email"],
                "scope": "https://www.googleapis.com/auth/calendar.events",
                "aud": "https://oauth2.googleapis.com/token",
                "iat": now,
                "exp": now + 3600,
            }
        ).encode()
    ).rstrip(b"=")

    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        key = serialization.load_pem_private_key(creds["private_key"].encode(), password=None)
        signature = key.sign(header + b"." + claim, padding.PKCS1v15(), hashes.SHA256())  # type: ignore[union-attr]
    except ImportError:
        raise HTTPException(500, "cryptography package wymagany dla Google Calendar (pip install cryptography)")

    sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=")
    assertion = header.decode() + "." + claim.decode() + "." + sig_b64.decode()

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "https://oauth2.googleapis.com/token",
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
        )
        r.raise_for_status()
        return r.json()["access_token"]
