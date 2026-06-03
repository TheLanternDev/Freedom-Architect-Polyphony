# SALES-READY checklist — Founders BYOK

Odhacz przed ogłoszeniem **100% SALES-READY (BYOK)**. Decyzje produktowe: [GTM_DECISIONS.md](GTM_DECISIONS.md).

## S0 — Decyzje GTM

- [ ] S0.1 Cena i VAT uzupełnione w [FOUNDERS_OFFER.md](FOUNDERS_OFFER.md)
- [ ] S0.2 Platformy (zip vs Tauri) opisane
- [ ] S0.3 Kanał płatności i proces po zakupie
- [ ] S0.4 E-mail support w [SUPPORT_PLAYBOOK.md](SUPPORT_PLAYBOOK.md)
- [ ] S0.5 Polityka paczki `--sponsor` (tylko zaufani testerzy)
- [ ] S0.6 `VITE_PRIVACY_URL` ustawione w buildzie / `.env`

## S1 — Fundament techniczny

- [ ] Demo: `GET /account/export` jako `demo_*` → 403
- [ ] Demo: `GET /integrations/status` jako demo → 403
- [ ] `./scripts/smoke_week1.sh` → exit 0 (backend działa)

## S2 — Dokumentacja GTM i prawna

- [ ] [FOUNDERS_OFFER.md](FOUNDERS_OFFER.md) bez placeholderów „…"
- [ ] [COMPLIANCE_PRIVACY.md](COMPLIANCE_PRIVACY.md) — sekcja Model A BYOK
- [ ] [PRICING.md](PRICING.md) spójny z ofertą
- [ ] Support playbook z realnym adresem

## S3 — Dystrybucja

- [ ] `./scripts/pack-founders-archive.sh build/` — archiwum powstaje
- [ ] `./scripts/unpack-founders-archive.sh` w czystym katalogu → INSTALL → smoke_week1
- [ ] Katalog `build/` **nie** commitowany (`.gitignore`)
- [ ] Opcjonalnie: release Tauri wg [TAURI_RELEASE.md](TAURI_RELEASE.md)

## S4 — UI RODO

- [ ] Ustawienia → zakładka Prywatność → eksport JSON (z JWT)
- [ ] Usuń konto z potwierdzeniem `USUŃ MOJE KONTO`
- [ ] W demo: panel bez akcji eksportu/usuń
- [ ] `npm run test:unit` — green (w tym AccountPrivacyPanel)

## S5 — Onboarding kupującego

- [ ] [INSTALL.md](../INSTALL.md) — sekcja „Pierwsza debata (10 min)"
- [ ] [BETA_TESTER_WINDOWS.md](BETA_TESTER_WINDOWS.md) — link do prywatności

## S6 — Sign-off

- [ ] `pytest tests/ -q` — 0 failed
- [ ] Przebieg demo + pack + rejestracja + eksport (ręcznie)
- [ ] [AUDIT_PRODUCTION_READINESS.md](../AUDIT_PRODUCTION_READINESS.md) — SALES-READY BYOK 100%

**Data sign-off:** ___________  
**Wersja / git:** ___________
