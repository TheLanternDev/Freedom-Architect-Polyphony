# NEXUS — osobny slot Cloudflare Pages

Interaktywna strona 3D (landing Architekta Wolności). **Deploy idzie do osobnego projektu Pages**, żeby nie nadpisywać głównej witryny `mypolyphony.com` (worker `supervisory-board-page`).

## Sloty (nie mylić)

| Slot | Projekt CF | URL | Zawartość |
|------|------------|-----|-----------|
| Główna strona | `supervisory-board-page` (Worker + Pages) | `mypolyphony.com` | Narracja, formularz, podstrony agentów |
| **NEXUS** | **`Nexus-portfolio`** (Pages) | `nexus-portfolio.pages.dev` lub `nexus.mypolyphony.com` | 3D landing, fragment, testuj |

## Deploy (lokalnie / Cursor)

```bash
# jednorazowo: npx wrangler login
export CLOUDFLARE_API_TOKEN=...   # albo login OAuth
./scripts/deploy-nexus.sh
```

Zmienna `CF_PAGES_PROJECT` nadpisuje nazwę projektu (domyślnie `Nexus-portfolio`).

## Ważne dla Cursora / agentów

- **Zawsze** używaj `--project-name=Nexus-portfolio` (lub ten skrypt).
- **Nigdy** nie deployuj `sites/nexus/` do projektu obsługującego `mypolyphony.com`.
- Linki do `/demo` prowadzą na `https://mypolyphony.com/demo` (demo nie jest w tym bundle).

## Custom domain

W Cloudflare Dashboard → Workers & Pages → **Nexus-portfolio** → Custom domains → dodaj `nexus.mypolyphony.com`.
