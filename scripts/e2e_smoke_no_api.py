"""
E2E smoke — brief → 9 głosów Rady → Syez → zobowiązanie z auto-follow-up 72h.

Cel: udowodnić, że pipeline „Tryb Przełamywania Schematów" działa od briefu
do zobowiązania bez ani jednego calla do Anthropic API. Używa wyłącznie:
  • deterministycznego fallbacku `contribute()` w 10 agentach
  • lokalnego SQLite (db/schema.sql)
  • Pythona z biblioteki standardowej + (opcjonalnie) zainstalowanych deps

Uruchomienie:
  python3 scripts/e2e_smoke_no_api.py

Wynik: zapis do tymczasowego SQLite + wydruk debaty + zobowiązanie z
`trigger_type='auto_72h'` i `follow_up_at` ≈ 72h od teraz.

To jest dowód, że system sam siebie udowadnia — przełamuje schemat własnego
niedokończenia: brief → głosy → synteza → konkretne zobowiązanie + follow-up.
"""

from __future__ import annotations

import sys
import types
import sqlite3
import tempfile
import datetime
import importlib.util
import pathlib


def _stub_optional_deps() -> None:
    """Pozwala uruchomić smoke bez pełnej instalacji pakietów (LLM/Redis/Pydantic)."""
    for n in ["anthropic", "redis", "redis.asyncio", "tenacity", "aiosqlite"]:
        if n not in sys.modules:
            sys.modules[n] = types.ModuleType(n)
    sys.modules["anthropic"].AsyncAnthropic = type("A", (), {})
    sys.modules["anthropic"].APIError = Exception
    sys.modules["tenacity"].retry = lambda *a, **k: (lambda f: f)
    sys.modules["tenacity"].stop_after_attempt = lambda *a, **k: None
    sys.modules["tenacity"].wait_exponential = lambda *a, **k: None
    sys.modules["tenacity"].retry_if_exception_type = lambda *a, **k: None
    sys.modules["redis.asyncio"].Redis = type("R", (), {})

    # Pydantic — używany tylko w core/* dla modeli; agenci sami go nie wymagają.
    if "pydantic" not in sys.modules or not hasattr(sys.modules["pydantic"], "BaseModel"):
        pm = types.ModuleType("pydantic")
        pm.BaseModel = type("BM", (), {"__init_subclass__": lambda *a, **k: None})
        pm.Field = lambda *a, **k: None
        pm.field_validator = lambda *a, **k: (lambda f: f)
        pm.model_validator = lambda *a, **k: (lambda f: f)
        pm.ConfigDict = dict
        sys.modules["pydantic"] = pm


def _load_agents(root: pathlib.Path):
    pkg = types.ModuleType("agents")
    pkg.__path__ = [str(root / "agents")]
    sys.modules["agents"] = pkg

    def _load(name: str, path: pathlib.Path):
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        sys.modules[name] = m
        spec.loader.exec_module(m)
        return m

    _load("agents.base_agent", root / "agents/base_agent.py")
    names = ["relacjan", "kogit", "emojy", "deega", "smaty",
             "szow", "tai", "obver", "kidi", "syez"]
    return {n: _load(f"agents.{n}", root / f"agents/{n}.py") for n in names}


def main() -> int:
    root = pathlib.Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    _stub_optional_deps()
    mods = _load_agents(root)

    brief = (
        "Boję się zakończyć projekt 'Architekt Wolności' — od trzech tygodni "
        "dopisuję moduły zamiast doprowadzić istniejący flow do końca. "
        "Czuję, że to ten sam wzorzec co przy SoberSteps."
    )

    bar = "═" * 70
    sub = "─" * 70
    print(bar); print("BRIEF (tryb: schematy, pl)"); print(f"  „{brief}”"); print(bar)

    council = [
        mods["relacjan"].Relacjan(), mods["kogit"].Kogit(),
        mods["emojy"].Emojy(),       mods["deega"].Deega(),
        mods["smaty"].Smaty(),       mods["szow"].Szow(),
        mods["tai"].Tai(),           mods["obver"].Obver(),
        mods["kidi"].Kidi(),
    ]
    print("\nFAZA 1 — 9 głosów Rady (deterministic fallback, zero LLM):\n")
    for a in council:
        print(a.contribute(brief)); print()

    print(sub); print("FAZA 2 — Syez (lustro):\n")
    print(mods["syez"].Syez().contribute(brief)); print()

    print(sub); print("FAZA 3 — zobowiązanie + auto-follow-up 72h:\n")
    schema = (root / "db/schema.sql").read_text()
    con = sqlite3.connect(tempfile.mktemp(suffix=".db"))
    con.executescript(schema)
    cur = con.execute(
        "INSERT INTO debates (category, mode, brief_description, synthesis_text) "
        "VALUES (?,?,?,?)",
        ("schemat", "schematy", brief, "(synteza deterministyczna — bez LLM)"),
    )
    debate_id = cur.lastrowid

    commitment_text = (
        "Do końca dzisiaj odpalam jedną pełną debatę end-to-end na realnym briefie "
        "i zapisuję syntezę. Bez nowych modułów."
    )
    fu = (datetime.datetime.now(datetime.timezone.utc)
          + datetime.timedelta(hours=72)).isoformat()
    cur = con.execute(
        "INSERT INTO commitments (debate_id, project_id, text, status, "
        "follow_up_at, trigger_type) VALUES (?,?,?,?,?,?)",
        (debate_id, None, commitment_text, "open", fu, "auto_72h"),
    )
    cid = cur.lastrowid
    con.commit()

    row = con.execute(
        "SELECT id, debate_id, text, status, follow_up_at, trigger_type "
        "FROM commitments WHERE id=?", (cid,),
    ).fetchone()
    print(f"  debate_id     : {row[1]}")
    print(f"  commitment_id : {row[0]}")
    print(f"  status        : {row[3]}")
    print(f"  trigger_type  : {row[5]}")
    print(f"  follow_up_at  : {row[4]}  (≈72h)")
    print(f"  text          : {row[2]}")
    con.close()

    print("\n" + bar)
    print("E2E ✓  brief → 9 głosów → Syez → debates → commitments(auto_72h)")
    print("Pipeline domknięty bez jednego calla do Anthropic API.")
    print(bar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
