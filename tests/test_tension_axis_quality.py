"""C5 — niezmienniki build_tension_axis po naprawie (#3/#4):
brak ```mermaid w `why`, brak pustych `why`, brak ucięć mid-word, pole-label fa2."""
from __future__ import annotations

from api.services.debate_orchestrator import build_tension_axis

_VOICES = {n: f"głos {n}" for n in ["Smaty", "Tai", "Kidi", "Kogit", "Obver"]}
_PAIRS = [
    {"a": "Smaty", "b": "Tai", "intensity": 0.77},
    {"a": "Kidi", "b": "Kogit", "intensity": 0.74},
    {"a": "Obver", "b": "Tai", "intensity": 0.71},  # para bez zdania w prozie → fallback
]

# Proza z blokiem mermaid, którego etykiety zawierają imiona agentów (zatruwacz #3),
# oraz jednym bardzo długim zdaniem (test przycięcia C3).
_LONG = "Smaty i Tai są w napięciu, " + "bo " * 120 + "to się różni."
_SYNTH = (
    _LONG + "\n\n```mermaid\nflowchart LR\n  Smaty[\"Smaty\"] --> Tai[\"Tai\"]\n"
    "  Kidi[\"Kidi\"] --> Kogit[\"Kogit\"]\n```\n\nKoniec."
)


def test_tension_axis_invariants_fa2():
    ax = build_tension_axis(_VOICES, _PAIRS, _SYNTH, "fa2")
    assert ax is not None
    whys = [t["why"] for t in ax["tensions"]]

    # 1. żaden `why`/core nie zawiera surowego mermaida
    blobs = whys + [ax["central_axis"]["core"]]
    assert all("```" not in w and "mermaid" not in w and "flowchart" not in w for w in blobs), blobs

    # 2. brak pustych `why`
    assert all(w.strip() for w in whys), whys

    # 3. brak ucięć mid-word: jeśli „…" to znak przed nim nie jest literą-w-środku
    #    (akceptujemy „…" tylko po granicy słowa lub pełnym zdaniu)
    for w in whys:
        assert "  " not in w  # brak podwójnych spacji po stripie fence
        if w.endswith("…"):
            assert not w[-2].isspace()  # „…" doklejone do słowa, nie do spacji
            assert len(w) <= 205

    # 4. fallback dla pary bez zdania (Obver↔Tai): zaczyna się od „Napięcie na osi"
    obver_tai = next(t for t in ax["tensions"] if set(t["between"]) == {"Obver", "Tai"})
    assert obver_tai["why"].startswith("Napięcie na osi")
    assert obver_tai["prose_anchor"] is None

    # 5. pole-label trybo-zależny dla fa2
    assert ax["axis_label"].startswith("rejestr myślenia")


def test_axis_label_personal_default():
    ax = build_tension_axis(_VOICES, _PAIRS, "Smaty i Tai różnią się.", "personal")
    assert ax["axis_label"] == "structural ↔ somatic ↔ cień"
