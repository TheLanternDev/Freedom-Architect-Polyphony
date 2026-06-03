#!/usr/bin/env python3
"""
Live smoke test — działające API + opcjonalnie jedna debata z realnym LLM.

Wymaga:
  - uruchomionego backendu (domyślnie http://127.0.0.1:8000)
  - ANTHROPIC_API_KEY w środowisku (koszt ~$0.001–0.005 przy Haiku)

Użycie:
  source venv/bin/activate
  uvicorn main:app --host 127.0.0.1 --port 8000   # osobny terminal
  python scripts/smoke_live.py

Zmienne:
  SMOKE_API_BASE / VITE_API_URL — bazowy URL API
  SMOKE_SKIP_DEBATE=1 — tylko /health i /health/ready (bez kosztu LLM)
"""

from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BASE = "http://127.0.0.1:8000"
TIMEOUT = 120


def _base_url() -> str:
    raw = (
        os.getenv("SMOKE_API_BASE")
        or os.getenv("VITE_API_URL")
        or DEFAULT_BASE
    ).strip()
    return raw.rstrip("/")


def _get(path: str) -> dict:
    req = Request(f"{_base_url()}{path}", method="GET")
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _stream_debate() -> list[str]:
    payload = json.dumps(
        {
            "description": (
                "Smoke live: krótka decyzja testowa — czy warto dziś poświęcić "
                "60 minut na uporządkowanie jednego priorytetu?"
            ),
            "category": "decyzja",
            "mode": "codzienny",
        }
    ).encode("utf-8")
    req = Request(
        f"{_base_url()}/debate/stream",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    events: list[str] = []
    with urlopen(req, timeout=TIMEOUT) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if line.startswith("event: "):
                events.append(line[len("event: ") :])
    return events


def main() -> int:
    skip_debate = os.getenv("SMOKE_SKIP_DEBATE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if not skip_debate and not (os.getenv("ANTHROPIC_API_KEY") or "").strip():
        print(
            "ERROR: ustaw ANTHROPIC_API_KEY albo SMOKE_SKIP_DEBATE=1",
            file=sys.stderr,
        )
        return 1

    base = _base_url()
    print(f"Smoke live → {base}")

    try:
        health = _get("/health")
        ready = _get("/health/ready")
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"ERROR: API niedostępne ({exc})", file=sys.stderr)
        print("Uruchom: uvicorn main:app --host 127.0.0.1 --port 8000", file=sys.stderr)
        return 1

    print(f"  /health: status={health.get('status')}, redis={health.get('redis')}")
    print(f"  /health/ready: {ready}")

    if skip_debate:
        print("OK (health only, SMOKE_SKIP_DEBATE=1)")
        return 0

    print("  POST /debate/stream (LLM live)…")
    try:
        events = _stream_debate()
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"ERROR: debata nieudana ({exc})", file=sys.stderr)
        return 1

    agent_starts = events.count("agent_start")
    print(f"  eventy: {len(events)}, agent_start={agent_starts}")
    if agent_starts < 9:
        print(f"ERROR: oczekiwano 9 agent_start, jest {agent_starts}", file=sys.stderr)
        return 1
    if "synthesis_done" not in events or "debate_done" not in events:
        print("ERROR: brak synthesis_done lub debate_done", file=sys.stderr)
        return 1

    cost_path = os.getenv("COST_LOG_PATH", "data/cost_log.jsonl")
    if os.path.isfile(cost_path):
        print(f"  cost_log: {cost_path} (sprawdź przyrost wierszy)")
    else:
        print(f"  cost_log: brak pliku {cost_path} (opcjonalnie)")

    print("OK — smoke live zakończony")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
