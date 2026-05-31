"""
Wspólna funkcja `key_func` dla slowapi.

Domyślne `get_remote_address` traktuje wszystko jako jeden user gdy klienci są
za NAT-em (jeden IP = wielu userów dzieli limit) i pozwala obejść limit przez
VPN/rotację IP (różny IP = nowy bucket).

Lepiej: JWT `sub` jest stabilny i jednoznacznie identyfikuje usera niezależnie
od sieci. Middleware `api.http_guard` zapisuje `sub` w `request.state.architekt_subject`
po weryfikacji JWT (HS256), więc tutaj tylko go odczytujemy. Gdy go nie ma
(legacy bearer / brak auth / błąd weryfikacji) — fallback do IP, żeby
endpointy publiczne (np. `/auth/login`) nie zostały bez ochrony.
"""

from __future__ import annotations

from slowapi.util import get_remote_address
from starlette.requests import Request


def jwt_or_ip_key(request: Request) -> str:
    """key_func dla slowapi: per-JWT-`sub` z fallbackiem na IP.

    Wartości są prefiksowane, żeby przestrzenie kluczy się nie kolidowały
    w Redisie:
      • `u:<sub>` — autentykowany request (limit per user, niezależny od sieci)
      • `ip:<adres>` — request bez ważnego JWT (login, password reset, etc.)
    """
    sub = getattr(request.state, "architekt_subject", None)
    if sub:
        return f"u:{sub}"
    return f"ip:{get_remote_address(request)}"
