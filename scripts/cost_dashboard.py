"""
Cost dashboard dla Architekta Wolności v3.0.

Czyta cost_log.jsonl i pokazuje:
- koszt ostatniego briefu + najdroższy agent
- top koszty per agent / per model
- sumę dnia / wszech czasów

Użycie (z katalogu głównego repo):
    python3 scripts/cost_dashboard.py              # ostatni brief
    python3 scripts/cost_dashboard.py --today      # dzisiejszy total
    python3 scripts/cost_dashboard.py --all        # cały log, agregaty
    python3 scripts/cost_dashboard.py --brief HASH # konkretny brief po hashu
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = _REPO_ROOT / "cost_log.jsonl"


def _read_entries() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    entries: list[dict] = []
    with LOG_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _fmt_usd(v: float) -> str:
    return f"${v:.4f}"


def _print_brief(entries: list[dict], brief_hash: str) -> None:
    rows = [e for e in entries if e["brief_hash"] == brief_hash]
    if not rows:
        print(f"Brak wpisów dla brief_hash={brief_hash}")
        return

    total = sum(e["cost_usd"] for e in rows)
    by_agent: dict[str, float] = defaultdict(float)
    for e in rows:
        by_agent[e["agent"]] += e["cost_usd"]

    most_expensive_agent, most_expensive_cost = max(by_agent.items(), key=lambda x: x[1])

    print(f"\n📋 Brief: {brief_hash}")
    print(f"   Agentów w briefie : {len(by_agent)}")
    print(f"   Wywołań LLM        : {len(rows)}")
    print(f"   Koszt łączny       : {_fmt_usd(total)}")
    print(f"   Najdroższy agent   : {most_expensive_agent} ({_fmt_usd(most_expensive_cost)})")
    print()
    print("   Per agent:")
    for agent, c in sorted(by_agent.items(), key=lambda x: -x[1]):
        bar = "█" * max(1, int(c / total * 30))
        print(f"     {agent:<10} {_fmt_usd(c):>10}  {bar}")


def _print_last_brief(entries: list[dict]) -> None:
    if not entries:
        print("Pusty cost_log.jsonl — nie było jeszcze żadnych wywołań LLM.")
        return
    last_hash = entries[-1]["brief_hash"]
    _print_brief(entries, last_hash)


def _print_today(entries: list[dict]) -> None:
    today_iso = date.today().isoformat()
    rows = [e for e in entries if e["timestamp"].startswith(today_iso)]
    _print_aggregate(rows, title=f"📅 Dzisiaj ({today_iso})")


def _print_all(entries: list[dict]) -> None:
    _print_aggregate(entries, title="🌍 Cały log")


def _print_aggregate(entries: list[dict], title: str) -> None:
    if not entries:
        print(f"{title}: brak danych")
        return

    total = sum(e["cost_usd"] for e in entries)
    in_tok = sum(e["in_tokens"] for e in entries)
    out_tok = sum(e["out_tokens"] for e in entries)

    by_agent: dict[str, float] = defaultdict(float)
    by_model: dict[str, float] = defaultdict(float)
    briefs: set[str] = set()

    for e in entries:
        by_agent[e["agent"]] += e["cost_usd"]
        by_model[e["model"]] += e["cost_usd"]
        briefs.add(e["brief_hash"])

    print(f"\n{title}")
    print(f"   Briefów             : {len(briefs)}")
    print(f"   Wywołań LLM         : {len(entries)}")
    print(f"   Tokeny in/out       : {in_tok} / {out_tok}")
    print(f"   Koszt łączny        : {_fmt_usd(total)}")
    print(f"   Średnio per brief   : {_fmt_usd(total / max(1, len(briefs)))}")
    print()
    print("   Top agenci po koszcie:")
    for agent, c in sorted(by_agent.items(), key=lambda x: -x[1])[:10]:
        print(f"     {agent:<10} {_fmt_usd(c):>10}  ({c / total * 100:.1f}%)")
    print()
    print("   Per model:")
    for model, c in sorted(by_model.items(), key=lambda x: -x[1]):
        print(f"     {model:<32} {_fmt_usd(c):>10}  ({c / total * 100:.1f}%)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cost dashboard Architekta Wolności")
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--today", action="store_true", help="agregat dzisiejszego dnia")
    g.add_argument("--all", action="store_true", help="agregat całego loga")
    g.add_argument("--brief", type=str, help="konkretny brief_hash")
    args = parser.parse_args()

    entries = _read_entries()

    if args.today:
        _print_today(entries)
    elif args.all:
        _print_all(entries)
    elif args.brief:
        _print_brief(entries, args.brief)
    else:
        _print_last_brief(entries)
    return 0


if __name__ == "__main__":
    sys.exit(main())
