# Oferta founders (model A — lokalnie, BYOK)

Dokument **marketingowy / produktowy**, nie umowa. Cenę, VAT i warunki prawne ustal z księgowością i prawnikiem ([LEGAL_PRIORITIES_FOR_COUNSEL.md](LEGAL_PRIORITIES_FOR_COUNSEL.md)). Parametry handlowe: [GTM_DECISIONS.md](GTM_DECISIONS.md).

## Co kupujesz

- Prawo do używania dostarczonej **paczki** aplikacji Architekt Wolności (backend Python + UI React/Tauri) zgodnie z licencją przy zakupie.
- **Bring your own key:** koszt modeli LLM ponosisz u dostawcy API (Anthropic lub Ollama lokalnie); sprzedawca **nie hostuje** Twoich debat ani briefów na swoim serwerze.

### Co dostajesz (artefakty)

| Artefakt | Opis |
|----------|------|
| Archiwum `.tar.gz` / `.zip` | Zbudowane [`scripts/pack-founders-archive.sh`](../scripts/pack-founders-archive.sh) — bez sekretów w repo |
| `CZYTAJ_MNIE.txt` + `INSTALL.md` | Pierwsze kroki po rozpakowaniu |
| Opcjonalnie binarka Tauri | macOS arm64 / Windows x64 — procedura [TAURI_RELEASE.md](TAURI_RELEASE.md) |

## Czego nie ma w cenie

- Hostingu chmurowego, SLA uptime, wsparcia 24/7.
- Klucza API Anthropic ani limitów po stronie sprzedawcy.
- Gwarancji zgodności z każdą polityką IT Twojej organizacji (testuj przed zakupem).

## Po zakupie (proces dostawy)

1. Opłata wg wybranego kanału (patrz tabela poniżej).
2. E-mail z linkiem do pobrania archiwum (wersja datowana, hash git w nazwie pliku).
3. Rozpakowanie: [`scripts/unpack-founders-archive.sh`](../scripts/unpack-founders-archive.sh).
4. Konfiguracja `src/.env` — `ANTHROPIC_API_KEY`, `ARCHITEKT_JWT_SECRET` (min. 32 znaki).
5. Smoke: `./scripts/smoke_week1.sh` → pierwsza debata wg [INSTALL.md](../INSTALL.md).

## Wsparcie

- Kontakt: **voidone@mypolyphony.com** (patrz [GTM_DECISIONS.md](GTM_DECISIONS.md) S0.4).
- Tryb **best effort** (np. odpowiedź w 48h roboczych), zakres: instalacja według `INSTALL.md`, błędy regresji w dostarczonej wersji — nie custom development.
- Szablony: [SUPPORT_PLAYBOOK.md](SUPPORT_PLAYBOOK.md).

## Prywatność (uproszczenie)

Dane debat zapisujesz **lokalnie** (SQLite domyślnie); przy rejestracji konta możesz eksportować i usuwać dane z UI (Ustawienia → Prywatność). Szczegóły: [COMPLIANCE_PRIVACY.md](COMPLIANCE_PRIVACY.md).

Telemetria produktu: domyślnie wyłączona (`APP_TELEMETRY` w buildzie UI).

## Oferta handlowa

| Pole | Wartość |
|------|---------|
| Cena | **149 EUR** (jednorazowo, founders; netto + VAT wg kraju) — patrz [PRICING.md](PRICING.md) |
| Platformy | Paczka źródłowa (wszystkie OS z Pythonem 3.12+); opcjonalnie Tauri: macOS arm64, Windows x64 |
| Kanał płatności | Faktura / przelew bankowy (zamówienie e-mailem na adres supportu) |
| Kontakt supportu | **voidone@mypolyphony.com** |

## Demo publiczne

Tryb `AW_DEMO_MODE=1` — limity debat, bez rejestracji trwałego konta, bez RODO/integracji w API. Patrz [DEMO.md](DEMO.md).
