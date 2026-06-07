"""
Reset pieczęci urządzenia — ścieżka odzyskiwania przy wymianie sprzętu /
reinstalacji systemu / przeniesieniu na nowy komputer.

Użycie:
    python -m tools.device_reset            # pokaż status + zapytaj
    python -m tools.device_reset --status   # tylko status, nic nie zmienia
    python -m tools.device_reset --rebind   # od razu przepnij na TĘ maszynę
    python -m tools.device_reset --yes      # usuń pieczęć bez pytania

Po resecie następny start aplikacji utworzy nową pieczęć dla bieżącej maszyny.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

# Ładujemy core/device_seal.py BEZPOŚREDNIO z pliku, z pominięciem core/__init__.py.
# Dlaczego: core/__init__ eagerly importuje dream_architect → pydantic itd.
# Narzędzie odzyskiwania MUSI działać nawet gdy ciężkie zależności są zepsute
# (to ostatnia deska ratunku przy zablokowanym urządzeniu). device_seal sam w
# sobie nie ma żadnych zależności poza stdlib.
_ROOT = Path(__file__).resolve().parent.parent
_SEAL_SRC = _ROOT / "core" / "device_seal.py"
_spec = importlib.util.spec_from_file_location("_aw_device_seal", _SEAL_SRC)
assert _spec and _spec.loader, f"Nie znaleziono modułu pieczęci: {_SEAL_SRC}"
_ds = importlib.util.module_from_spec(_spec)
sys.modules["_aw_device_seal"] = _ds  # wymagane przez @dataclass
_spec.loader.exec_module(_ds)

_seal_path = _ds._seal_path
ensure_and_verify = _ds.ensure_and_verify
rebind_to_current = _ds.rebind_to_current
reset_seal = _ds.reset_seal


def _print_status() -> None:
    chk = ensure_and_verify()
    print(f"Pieczęć urządzenia: {_seal_path()}")
    print(f"  status:               {chk.status}")
    print(f"  fingerprint (ta maszyna): {chk.fingerprint_current[:16]}…")
    if chk.fingerprint_sealed:
        print(f"  fingerprint (pieczęć):    {chk.fingerprint_sealed[:16]}…")
    if chk.status == "locked":
        print("\n  ⚠️  Pieczęć pochodzi z INNEJ maszyny — instalacja zablokowana.")
        print("      Jeśli to Twój nowy sprzęt, użyj --rebind albo --yes.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Reset pieczęci urządzenia Architekta.")
    ap.add_argument("--status", action="store_true", help="tylko pokaż status")
    ap.add_argument("--rebind", action="store_true", help="przepnij pieczęć na tę maszynę")
    ap.add_argument("--yes", action="store_true", help="usuń pieczęć bez pytania")
    args = ap.parse_args(argv)

    _print_status()

    if args.status:
        return 0

    if args.rebind:
        fp = rebind_to_current()
        print(f"\n✅ Pieczęć przepięta na tę maszynę (fingerprint {fp[:16]}…).")
        return 0

    if not args.yes:
        print()
        ans = input("Usunąć pieczęć i pozwolić przypisać nową maszynę? [t/N] ").strip().lower()
        if ans not in ("t", "tak", "y", "yes"):
            print("Anulowano — nic nie zmieniono.")
            return 1

    existed = reset_seal()
    if existed:
        print("\n✅ Pieczęć usunięta. Następny start aplikacji przypisze tę maszynę.")
    else:
        print("\nℹ️  Pieczęć nie istniała — nic do usunięcia.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
