"""
Test: każdy agent Rady ma w `get_full_instruction()` wstrzyknięte
postscriptum AKSJOMATU 2. Dodatkowo: gdy podany `dream`, jego kontekst
trafia na początek instrukcji.
"""

from agents import COUNCIL, SYNTHESIZER
from core.completion_enforcer import AGENT_COMPLETION_POSTSCRIPT
from core.dream_architect import distill_dream


def test_every_agent_has_postscript_in_full_instruction():
    for agent in COUNCIL + [SYNTHESIZER]:
        full = agent.get_full_instruction()
        assert AGENT_COMPLETION_POSTSCRIPT.strip() in full, (
            f"Agent {agent.name} nie ma wstrzykniętego AGENT_COMPLETION_POSTSCRIPT"
        )


def test_dream_context_prepended_when_provided():
    dream = distill_dream("Brief do testu kontekstu marzenia w agentach.")
    for agent in COUNCIL:
        full = agent.get_full_instruction(dream=dream)
        assert "ARCHITEKTURA MARZENIA" in full
        marzenie_idx = full.find("ARCHITEKTURA MARZENIA")
        instr_idx = full.find(agent.instruction)
        assert instr_idx != -1, (
            f"Tożsamość agenta {agent.name} musi być częścią full_instruction"
        )
        assert marzenie_idx < instr_idx, (
            f"Marzenie powinno być przed tożsamością agenta ({agent.name})"
        )
        postscript_idx = full.find(AGENT_COMPLETION_POSTSCRIPT.strip())
        assert postscript_idx > instr_idx, (
            f"Postscriptum AKSJOMATU 2 powinno być po tożsamości agenta ({agent.name})"
        )
