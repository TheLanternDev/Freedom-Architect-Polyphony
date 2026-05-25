"""Testy składu Rady Nadzorczej.

Przeniesione z personal_v1/tests/test_agents.py.
sys.path obsługiwany przez tests/conftest.py — nie potrzeba tu manipulacji.
"""
from agents import COUNCIL, SYNTHESIZER


def test_nine_agents():
    assert len(COUNCIL) == 9
    assert {a.name.lower() for a in COUNCIL} == {
        "relacjan",
        "kogit",
        "emojy",
        "deega",
        "smaty",
        "szow",
        "tai",
        "obver",
        "kidi",
    }


def test_syez_is_mirror():
    instr = getattr(SYNTHESIZER, "instruction_pl", None) or SYNTHESIZER.instruction
    assert "lustrem" in instr.lower()
