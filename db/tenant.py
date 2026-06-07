"""
Faza 4 — multi-user: ContextVar trzymający aktywny tenant_id dla bieżącego żądania.

• Single-user (brak JWT) → tenant_id = 'default' (wstecznie kompatybilne).
• JWT (sub/tenant_id claim) → middleware (`api.http_guard`) ustawia ContextVar
  na czas obsługi żądania, po czym przywraca poprzednią wartość.

Repo (`db.connection._Repo`) czyta ContextVar w każdym INSERT/SELECT —
nie trzeba przekazywać tenant_id przez wszystkie sygnatury.

═══ ŚWIADOMA DECYZJA: tenant_id ↔ user_id ═══
Kanon: docs/SECURITY_PRODUCTION.md → ADR-001 (kiedy/jak wprowadzić team-plan).
W obecnym modelu KAŻDY user jest swoim własnym tenantem. Middleware
ustawia tenant_id = JWT claim `tenant_id` LUB fallback do `sub`. Schemat DB
ma tylko kolumnę `tenant_id` (nie `user_id` per row), bo nie wspieramy
jeszcze team-plan (wielu userów w jednym tenancie).

Konsekwencje:
  • izolacja per-user JEST — przez `tenant_id := sub`.
  • RLS w Postgresie (migracja 0002) opiera się WYŁĄCZNIE na `tenant_id`.
  • `current_user_id()` (ContextVar) używany jest do izolacji cache LLM
    (BaseAgent._cache_key) — tam izolacja per-user MA sens nawet w
    przyszłym team-planie, bo różni userzy z tego samego tenanta mogą
    zadawać różne briefy.

Gdy zechcesz team-plan: dodaj kolumnę `user_id` do tabel z danymi
osobistymi (dreams, debates, projects, commitments), zaktualizuj RLS
o predykat `user_id = current_setting('architekt.user_id')`, i dopiero
wtedy oddzieli się "moje" od "współdzielone w teamie". Do tego czasu
upraszczamy: tenant = user.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

DEFAULT_TENANT = "default"
DEFAULT_USER = "default"

_current_tenant_id: ContextVar[str] = ContextVar(
    "architekt_current_tenant_id", default=DEFAULT_TENANT
)
_current_user_id: ContextVar[str] = ContextVar(
    "architekt_current_user_id", default=DEFAULT_USER
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


def current_user_id() -> str:
    """Aktywny user_id dla bieżącego async-tasku.

    Używany m.in. przez `BaseAgent._cache_key` do twardej izolacji cache LLM
    między userami w obrębie tego samego tenantu (claim `sub` z JWT)."""
    return _current_user_id.get()


def set_current_user_id(user_id: str | None) -> Token[str]:
    """Ustawia user_id (Token do `reset_current_user_id`)."""
    uid = (user_id or "").strip() or DEFAULT_USER
    return _current_user_id.set(uid)


def reset_current_user_id(token: Token[str]) -> None:
    _current_user_id.reset(token)
