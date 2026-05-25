"""
Faza 4 — multi-user: ContextVar trzymający aktywny tenant_id dla bieżącego żądania.

• Single-user (brak JWT) → tenant_id = 'default' (wstecznie kompatybilne).
• JWT (sub/tenant_id claim) → middleware (`api.http_guard`) ustawia ContextVar
  na czas obsługi żądania, po czym przywraca poprzednią wartość.

Repo (`db.connection._Repo`) czyta ContextVar w każdym INSERT/SELECT —
nie trzeba przekazywać tenant_id przez wszystkie sygnatury.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

DEFAULT_TENANT = "default"

_current_tenant_id: ContextVar[str] = ContextVar(
    "architekt_current_tenant_id", default=DEFAULT_TENANT
)


def current_tenant_id() -> str:
    """Aktywny tenant_id dla bieżącego async-tasku."""
    return _current_tenant_id.get()


def set_current_tenant_id(tenant_id: str | None) -> Token[str]:
    """Ustawia tenant_id (Token do `reset_current_tenant_id`)."""
    tid = (tenant_id or "").strip() or DEFAULT_TENANT
    return _current_tenant_id.set(tid)


def reset_current_tenant_id(token: Token[str]) -> None:
    _current_tenant_id.reset(token)
