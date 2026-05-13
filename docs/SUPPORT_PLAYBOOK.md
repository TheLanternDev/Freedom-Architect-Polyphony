# Szablon supportu (model A — founders / lokalnie)

Zastąp `SUPPORT_EMAIL` adresem z oferty (`docs/FOUNDERS_OFFER.md`).

## Pierwsza odpowiedź (ogólna)

Dziękuję za zgłoszenie. Proszę po kolei:

1. Backend: `uvicorn main:app --host 127.0.0.1 --port 8000` z aktywowanego `venv` (por. `INSTALL.md`).
2. W UI: przycisk **Połączenie** → **Test /health** — czy jest zielony komunikat?
3. Klucz: `ANTHROPIC_API_KEY` w pliku **`ui/.env`**, potem restart backendu.
4. Jeśli zmieniali Państwo port — w tym samym oknie ustaw adres API i **Zastosuj**.

## „Load failed” / brak debaty

- Czy adres API w aplikacji wskazuje ten sam host/port co uvicorn?
- Firewall / VPN — wyłączenie testowe.
- Logi serwera (terminal z uvicorn) w momencie wysłania briefu.

## Błąd 401 / model

- Ważność klucza Anthropic i limitów na koncie Anthropic — poza zakresem licencji oprogramowania.

## Prośba o funkcję X

- Zbieramy feedback do backlogu; w founders nie ma obowiązku custom development — odpowiedź uprzejma, krótka.
