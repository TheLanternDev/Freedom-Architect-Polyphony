# Checklista sprzedażowa — Architekt Wolności (model: izolowana paczka lokalna)

**Data:** 2026-06-16 (zaktualizowana pod model local-first)
**Kontekst:** aplikacja przetwarza **dane szczególnej kategorii (zdrowie / uzależnienia,
art. 9 RODO)**.

> ⚠️ **Zastrzeżenie:** to nie jest porada prawna — mapa obszarów do konsultacji z
> kancelarią od RODO/IT, zwłaszcza warstwa danych zdrowotnych i pozycjonowanie produktu.

---

## Model dystrybucji (założenie nadrzędne — wszystko poniżej z niego wynika)

Każdy klient dostaje **wyizolowaną paczkę** Architekta:
- **bez kluczy API** — klient wstawia swój (BYOK),
- **bez wspólnej bazy** — tylko lokalny SQLite na maszynie klienta,
- **zbindowaną do urządzenia** (`core/device_seal`),
- **bez telemetrii** — aplikacja nie wysyła danych na zewnątrz (potwierdzone w kodzie).

**Konsekwencja prawna:** dane użytkownika (debaty, dreams, treści o zdrowiu) **nie
przechodzą przez Twoją infrastrukturę**. Klient jest administratorem swoich danych na
własnym urządzeniu; Ty dostarczasz oprogramowanie. To model „pudełkowy", nie SaaS —
radykalnie lżejszy reżim RODO po Twojej stronie.

> 🔒 **Warunek ważności tego re-scope'u:** trzyma się TYLKO dopóki sprzedajesz wyłącznie
> paczkę lokalną i **nie uruchamiasz hostingu** zbierającego dane klientów. Jeśli kiedyś
> ruszy wersja hostowana → reaktywują się obowiązki z Sekcji 1B i 2B (multi-tenant/RLS,
> administrator danych, DPA, DPIA na treści). Wtedy wróć do `CODE_REVIEW_2026-06-16.md`.

---

## Legenda
🔴 BLOKER · 🟠 przed publicznym startem · 🟢 równolegle · 💤 uśpione (tylko jeśli hosting)
✅ zrobione · 🔲 do zrobienia

---

## SEKCJA 1 — Bezpieczeństwo paczki lokalnej

### 1A — Aktywne w modelu local-first

- 🔲 🔴 **Szyfrowanie danych at-rest** — lokalny SQLite jest **plaintext**
  (`db/backend.py`). Na dysku klienta leżą dane o uzależnieniach. Opcje: SQLCipher,
  szyfrowanie pliku bazy kluczem z keychain OS, albo (minimum) **jawna informacja dla
  klienta**, że baza jest nieszyfrowana i odpowiada za zabezpieczenie swojego dysku.
  To zastępuje „izolację tenantów" jako główny punkt bezpieczeństwa.
- 🔲 🔴 **Lokalne przechowywanie klucza API klienta** — gdzie ląduje klucz BYOK
  (`llmKeyStorage.ts`)? Potwierdź, że nie trafia do logów ani plaintext w miejscu
  łatwym do podejrzenia; najlepiej keychain OS.
- 🔲 🟠 **Integralność paczki** — patrz Sekcja 4 (podpisywanie). Bez tego klient nie
  ma pewności, że paczka nie była zmodyfikowana.
- 🔲 🟢 Znalezisko D (review) — zawęzić zakres `shell.open` w `capabilities/default.json`.
- ✅ Device binding (`device_seal`) — anty-kopiowanie paczki na inną maszynę.
- ✅ Brak telemetrii / phone-home — potwierdzone.
- ✅ Brak hardkodowanego klucza w paczce — `.env` ignorowany, nie wchodzi do buildu.

### 1B — Uśpione (reaktywują się TYLKO przy wersji hostowanej)

- 💤 Test cross-tenant multi-user na Postgresie.
- 💤 Znalezisko A — handlery admin jako `DEFAULT_TENANT`.
- 💤 RLS / izolacja tenantów / weryfikacja konfiguracji serwera.
  (Kod izolacji zostaje w repo jako defense-in-depth — po prostu nieaktywny w paczce.)

---

## SEKCJA 2 — RODO (przesunięcie odpowiedzialności)

### 2A — Co przetwarzasz TY (lekkie, standardowe e-commerce)

Tylko dane sprzedażowe: e-mail, płatność, licencja/bindowanie.

- 🔲 🔴 **Polityka prywatności sprzedaży** — wąski zakres: e-mail, dane płatnicze,
  licencja. Bez danych zdrowotnych (one nie docierają do Ciebie).
- 🔲 🟠 **Podstawa przetwarzania danych sprzedażowych** — wykonanie umowy (art. 6 ust. 1 b).
- 🔲 🟢 Procedura usunięcia danych klienta sprzedażowego na żądanie.

### 2B — Co przetwarza KLIENT (Ty tylko dostarczasz narzędzie)

Treści w aplikacji + wywołania LLM kluczem klienta → przepływ klient → dostawca LLM,
**z pominięciem Ciebie**.

- 🔲 🔴 **Transparentność, nie kontrolerstwo** — w dokumentacji/EULA jasno: dane
  zostają lokalnie; przy korzystaniu z AI treści idą do dostawcy LLM **kluczem klienta**,
  więc to relacja klient ↔ dostawca LLM (np. Anthropic), nie przez Twój serwer.
- 🔲 🟠 **Wskazówka dla klienta-firmy** — jeśli klientem jest firma przetwarzająca dane
  swoich podopiecznych, to ona robi własną DPIA/DPA z dostawcą LLM. Ty dajesz materiał
  informacyjny, nie bierzesz tego na siebie.
- 💤 DPIA na treści / DPA z dostawcą LLM po Twojej stronie — **odpada**, dopóki nie
  hostujesz i nie używasz swojego klucza.

---

## SEKCJA 3 — Pozycjonowanie produktu (bez zmian, nadal krytyczne)

- 🔲 🔴 **Disclaimer: to nie pomoc medyczna ani terapeutyczna** — widoczny, zaakceptowany.
  Inaczej ryzyko reklasyfikacji jako wyrób medyczny (MDR).
- 🔲 🔴 **Brak roszczeń terapeutycznych** w marketingu i UI.
- 🔲 🟠 **Ścieżka kryzysowa** — kontakt do pomocy, gdy treści sygnalizują kryzys.

---

## SEKCJA 4 — Dystrybucja desktopa (twarda blokada, teraz WAŻNIEJSZA)

W modelu pudełkowym podpis to jedyny dowód integralności paczki dla klienta.

- 🔲 🔴 **Podpisywanie + notaryzacja macOS** — `signingIdentity` ustawione, notaryzacja Apple.
- 🔲 🔴 **Podpisywanie Windows** — `certificateThumbprint` (cert EV/OV) vs SmartScreen.
- 🔲 🟢 Kanał aktualizacji — jeśli updater, podpisany artefakt + bezpieczny feed.

---

## SEKCJA 5 — Forma prawna, podatki

- 🔲 🔴 **Forma działalności** — JDG vs sp. z o.o. (ograniczenie odpowiedzialności).
- 🔲 🔴 **VAT** — rejestracja; sprzedaż do UE → **VAT-OSS**.
- 🔲 🟠 Faktury zgodne z formą i krajem nabywcy.

---

## SEKCJA 6 — Prawo konsumenckie (akcent: licencja, nie SaaS)

- 🔲 🔴 **EULA / licencja na oprogramowanie** — w modelu pudełkowym to dokument główny
  (zakres licencji, bindowanie do urządzenia, brak gwarancji terapeutycznej).
- 🔲 🔴 **Prawo odstąpienia 14 dni** + klauzula zgody na rozpoczęcie świadczenia/pobranie
  przed terminem (inaczej tracisz zapłatę przy odstąpieniu od treści cyfrowej).
- 🔲 🟠 Jasna cena i warunki (jednorazowa licencja vs subskrypcja, odnowienia).

---

## SEKCJA 7 — Płatności

- 🔲 🟠 Operator — Stripe / Paddle (Paddle jako MoR zdejmuje część VAT) lub sklepy aplikacji.
- 🔲 🟢 Zgodność z regulaminem operatora dla treści zdrowotnych.

---

## SEKCJA 8 — AI Act / transparentność

- 🔲 🟠 Jawna informacja, że użytkownik rozmawia z AI (Rada).
- 🔲 🟢 Ujawnienie, że AI działa na kluczu/dostawcy klienta.

---

## Rekomendowana kolejność (zaktualizowana)

1. **🔴 Sekcja 1A** — szyfrowanie/ochrona danych at-rest + bezpieczne lokalne
   trzymanie klucza. To nowy fundament zamiast izolacji tenantów.
2. **🔴 Sekcja 3** — disclaimery medyczne (niezależne od architektury, zawsze krytyczne).
3. **🔴 Sekcja 4** — podpisywanie paczki (w modelu pudełkowym = dowód integralności).
4. **🔴 Sekcja 6** — EULA + odstąpienie; **🔴 Sekcja 5** — forma prawna i VAT.
5. **🟠/🟢** — reszta jako formalności uruchomieniowe.

> Co zniknęło względem wersji SaaS: ciężka DPIA na treści, DPA z dostawcą LLM po Twojej
> stronie, test cross-tenant, obowiązki administratora danych zdrowotnych. **Przeniosło
> się to na klienta i na model lokalny — pod warunkiem, że nie uruchomisz hostingu.**
> Co urosło: ochrona danych at-rest na dysku klienta i podpisywanie paczki.
