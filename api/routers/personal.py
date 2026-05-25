"""Endpointy „personal mode": onboarding (20 pytań), codzienny rytuał."""
from __future__ import annotations
from fastapi import APIRouter

from personal_v1.rituals.onboarding import PYTANIA as ONBOARDING_PYTANIA
from personal_v1.rituals.daily import PYTANIA_PORANNE, PYTANIA_WIECZORNE

router = APIRouter(prefix="/personal", tags=["personal"])

@router.get("/onboarding/questions")
def onboarding_questions():
    return {"items": ONBOARDING_PYTANIA, "ton": "lagodny", "tempo": "ile_chcesz"}

@router.get("/ritual/daily")
def ritual_daily():
    return {"poranek": PYTANIA_PORANNE, "wieczor": PYTANIA_WIECZORNE}
