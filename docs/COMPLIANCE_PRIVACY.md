# Prywatność, RODO i dostawcy LLM

Ten dokument jest szkieletem operatorskim — nie stanowi porady prawnej. Uzupełnij go pod konkretny hosting, jurysdykcję i wybrane modele.

## Zakres danych

- **Brief**, kontekst debaty, syntezy i zapisy w SQLite/Postgres mogą zawierać dane osobowe lub szczególnie wrażliwe informacje (np. treści biograficzne).
- **Log kosztów** (`cost_log.jsonl`) może zawierać skróty kontekstu (`brief_hash`) — nie powinien zawierać pełnego tekstu briefu.

## Model A — BYOK lokalnie (oferta founders)

Ten model jest domyślny dla [FOUNDERS_OFFER.md](FOUNDERS_OFFER.md).

| Rola | Kto przetwarza dane debat | Uwagi |
|------|---------------------------|--------|
| **Administrator danych debat** | Użytkownik / kupujący | Plik SQLite (`ARCHITEKT_DB_PATH`) na jego maszynie |
| **Sprzedawca oprogramowania** | Dostawca licencji | Nie hostuje briefów przy czystym BYOK; e-mail support, ewentualnie faktura |
| **Dostawca LLM** | Anthropic / xAI / Ollama (użytkownik) | Umowa użytkownika z dostawcą API; briefy wychodzą z urządzenia użytkownika |

**Prawa użytkownika (lokalnie z JWT):**

- Eksport: `GET /account/export` lub UI Ustawienia → Prywatność.
- Usunięcie: `DELETE /account` z potwierdzeniem `USUŃ MOJE KONTO` — purge tenanta w bazie lokalnej.

**Retencja:** użytkownik kontroluje plik bazy i kopie zapasowe OS. Sprzedawca nie trzyma kopii debat, o ile nie hostuje backendu za użytkownika.

**Wersja demo (`demo_*`):** dane efemeryczne, bez eksportu RODO w API — patrz [DEMO.md](DEMO.md).

## Lokalnie vs chmura

- **Wyłącznie lokalnie (Tauri / localhost):** ryzyko transferu poza urządzenie jest niższe, nadal oceniaj kopie zapasowe dysku i synchronizację chmurową OS.
- **Backend w sieci:** każda debata to **transfer do dostawcy LLM** — potrzebna jest podstawa prawna (np. art. 6 RODO), transparentność i minimalizacja danych.

## RODO — checklista

1. **Informacja dla osób, których dane dotyczą** — cel, podstawa, odbiorcy (w tym dostawcy LLM), okres przechowywania, prawa (dostęp, usunięcie, sprzeciw itd.).
2. **Umowa powierzenia (DPA)** z hostingiem i innymi procesorami.
3. **Ocena skutków (DPIA)** gdy przetwarzasz treści wrażliwe lub na dużą skalę.
4. **Retencja:** jak długo trzymasz `debates`, logi serwera i kopie zapasowe DB.
5. **Prawo do usunięcia:** procedura kasowania rekordów + kopii przywróceniowych.

## Dostawcy LLM

Dla każdego używanego modelu (Anthropic, xAI itd.) zbierz na piśmie:

| Temat | Pytanie |
|-------|---------|
| Retencja promptów | Jak długo i w jakim celu dostawca przechowuje treść? |
| Szkolenie modeli | Czy zapytania mogą trafiać do treningu domyślnie i jak wyłączyć? |
| Region | Gdzie są regiony przetwarzania i jak je ustawić w koncie/API? |
| Podwykonawcy | Kto ma dostęp do infrastruktury (subprocessors)? |

Odnoś się do aktualnych warunków i dodatków poufności dostawcy dla wybranej warstwy API.

## Rekomendacja architektoniczna

- Publiczny frontend **bez** stałego `ARCHITEKT_API_KEY`; sesja użytkownika na BFF → JWT lub nagłówek serwisowy dodany **tylko** po stronie serwera (`docs/SECURITY_PRODUCTION.md`).
