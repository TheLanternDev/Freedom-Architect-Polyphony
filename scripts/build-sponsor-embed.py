#!/usr/bin/env python3
"""build-sponsor-embed.py — generuje config/sponsor_payload.py (klucze zakodowane, nie w .env)."""
from __future__ import annotations

import base64
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

SECRET_KEYS = (
    "ANTHROPIC_API_KEY",
    "XAI_API_KEY",
    "LLM_BACKEND",
    "ARCHITEKT_JWT_SECRET",
    "REDIS_URL",
    "DAILY_BUDGET_USD",
    "AW_AGENT_EVOLUTION",
    "MAX_ACTIVE_PROJECTS",
    "STALE_DAYS_AT_RISK",
    "STALE_DAYS_STUCK",
    "COST_LOG_PATH",
)

PUBLIC_ENV_LINES = (
    "VITE_API_URL=http://127.0.0.1:8000",
    "AW_ENV=development",
    "AW_CORS_ORIGINS=http://localhost:1420,http://127.0.0.1:1420",
    "ARCHITEKT_DB_PATH=data/architekt.db",
)


def parse_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip()
    return out


def encode_value(value: str, salt: int) -> str:
    raw = value.encode("utf-8")
    xored = bytes(b ^ salt for b in raw)
    return base64.b64encode(xored).decode("ascii")


def build_payload_module(values: dict[str, str], salt: int) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    lines = [
        "# AUTO-GENERATED — paczka beta sponsorowana. Nie commituj.",
        f"# Wygenerowano: {stamp}",
        "from __future__ import annotations",
        "",
        f"SALT = {salt}",
        "BLOBS: dict[str, str] = {",
    ]
    for key in SECRET_KEYS:
        val = values.get(key)
        if not val:
            continue
        blob = encode_value(val, salt)
        lines.append(f'    "{key}": "{blob}",')
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def build_public_env() -> str:
    return (
        "# Paczka beta sponsorowana — bez sekretów (Vite / dev).\n"
        "# Klucze API wczytuje backend z config/sponsor_payload.py przy starcie.\n"
        + "\n".join(PUBLIC_ENV_LINES)
        + "\n"
    )


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "src" / ".env"
    staging = Path(sys.argv[2]) if len(sys.argv) > 2 else root

    if not source.is_file():
        print(f"Brak pliku źródłowego: {source}", file=sys.stderr)
        return 1

    values = parse_env(source)
    if not values.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY jest pusty w src/.env", file=sys.stderr)
        return 1
    if not values.get("ARCHITEKT_JWT_SECRET"):
        values["ARCHITEKT_JWT_SECRET"] = secrets.token_hex(32)
        print("→ Wygenerowano ARCHITEKT_JWT_SECRET dla paczki beta.")

    salt = secrets.randbelow(254) + 1
    payload_path = staging / "config" / "sponsor_payload.py"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(build_payload_module(values, salt), encoding="utf-8")

    env_path = staging / "src" / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(build_public_env(), encoding="utf-8")

    marker = staging / "BETA_SPONSOR.marker"
    marker.write_text("sponsor-beta\n", encoding="utf-8")

    print(f"→ config/sponsor_payload.py ({len(SECRET_KEYS)} slotów, salt={salt})")
    print("→ src/.env (tylko publiczne VITE/AW_*, bez kluczy API)")
    print("→ BETA_SPONSOR.marker")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
