"""
Heurystyczny „monitor napięć” między parami agentów podczas debaty.

Miarą jest odwrócone pokrycie słów (Jaccard na tokenach ≥4 znaki). Nie jest to
semantyczna analiza sentymentu — sygnał dla UI: które głosy mniej/n bardziej
nachodzą na siebie leksykalnie.
"""

from __future__ import annotations

import re
from typing import Any, TypedDict

_TOKEN_RE = re.compile(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]{4,}", re.UNICODE)


class PairFriction(TypedDict):
    a: str
    b: str
    intensity: float  # 0–1, wyżej = większe „napięcie leksykalne”


def _tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")}


def compute_live_pair_frictions(
    council_names: list[str],
    voices: dict[str, str],
    *,
    max_pairs: int = 16,
) -> list[dict[str, Any]]:
    pairs: list[PairFriction] = []
    names = [n for n in council_names if n in voices]
    for i, na in enumerate(names):
        for nb in names[i + 1 :]:
            ta, tb = _tokens(voices.get(na, "")), _tokens(voices.get(nb, ""))
            if not ta or not tb:
                intensity = 0.42
            else:
                inter = len(ta & tb)
                union = len(ta | tb)
                jacc = inter / max(1, union)
                intensity = min(1.0, max(0.22, 1.0 - 2.2 * jacc))
            pairs.append({"a": na, "b": nb, "intensity": round(float(intensity), 2)})
    pairs.sort(key=lambda x: x["intensity"], reverse=True)
    return pairs[:max_pairs]
