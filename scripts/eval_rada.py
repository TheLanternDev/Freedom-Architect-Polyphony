"""CLI runner: odpala briefy z `evals/rada/briefs.yaml` przez `afull_synthesis`,
skoruje wypowiedzi heurystykami z `evals/rada/scorer.py` i zwraca raport
JSON + exit code 0/1 (do CI).

Użycie:
    python scripts/eval_rada.py                      # wszystkie briefy
    python scripts/eval_rada.py --brief personal_chronic_abandonment
    python scripts/eval_rada.py --offline             # bez LLM (heurystyki na pre-zapisanych odpowiedziach)

Bez `ANTHROPIC_API_KEY` przechodzi do fallback contribute (placeholder), więc
i tak przejdzie test "scorer się odpala bez błędu" — ale realny score będzie
niski. Realne evaly wymagają klucza i nie odpalają się w CI bez kosztu.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load_briefs():
    """Czyta YAML bez zależności (mini-parser dla naszej prostej struktury)."""
    try:
        import yaml
        return yaml.safe_load((ROOT / "evals" / "rada" / "briefs.yaml").read_text())["briefs"]
    except ImportError:
        print("Brak PyYAML — uruchom: pip install pyyaml", file=sys.stderr)
        sys.exit(2)


async def _run_one(brief: dict) -> dict:
    from agents import COUNCIL, SYNTHESIZER, adeliberate, _build_syez_input
    from evals.rada.scorer import score_agent, score_syez

    council_mode = brief.get("council_mode", "personal")
    description = brief["description"].strip()

    voices = await adeliberate(description, dream=None, language="pl",
                               debate_mode="pelna")
    voices_block = "\n\n".join(f"[{n}]\n{v}" for n, v in voices)
    syez_input = _build_syez_input(description, voices_block, None)
    synthesis = await SYNTHESIZER.acontribute(
        syez_input, dream=None, language="pl",
        debate_mode="pelna", council_mode=council_mode,
    )

    agent_by_name = {a.name: a for a in COUNCIL}
    agent_scores = [
        score_agent(name, agent_by_name[name].emoji, text).to_dict()
        for name, text in voices
    ]
    syez = score_syez(synthesis).to_dict()
    return {
        "brief_id": brief["id"],
        "council_mode": council_mode,
        "agent_scores": agent_scores,
        "syez_score": syez,
        "avg_agent_score": round(
            sum(s["score"] for s in agent_scores) / max(len(agent_scores), 1), 3
        ),
    }


async def _main_async(args) -> int:
    briefs = _load_briefs()
    if args.brief:
        briefs = [b for b in briefs if b["id"] == args.brief]
        if not briefs:
            print(f"Brak briefa '{args.brief}'", file=sys.stderr)
            return 2

    results = []
    for b in briefs:
        try:
            results.append(await _run_one(b))
        except Exception as e:
            results.append({"brief_id": b["id"], "error": f"{type(e).__name__}: {e}"})

    avg_total = (
        sum(r.get("avg_agent_score", 0) for r in results if "error" not in r)
        / max(sum(1 for r in results if "error" not in r), 1)
    )
    syez_avg = (
        sum(r["syez_score"]["score"] for r in results if "error" not in r)
        / max(sum(1 for r in results if "error" not in r), 1)
    )

    report = {
        "n_briefs": len(briefs),
        "avg_agent_score": round(avg_total, 3),
        "avg_syez_score": round(syez_avg, 3),
        "threshold": args.threshold,
        "passed": avg_total >= args.threshold and syez_avg >= args.threshold,
        "results": results,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--brief", help="id konkretnego briefa")
    p.add_argument("--threshold", type=float, default=0.6,
                   help="minimalny średni score dla pass (default 0.6)")
    args = p.parse_args()
    sys.exit(asyncio.run(_main_async(args)))


if __name__ == "__main__":
    main()
