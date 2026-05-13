from core.live_tensions import compute_live_pair_frictions


def test_live_tensions_orders_pairs():
    names = ["A", "B", "C"]
    voices = {
        "A": "budżet monet czas harmonogram ryzyko koszt",
        "B": "budżet monet czas harmonogram ryzyko koszt podobnie",
        "C": "łąka pszczoły kwiat ogród natura spokój",
    }
    pairs = compute_live_pair_frictions(names, voices, max_pairs=8)
    assert pairs
    # A–B duże pokrycie → niższa intensywność niż A–C lub B–C
    key_ab = next((p for p in pairs if {p["a"], p["b"]} == {"A", "B"}), None)
    key_ac = next((p for p in pairs if {p["a"], p["b"]} == {"A", "C"}), None)
    assert key_ab and key_ac
    assert key_ac["intensity"] >= key_ab["intensity"]
