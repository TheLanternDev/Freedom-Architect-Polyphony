"""Dev helper: równoległe głosy Rady + dashboard kosztów + pełna synteza."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agents import COUNCIL, afull_synthesis

B = "Klient chce CRM dla salonu fryzjerskiego za 15k PLN, deadline 6 tygodni"


async def adel(c):
    """9 głosów Rady równolegle — bez Syeza (jest osobnym orchestratorem)."""
    return "\n\n".join(
        f"── {a.identity()} ──\n{v}"
        for a, v in zip(COUNCIL, await asyncio.gather(*[a.acontribute(c) for a in COUNCIL]))
    )


async def main():
    print("===A START===")
    print(await adel(B))
    print("===A END===")

    print("===C START===")
    dash = _ROOT / "scripts" / "cost_dashboard.py"
    print(subprocess.run(["python3", str(dash)], capture_output=True, text=True).stdout)
    print("===C END===")

    print("===B START===")
    print(await afull_synthesis(B))
    print("===B END===")


asyncio.run(main())
