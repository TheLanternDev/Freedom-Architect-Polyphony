"""Heurystyczny scorer FA2 (Freedom Architect Business)."""

from __future__ import annotations

from evals.rada.scorer import score_syez_fa2


def _full_fa2(extra: str = "") -> str:
    """Pełna FA2 synteza spełniająca wszystkie 6 checków (≥600 słów)."""
    base = (
        "Wybieram niszę RevOps tooling dla Head of Operations w firmach 20-200 "
        "osób. Uzasadnienie liczbowe oparte na danych z trzech źródeł: ICP "
        "spreadsheet, raport HubSpot 2024 oraz wywiady. CAC w tym segmencie "
        "LinkedIn-driven to $800-2500, LTV $8000-30000, marża brutto 70%+. "
        "Runway pozwala na 12 miesięcy egzekucji bez seed funding. Tech stack: "
        "FastAPI + Supabase + Stripe, Vercel dla landing page, HubSpot dla CRM, "
        "ahrefs do SEO research. Decyzja stack-owa oparta na trzech wymiarach: "
        "koszt utrzymania, learning curve, deployment friction. Każdy z tych "
        "elementów został zważony przeciw alternatywom (AWS, Salesforce, Django) "
        "w macierzy decyzyjnej. \n\n"
        "Scenariusz BASE (realistyczny, 12 miesięcy): 30 płacących klientów, "
        "$15K MRR przy końcu roku, churn 6% miesięcznie, conversion z trial 18%. "
        "Marża brutto 72%, koszt operacyjny $3K/miesiąc, gross profit positive "
        "od miesiąca 4. Break-even na poziomie $5K MRR, osiągany w miesiącu 6. "
        "Stack utility cost: $400/miesiąc (Supabase Pro, Stripe fee, Vercel Pro). \n\n"
        "Scenariusz BULL (wszystko idzie dobrze, 12 miesięcy): 60 klientów, "
        "$35K MRR, conversion z trial wzrasta do 22% dzięki viralowi w LinkedIn, "
        "retention 96%. Zatrudnienie pierwszego sales person w miesiącu 8, drugi "
        "engineer w miesiącu 10. Cash position wystarczający do zaproszenia "
        "seed funding na własnych warunkach (valuation $4-5M). \n\n"
        "Scenariusz BEAR (główne ryzyko materializuje się, 12 miesięcy): CAC "
        "rośnie do $4000 przez konkurencję, runway kończy się przy 18 klientach. "
        "Plan przetrwania: cut burn do $1.5K/miesiąc, pivot na consulting jako "
        "bridge revenue, downscale stack (Supabase free tier, własny VPS). "
        "Czerwone flagi do monitorowania: payback period >18 miesięcy, "
        "conversion trial <12%, NPS <30, churn >10%. \n\n"
        "```mermaid\nflowchart TD\nA[Lead z LinkedIn] --> B[Trial signup]\n"
        "B --> C[Onboarding call]\nC --> D{Decyzja}\nD -->|tak| E[Płacący klient]\n"
        "D -->|nie| F[Re-engagement sequence]\nE --> G[Retention loop]\n```\n\n"
        "Wdrożenie krok po kroku: Tydzień 1 — landing page + waitlist (Vercel + "
        "Tailwind). Miesiąc 1 — pierwsze 10 demo calls z ICP, walidacja briefu. "
        "Miesiąc 3 — closed beta z 5 płacącymi pilots ($199/miesiąc per seat). "
        "Miesiąc 6 — otwarcie self-serve signup, $5K MRR target. \n\n"
        "Trzy pytania otwarte do założyciela, wymagają odpowiedzi przed "
        "wydaniem pierwszej złotówki na marketing: \n"
        "1. Co zrobisz, jeśli CAC przekroczy $3000 w pierwszym kwartale — czy "
        "masz emocjonalny próg porzucenia czy podwójnego kliknięcia?\n"
        "2. Kogo zatrudnisz pierwszego — sales czy engineera — gdy MRR "
        "przekroczy $10K i przy jakich konkretnych metrykach?\n"
        "3. Jaki jest twój próg porażki — przy jakim MRR i jakiej runway "
        "powiesz dość, świadomie zarchiwizujesz projekt i wrócisz do konsultingu?\n\n"
        "Struktura kosztów (Base): hosting Vercel $40, Supabase Pro $25, "
        "Stripe fees ~2.9% volumetric, HubSpot Starter $50, ahrefs $99, domena "
        "$15/rok, designer freelance $500/miesiąc (kwartalnie). Łącznie fixed "
        "$215, variable scale-up z liczbą klientów. Nie planuję employer "
        "branding ani office space w pierwszym roku.\n\n"
        "Struktura przychodów (Base): seat-based pricing $99/seat/miesiąc, "
        "średnio 3 seats per klient, ARPU $297. Przy 30 klientach ARR $107K. "
        "Bull case ARPU rośnie do $450 dzięki upsellingu Advanced Analytics. "
        "Bear case ARPU spada do $199 wymuszone konkurencją cenową.\n\n"
        "Model akwizycji w Base: 60% LinkedIn outbound (ICP Head of Ops), "
        "25% organic SEO long-tail, 15% referrals z pilots. Każdy kanał ma "
        "własny tracking, własny CAC target i własne progi escalation. "
        "LinkedIn driven posiada highest intent ale highest cost; SEO odwrotnie.\n\n"
        "Ryzyka operacyjne i ich mitigation: (a) churn przekraczający 8% "
        "miesięcznie — odpowiedź quarterly business review z każdym klientem; "
        "(b) burnout solofoundera — 1 dzień off-call tygodniowo; (c) "
        "konkurencja zamykająca nasz segment — quarterly competitive review.\n\n"
        "Decyzje wymagające drugiego myślenia w miesiącu 6: czy zatrudniać "
        "sales SDR czy founder-led sales kontynuuje; czy podnieść pricing "
        "do $149/seat; czy rozszerzyć ICP o firmy 200-500 osób; czy aplikować "
        "do akceleratora typu YC W26 batch.\n"
    )
    return base + extra


def test_fa2_full_synthesis_passes_all_checks():
    s = score_syez_fa2(_full_fa2())
    assert s.score == 1.0
    assert "three_scenarios" in s.passed_checks
    assert "mermaid_diagram" in s.passed_checks
    assert "min_three_open_questions" in s.passed_checks
    assert "stack_concrete" in s.passed_checks
    assert "business_metrics_present" in s.passed_checks
    assert "length_in_range" in s.passed_checks


def test_fa2_fails_without_bull_scenario():
    """Case-insensitive replace — fixture ma 'BULL' i 'Bull' w różnych miejscach."""
    import re as _re
    text = _re.sub(r"bull", "alternatywny", _full_fa2(), flags=_re.IGNORECASE)
    s = score_syez_fa2(text)
    assert "three_scenarios" in s.failed_checks


def test_fa2_fails_without_mermaid():
    text = _full_fa2().replace("```mermaid", "```text").replace("flowchart", "linear")
    s = score_syez_fa2(text)
    assert "mermaid_diagram" in s.failed_checks


def test_fa2_fails_with_too_few_open_questions():
    text = _full_fa2().split("Trzy pytania")[0] + "Jedno pytanie: czy starczy ci runway?"
    s = score_syez_fa2(text)
    assert "min_three_open_questions" in s.failed_checks


def test_fa2_fails_without_stack_mention():
    """Synteza bez konkretnego stacku — kontrakt FA2 wymaga nazw platform."""
    text = (
        "Wybieram niszę. Scenariusz BASE — 30 klientów. BULL — 60. BEAR — 10.\n"
        "```mermaid\nflowchart\nA-->B\n```\n"
        "Pyt 1? Pyt 2? Pyt 3?"
    ) + " " + ("x " * 700)  # padding na długość
    s = score_syez_fa2(text)
    assert "stack_concrete" in s.failed_checks


def test_fa2_detects_metrics_keywords():
    text = "BASE BULL BEAR mermaid flowchart ? ? ? CAC LTV margin FastAPI " * 50
    s = score_syez_fa2(text)
    assert "business_metrics_present" in s.passed_checks


def test_fa2_fails_too_short():
    text = "BASE BULL BEAR ```mermaid\nflowchart\n``` ? ? ? FastAPI CAC"
    s = score_syez_fa2(text)
    assert "length_in_range" in s.failed_checks
