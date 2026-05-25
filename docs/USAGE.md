# Użycie

## Osobista (Rada)
```python
from personal_v1.core.runner import run_council
import asyncio
print(asyncio.run(run_council("Nie mogę domknąć projektu X — czemu?")))
```

## Biznesowa (FA2)
```bash
uvicorn business_fa2.api.main:app --reload
curl -X POST localhost:8000/debate -H 'Content-Type: application/json' \
  -d '{"brief":"CRM dla salonu 15k PLN/6 tyg","mode":"strategic"}'
```

## Pierwsze uruchomienie (osobiste)
```python
from personal_v1.rituals.onboarding import start_onboarding
print(start_onboarding())  # 20 pytań tożsamości
```
