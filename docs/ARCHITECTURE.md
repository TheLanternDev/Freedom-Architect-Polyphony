# Architektura

## personal_v1 (Rada Nadzorcza, osobista)
- 9 agentów + Syez
- Hybryda modeli: Haiku (Relacjan, Emojy, Smaty, Kidi), Sonnet (Kogit, Deega, Szow, Tai, Obver), Opus (Syez)
- Safety: czerwone flagi → halt + numer kryzysowy
- Test zgodności: 5 pytań po syntezie

## business_fa2 (Freedom Architect, biznesowa)
- 10 stałych ról: Strategos, Economist, Operator, Growth, Product&Tech, OrgDesigner, Risk, Scaling, CVA, Executor
- Tryby: full / strategic / scaling / fundraising / pivot
- FastAPI + Anthropic Messages API (`shared/utils/llm`)
- SQLite historia

## Wspólne (shared)
- LLM wrapper (Anthropic SDK + fallback)
- Cache SHA256
- Config + budżety

## Zasady rozdzielenia
- Konteksty nie łączą się — osobny runner, osobna pamięć, osobne testy.
- Patryk świadomie wybiera tryb: osobisty albo biznesowy.
