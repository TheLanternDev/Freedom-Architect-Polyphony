# Propozycja ceny — Founders BYOK

**Status:** rekomendacja do decyzji S0.1. Nie jest wiążącą ofertą. Po akceptacji → wpisz do `PRICING.md`, `FOUNDERS_OFFER.md`, `GTM_DECISIONS.md`.
**Kanał płatności (zdecydowane):** LemonSqueezy (Merchant of Record).
**Model:** klient płaci Anthropic osobno (BYOK); ty sprzedajesz licencję na oprogramowanie.

---

## Dlaczego LemonSqueezy jest właściwym wyborem (a nie tylko Payment Link)

LemonSqueezy działa jako **Merchant of Record** — to on jest prawnym sprzedawcą wobec klienta. Dla solo-foundera z Polski sprzedającego cyfrowo do UE/świata oznacza to, że LemonSqueezy **przejmuje rozliczenie VAT/podatku** (VAT-OSS, podatek od sprzedaży w USA itd.). Nie musisz rejestrować VAT-OSS ani ręcznie naliczać stawek per kraj.

Koszt tej wygody: **5% + 0,50 USD** od transakcji (bazowo; +1,5% transakcje międzynarodowe, +1,5% PayPal). Brak opłaty miesięcznej.

**Implikacja dla ceny:** przy jednorazowej sprzedaży ~€150 prowizja to ≈ €8 — pomijalna względem wartości. Nie ma powodu zaniżać ceny pod kątem prowizji.

---

## Pozycjonowanie (dlaczego nie €49)

| Produkt-typ | Cena rynkowa | Czym jest |
|-------------|--------------|-----------|
| Utility BYOK (voice-to-text, lepszy UI dla GPT) | $49 | jeden feature, wrapper |
| Pro/Lifetime narzędzia deweloperskie (VibeRails) | $299 | warsztat pro, BYOK |
| **Architekt Wolności (BYOK founders)** | **propozycja niżej** | głęboki, wieloagentowy system decyzyjny — Rada 9 głosów + Syez, AKSJOMAT 0/1/2, tryb personal + fa2 |

Architekt **nie jest** wrapperem na czat. To jest najbliżej kategorii „warsztat pro", a wartością nie jest oszczędność czasu, tylko jakość decyzji życiowych i biznesowych. Cena €49 sygnalizowałaby „kolejne UI do Claude" i podkopała pozycjonowanie. Cena też pełni rolę filtra sygnału: zbyt nisko → przyciągasz przypadkowych użytkowników, nie founderów gotowych na głęboką pracę.

---

## Rekomendacja

**Cena founders (jednorazowo, lifetime na major version): €149 netto.**

Powód jednej liczby zamiast widełek: founderzy kupują zdecydowanie albo wcale; „od–do" osłabia ofertę. €149 to:

- wyraźnie powyżej kategorii „utility" (sygnalizuje głębię),
- poniżej progu, przy którym solo-founder oczekuje SLA / supportu 24-7 (którego świadomie nie dajesz — to jest w `FOUNDERS_OFFER.md`),
- czysta liczba psychologicznie (€149, nie €150).

### Warianty (jeśli chcesz testować)

| Wariant | Cena | Kiedy |
|---------|------|-------|
| **Founders (rekomendowany)** | **€149** | domyślny, pierwsze ~20–50 licencji |
| Early-bird (pierwszych 10) | €99 | jeśli potrzebujesz szybkich referencji/testimonials |
| Po fazie founders | €199–€249 | gdy są case studies i Tauri-buildy podpisane |
| Dodatek: podpisana binarka Tauri (mac+win) | wliczone | nie różnicuj — komplikuje ofertę |

**VAT/brutto:** LemonSqueezy dolicza podatek po stronie klienta automatycznie; podajesz **cenę netto €149**, klient widzi brutto wg swojej jurysdykcji. W ofercie pisz „€149 + VAT (nalicza LemonSqueezy)".

**PLN:** jeśli celujesz w polskich founderów, ustaw walutę wyświetlania PLN w LemonSqueezy (≈ 649 zł). Trzymaj jedną walutę bazową (EUR) dla spójności księgowej.

---

## Co cena NIE obejmuje (powtórz w ofercie — chroni Cię)

- Klucza API Anthropic (BYOK — klient płaci Anthropic bezpośrednio).
- Hostingu, SLA, supportu 24/7.
- Custom developmentu. Support = best-effort, instalacja wg `INSTALL.md`, 48h robocze.

---

## Najmniejszy następny krok

Zaakceptuj €149 (lub wskaż inną liczbę) → wpiszę ją w `PRICING.md` / `FOUNDERS_OFFER.md` / `GTM_DECISIONS.md` i usunę wszystkie `[DO UZUPEŁNIENIA]` dot. ceny w jednym przejściu.
