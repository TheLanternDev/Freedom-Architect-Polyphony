#!/usr/bin/env bash
# Deploy NEXUS (3D landing) do OSOBNEGO projektu Cloudflare Pages.
# NIE nadpisuje mypolyphony.com — tam zostaje worker supervisory-board-page.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE="$ROOT/sites/nexus"
PROJECT="${CF_PAGES_PROJECT:-mypolyphony-nexus}"
BRANCH="${CF_PAGES_BRANCH:-main}"

if ! command -v npx >/dev/null 2>&1; then
  echo "ERROR: npx nie znaleziony" >&2
  exit 1
fi

if [ -z "${CLOUDFLARE_API_TOKEN:-}" ] && [ -z "${CF_API_TOKEN:-}" ]; then
  echo "WARN: brak CLOUDFLARE_API_TOKEN — uruchom 'npx wrangler login' lub ustaw token w ENV." >&2
fi

cd "$SITE"
echo "→ Deploy NEXUS → project=${PROJECT} branch=${BRANCH}"
npx --yes wrangler@4 pages deploy . \
  --project-name="$PROJECT" \
  --branch="$BRANCH" \
  --commit-dirty=true

echo ""
echo "✅ NEXUS wdrożony do osobnego slotu: ${PROJECT}"
echo "   URL (domyślny): https://${PROJECT}.pages.dev"
echo "   Następny krok — własna domena:"
echo "   Cloudflare Dashboard → Workers & Pages → ${PROJECT} → Custom domains → nexus.mypolyphony.com"
echo "   mypolyphony.com NIE jest dotykany tym deployem."
