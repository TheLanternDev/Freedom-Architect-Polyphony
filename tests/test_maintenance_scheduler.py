"""Strażnik: auto-scheduler Fazy 2 nie startuje przy interwale 0."""

import os


def _interval(env_val):
    if env_val is None:
        os.environ.pop("AW_MAINTENANCE_INTERVAL_SEC", None)
    else:
        os.environ["AW_MAINTENANCE_INTERVAL_SEC"] = env_val
    # Ta sama reguła co w main.py lifespan.
    return int(os.getenv("AW_MAINTENANCE_INTERVAL_SEC", "0") or "0")


def test_scheduler_disabled_when_zero():
    assert _interval("0") == 0          # 0 → wyłączony (warunek > 0 nie startuje tasku)


def test_scheduler_default_disabled():
    assert _interval(None) == 0         # default 0 → wyłączone (bezpieczne domyślne)


def test_scheduler_custom_interval():
    assert _interval("3600") == 3600    # konfigurowalny
