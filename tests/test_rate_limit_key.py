"""Rate limit key_func: per JWT `sub`, fallback IP."""

from __future__ import annotations

from types import SimpleNamespace

from api._rate_limit import jwt_or_ip_key


def _req(subject: str | None, client_ip: str = "1.2.3.4") -> SimpleNamespace:
    """Fake starlette.Request — tylko atrybuty których jwt_or_ip_key dotyka."""
    state = SimpleNamespace()
    if subject is not None:
        state.architekt_subject = subject
    return SimpleNamespace(
        state=state,
        client=SimpleNamespace(host=client_ip),
        headers={},
    )


def test_key_uses_jwt_sub_when_present():
    r = _req(subject="user-A")
    assert jwt_or_ip_key(r) == "u:user-A"


def test_key_isolates_users_with_same_ip():
    """Dwóch userów za tym samym NAT-em — różne klucze, niezależne buckety."""
    assert jwt_or_ip_key(_req("user-A", "10.0.0.1")) != jwt_or_ip_key(_req("user-B", "10.0.0.1"))


def test_key_falls_back_to_ip_without_jwt():
    r = _req(subject=None, client_ip="9.9.9.9")
    key = jwt_or_ip_key(r)
    assert key.startswith("ip:")
    assert "9.9.9.9" in key


def test_key_isolates_namespaces_user_vs_ip():
    """`u:foo` i `ip:foo` MUSZĄ być różne — inaczej IP może podszywać się pod sub."""
    assert jwt_or_ip_key(_req("foo")) != jwt_or_ip_key(_req(None, "foo"))
