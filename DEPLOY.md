# Wdrożenie — Freedom Architect: Polyphony (Cloudflare Pages)

## Struktura

- **Statyczna warstwa narracyjna** — katalog główny repo (`index.html`, podstrony, `assets/`, `styles/`, `js/`)
- **Worker API** — `worker/supervisory-board-page/` (formularz `/api/submit`, security headers)

## Przed pierwszym deployem

1. **Turnstile Site Key** — w `js/config.js` zamień placeholder na klucz z:
   Cloudflare Dashboard → Turnstile → Twoja witryna → Site Key

2. **CSP Workera (opcjonalnie)** — jeśli fonty Google nie ładują się, w `worker/supervisory-board-page/index.js` rozszerz CSP:
   ```
   font-src 'self' https://fonts.gstatic.com;
   style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
   ```
   (Obecny CSP blokuje zewnętrzne fonty — strona działa z fallbackiem systemowym.)

## Deploy statyki — Cloudflare Pages

### Opcja A — Cursor + Cloudflare plugin

1. Otwórz projekt `Freedom-Architect-Polyphony` w Cursorze
2. **Settings → Integrations → Cloudflare** (lub Cloudflare plugin w panelu)
3. Utwórz projekt Pages powiązany z tym repo
4. **Build settings:**
   - Framework preset: **None**
   - Build command: *(puste)*
   - Build output directory: **`/`** (katalog główny repo)
5. Połącz domenę `mypolyphony.com` z projektem Pages
6. Deploy przy pushu na `main`

### Opcja B — Wrangler CLI

```bash
cd /Users/voidone/Projects/Freedom-Architect-Polyphony
npx wrangler pages deploy . --project-name=mypolyphony-narrative
```

## Deploy Workera (API + security headers)

```bash
cd worker/supervisory-board-page
npx wrangler login          # jednorazowo
npx wrangler deploy
```

Worker ma route `mypolyphony.com/*` — obsługuje `/api/submit` i dodaje security headers do odpowiedzi Pages.

## Regeneracja podstron agentów

Po zmianie `js/agents.js` lub szablonu:

```bash
node scripts/generate-pages.js
```

## Lokalny podgląd

```bash
npx serve . -p 3000
# lub
python3 -m http.server 3000
```

Formularz wymaga produkcji (Turnstile + Worker) — lokalnie testuj tylko layout.

## Pliki kanoniczne

- Agenci: `js/agents.js` (źródło: `manifest.yaml`)
- Portrety: `assets/council/*.png`
- Czyste URL: `_redirects`
