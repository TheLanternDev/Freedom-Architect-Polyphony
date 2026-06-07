#!/usr/bin/env bash
set -euo pipefail
# ──────────────────────────────────────────────────────────────────────────────
# AW — Daily IG Reel  (render lokalny)
# Wygenerowane przez automation "aw-daily-ig-reel-0900" — 2026-06-06
#
#   Koncept:  reel3_brief_w_rade   (Reel #3A — „Brief wchodzi do Rady")
#   Odcinek:  #3  (kontynuacja reela #2 rada_polyphony_moj_swiat, match cut z mandali)
#   Czas:     15.000s, 9:16, kanon portretów 1:1 (assets/council/*.png)
#
# UWAGA: ten skrypt URUCHAMIASZ LOKALNIE NA MAC. Wymaga .venv/bin/aw-reels,
#        kluczy API (xAI/ElevenLabs) i połączenia. Sandbox automatyzacji ich nie ma.
#
#   Odpal:  bash tools/ig-reels/run_today.sh
# ──────────────────────────────────────────────────────────────────────────────

cd /Users/tpltd145/Projects/architekt-wolnosci/tools/ig-reels

CONCEPT="reel3_brief_w_rade"
REFS="assets/council/manifest.yaml"
PROMPT="prompts/reel3-brief-final-prompt.txt"
NARRATION="brand/reel3_brief_narration.yaml"

# ── 1. NOWA SESJA ─────────────────────────────────────────────────────────────
# CLI nie ma flagi --print-session-id. session.id == nazwa najnowszego katalogu
# output/reel-*. Tworzymy sesję, potem odczytujemy najnowszy katalog.
.venv/bin/aw-reels new "$CONCEPT"
SID="$(ls -dt output/reel-* | head -n1 | xargs basename)"
echo ">> Sesja: $SID"

# ── 2. WARIANTY (drafty 480p/8s) ──────────────────────────────────────────────
# UWAGA: 'variants' NIE przyjmuje --refs (to flaga 'finalize'/'generate').
# Drafty służą tylko do wyboru kadru/lensa; kanon portretów 1:1 wchodzi przy finalize.
.venv/bin/aw-reels variants "$SID" -n 2 --draft --yes

# ── 3. PICK DRAFTU ────────────────────────────────────────────────────────────
# Auto: bierzemy najnowszą iterację 'done' z session.json jako draft.
# Ręcznie zamiast tego:  .venv/bin/aw-reels variants "$SID" --draft -n 2  → wybierz lens,
#                        potem:  .venv/bin/aw-reels pick "$SID" <ITER>
DRAFT="$(python3 - "$SID" <<'PY'
import json, sys, pathlib
sid = sys.argv[1]
d = json.loads(pathlib.Path(f"output/{sid}/session.json").read_text())
done = [i["id"] for i in d.get("iterations", []) if i.get("status") in ("done", "picked")]
if not done:
    sys.exit("BRAK gotowej iteracji — sprawdź drafty ręcznie: aw-reels list / show")
print(done[-1])
PY
)"
echo ">> Draft: $DRAFT"

# ── 4. FINALIZE (pełne 720p/15s, prompt + refs 1:1) ───────────────────────────
.venv/bin/aw-reels finalize "$SID" "$DRAFT" --no-confirm --no-cache \
  -f "$PROMPT" --refs "$REFS"

# ── 5. (warunkowo) HYBRID-EXTEND do 15s ───────────────────────────────────────
# R2V z --refs bywa obcięte do 10s (limit API). Jeśli finalny iter < 15s,
# rozciągnij do 15s. Odczytujemy ostatni 'done/picked' iter jako FINAL.
FINAL="$(python3 - "$SID" <<'PY'
import json, sys, pathlib
sid = sys.argv[1]
d = json.loads(pathlib.Path(f"output/{sid}/session.json").read_text())
done = [i for i in d.get("iterations", []) if i.get("status") in ("done", "picked")]
if not done:
    sys.exit("BRAK finalnej iteracji.")
last = done[-1]
print(last["id"], (last.get("duration") or 0))
PY
)"
FINAL_ITER="$(echo "$FINAL" | awk '{print $1}')"
FINAL_DUR="$(echo "$FINAL" | awk '{print $2}')"
echo ">> Finalny iter: $FINAL_ITER (dur=${FINAL_DUR}s)"
# Próg: jeśli krócej niż ~14.5s — domknij do 15s.
if python3 -c "import sys; sys.exit(0 if float('${FINAL_DUR:-0}') < 14.5 else 1)"; then
  echo ">> R2V krótkie (${FINAL_DUR}s) — hybrid-extend do 15s"
  .venv/bin/aw-reels hybrid-extend "$SID" "$FINAL_ITER" --target 15
  # po extend bierzemy najnowszy gotowy iter
  FINAL_ITER="$(python3 - "$SID" <<'PY'
import json, sys, pathlib
sid = sys.argv[1]
d = json.loads(pathlib.Path(f"output/{sid}/session.json").read_text())
done = [i["id"] for i in d.get("iterations", []) if i.get("status") in ("done", "picked")]
print(done[-1])
PY
)"
  echo ">> Finalny iter po extend: $FINAL_ITER"
fi

# ── 6. NARRACJA RADY (szept agentów + lead/CTA Syeza, off-screen) ─────────────
.venv/bin/aw-reels narrate-council "$SID" --timeline "$NARRATION"

# ── 7. PUBLISH (mix ambient + narracja, napisy CTA) ───────────────────────────
.venv/bin/aw-reels publish "$SID" "$FINAL_ITER" --mix-ambient --skip-narrate \
  --caption-line1 "Twój brief. Ich debata. Twoja decyzja." \
  --caption-line2 "Founders Cohort • link w bio"

# ── 8. WERYFIKACJA ────────────────────────────────────────────────────────────
echo
echo "════════════════════════════════════════════════════════════════════════"
echo "  GOTOWE. Sesja: $SID  ·  finalny iter: $FINAL_ITER"
echo "  ▸ ffprobe -v error -show_entries format=duration -of csv=p=0 \\"
echo "      output/$SID/${FINAL_ITER}-ready.mp4    # oczekiwane: 15.000"
echo "  ▸ ODSŁUCHAJ KOŃCÓWKĘ (~11.3–13.0s): pełna linia Syeza + CTA"
echo "      'Twój brief. / Ich debata. / Twoja decyzja.' — nic nie ucięte na 15s."
echo "  ▸ SPRAWDŹ KANON: 4 twarze (Kogit, Emojy, Szow, Smaty) = 1:1 do PNG;"
echo "      Syez NIE jako 10. twarz w mandali; brak etykiet z imionami."
echo "  Po akceptacji: zaktualizuj reel_series_state.yaml (episode_number → 3,"
echo "    next_concept_id → reel3_szow_glos, last_session_id → $SID)."
echo "════════════════════════════════════════════════════════════════════════"
