# Soft Launch — protokół (Tydzień 4 mapy luk)

> Cel: przepuścić 3–5 zaproszonych userów przez system w ramach kontrolowanego
> testu, zebrać konkretny feedback i dotknąć **realnych** debat zamiast
> wyobrażania ich sobie. Każda dalsza decyzja produktowa po tym tygodniu
> opiera się na danych z soft launchu, nie na intuicji.

## Pre-flight (przed wysłaniem zaproszeń)

- [ ] CI zielone: `lint`, `pytest`, `secrets-scan`, `rls-smoke` — wszystkie 5 jobów na main.
- [ ] Coverage gate ≥ 75% (`.github/workflows/ci.yml`).
- [ ] Wszystkie 5 jobów CI zielonych dla ostatniego commita na main.
- [ ] `verify_cache_isolation.py` przechodzi na prod-Redisie (exit 0).
- [ ] Smoke RLS na prod-Postgresie: user-A INSERT → user-B SELECT zwraca 0 wierszy.
- [ ] `pg_dump` produkcyjnej bazy ZANIM przyjdą pierwsi userzy. Restore drill na osobnym instance: zadziałał.
- [ ] Klucze API w `.env` produkcyjnym są ROTAted po jakiejkolwiek zmianie repo (Anthropic / xAI console).
- [ ] Sentry DSN ustawiony i `capture_exception` przepuszcza testowy błąd → widać w dashboardzie.
- [ ] `/metrics` osiągalne wewnętrznie (Prometheus scrape OK).
- [ ] `USER_README.md` istnieje, czytelny, linkowany z głównego `README.md`.
- [ ] `MAX_ACTIVE_PROJECTS=1` na prod (świadomy limit, AKSJOMAT 2).

## Wybór 3–5 userów

Profil **idealny dla soft launchu** (NIE pełny ICP — to weryfikacja, nie sprzedaż):

- Zna Cię osobiście lub przez 1 stopień separacji (możesz zadzwonić jak coś się posypie).
- Ma realną decyzję / projekt na biurku w tym tygodniu (NIE „pobaw się jak chcesz").
- Toleruje surowość Szowa i Deegi (nie chce coachingu).
- Da Ci 60 minut na rozmowę po użyciu (bez tego feedback in-app to wycinek).

**Dyskwalifikacja:**

- Nikt, kto powie „przetestuję jeśli mam czas" — bez konkretnej decyzji nie ma sygnału.
- Nikt w aktywnym kryzysie psychicznym (system wykryje halt, ale nie testujesz tego na żywej osobie).
- Nikt z pełnymi wymaganiami corporate (procurement, SOC 2) — to nie ten etap.

## Wysłanie zaproszeń

Każdy zaproszony dostaje:

1. **JWT login** (lub konto przez `/auth/register`) z `tenant_id` = ich `sub`. RLS gwarantuje izolację.
2. **Link do `USER_README.md`** — czytany ZANIM dotkną UI.
3. **Krótki email/wiadomość** (3 zdania): co to jest, czego oczekujesz, kiedy chcesz feedback.
4. **Datę rozmowy follow-up** — wpisana w kalendarz przed zaproszeniem.

## Monitoring (przez 7 dni)

Codziennie, 5 minut:

```
# Prometheus / Grafana lub bezpośrednio z /metrics:
curl -s http://prod/metrics | grep -E "architekt_(debate|llm|completion|rate_limit)"

# Feedback w bazie:
psql "$DATABASE_URL" -c "SELECT created_at, rating, LEFT(what_broke, 80) FROM feedback ORDER BY created_at DESC LIMIT 20;"

# Errors (Sentry):
# Otwórz dashboard → szukaj nowych issues z dziś.

# Cost tracking:
curl -s http://prod/costs/status | jq .
```

Co śledzimy:

| Metryka | Próg ostrzegawczy | Próg krytyczny |
|---|---|---|
| Errors per debate | >5% | >15% (rollback) |
| Cache hit rate (po pierwszym dniu) | <30% | <10% |
| Completion audit violations | >20% syntez | >50% (kontrakt FA2/Syez złamany) |
| Średni rating feedback | <3.5 | <2.5 |
| Cost per debate | >$0.50 | >$1.00 (debug retry/loops) |
| RLS leak (cross-tenant feedback widoczny) | jakikolwiek | **natychmiastowy rollback** |

## Kryteria sukcesu Tygodnia 4

Soft launch uznajemy za zamknięty **i sensowny** gdy:

- [ ] 3–5 userów zrobiło ≥ 2 debaty każdy w ciągu 7 dni.
- [ ] Średni rating feedback ≥ 3.5 z minimum 5 wpisów.
- [ ] Zero incydentów typu RLS leak / cross-tenant.
- [ ] `eval_rada.py` na 10 briefach (3 personal + 7 fa2) — średni score Syez ≥ 0.7, średni score Rady ≥ 0.7.
- [ ] Lista wyciągniętych regresji z feedbacku, posortowana — pierwsze trzy są **dotkliwe** (wpływ na decyzję usera), nie kosmetyczne.
- [ ] Po follow-up rozmowach: minimum 2 userów mówi „użyję tego dalej" bez Twojego pytania.

## Kiedy rollback / pauza

- **Natychmiast:** RLS leak, klucze API w logach, klient widzi czyjąś syntezę.
- **24h zatrzymanie + post-mortem:** error rate >15%, koszt >$1/debata, krytyczny crash, krash debate streamu który zostawia debate w stanie pending.
- **Zatrzymaj rekrutację, dokończ obecnych:** rating <2.5, ≥3 userów mówi „nie wracam" w follow-up.

## Po soft launchu

Każdy „dalszy production-ready" jest pętlą na realnych debatach — nie na wyobrażeniu:

1. Ranking regresji z feedbacku → mapuj na konkretne pliki kodu.
2. Najwyższy bólowo punkt → osobny PR, test który by go złapał, fix, deploy.
3. Powtórz cykl. Skala (>5 userów) ma sens dopiero gdy 5 zaproszonych ma stabilny pozytywny sygnał przez 2 tygodnie z rzędu.

**NIE** rozszerzaj scope soft launchu (nowe features, nowe nisze, nowe agenty) zanim domkniesz pętlę feedbacku. To wzorzec porzucenia, który AKSJOMAT 2 ma blokować — w Tobie i w produkcie.
