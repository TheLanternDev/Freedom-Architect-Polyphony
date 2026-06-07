#!/usr/bin/env bash
set -euo pipefail
# ──────────────────────────────────────────────────────────────────────────────
# AW — IG Reel #3B  (render lokalny)
#
#   Koncept:  reel3_szow_glos   (Reel #3B — „Głos, którego nie chcesz")
#   Odcinek:  #3B  (kontynuacja #2/#3A, match cut z mandali — tylko węzeł Szowa)
#   Czas:     15.000s, 9:16, kanon Szowa 1:1 (assets/council/Szow.png)
#
# UWAGA: ten skrypt URUCHAMIASZ LOKALNIE NA MAC. Wymaga .venv/bin/aw-reels,
#        kluczy API (xAI/ElevenLabs) i połączenia. Sandbox automatyzacji ich nie ma.
#
#   Odpal:  bash tools/ig-reels/run_today_3b.sh
# ──────────────────────────────────────────────────────────────────────────────

cd /Users/tpltd145/Projects/architekt-wolnosci/tools/ig-reels

CONCEPT="reel3_szow_glos"
REFS="assets/council/manifest_szow.yaml"   # tylko Szow (1 ref) — #3B = jedna twarz, bez przecieku R2V
PROMPT="prompts/reel3-szow-final-prompt.txt"
NARRATION="brand/reel3_szow_narration.yaml"

# ── 1. NOWA SESJA ─────────────────────────────────────────────────────────────
.venv/bin/aw-reels new "$CONCEPT"
SID="$(ls -dt output/reel-* | head -n1 | xargs basename)"
echo ">> Sesja: $SID"

# ── 2. WARIANTY (drafty 480p/8s) ──────────────────────────────────────────────
.venv/bin/aw-reels variants "$SID" -n 2 --draft --yes

# ── 3. PICK DRAFTU ────────────────────────────────────────────────────────────
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

# ── 4. FINALIZE (pełne 720p/15s, prompt + ref Szowa 1:1) ──────────────────────
.venv/bin/aw-reels finalize "$SID" "$DRAFT" --no-confirm --no-cache \
  -f "$PROMPT" --refs "$REFS"

# ── 5. (warunkowo) HYBRID-EXTEND do 15s ───────────────────────────────────────
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
if python3 -c "import sys; sys.exit(0 if float('${FINAL_DUR:-0}') < 14.5 else 1)"; then
  echo ">> R2V krótkie (${FINAL_DUR}s) — hybrid-extend do 15s"
  .venv/bin/aw-reels hybrid-extend "$SID" "$FINAL_ITER" --target 15
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

# ── 6. NARRACJA (jeden głos: Szow, off-screen, bez lip-sync) ──────────────────
.venv/bin/aw-reels narrate-council "$SID" --timeline "$NARRATION"

# ── 7. PUBLISH (mix ambient + narracja, napisy CTA) ───────────────────────────
.venv/bin/aw-reels publish "$SID" "$FINAL_ITER" --mix-ambient --skip-narrate \
  --caption-line1 "Szow nie jest twoim wrogiem. Jest twoją uczciwością." \
  --caption-line2 "Founders Cohort • link w bio"

# ── 8. WERYFIKACJA ────────────────────────────────────────────────────────────
echo
echo "════════════════════════════════════════════════════════════════════════"
echo "  GOTOWE. Sesja: $SID  ·  finalny iter: $FINAL_ITER"
echo "  ▸ ffprobe -v error -show_entries format=duration -of csv=p=0 \\"
echo "      output/$SID/${FINAL_ITER}-ready.mp4    # oczekiwane: 15.000"
echo "  ▸ ODSŁUCHAJ KOŃCÓWKĘ (~13.1–15.0s): pełna linia CTA Szowa"
echo "      'Nie jestem twoim wrogiem. / Jestem twoją uczciwością.' — nic nie ucięte."
echo "  ▸ SPRAWDŹ KANON: 1 twarz = Szow 1:1 do PNG (split-face, amber eyes);"
echo "      brak innych agentów; Syez NIE występuje; brak etykiet z imionami;"
echo "      brak estetyki horror/jump-scare — godny cień."
echo "  Po akceptacji + publikacji: zaktualizuj reel_series_state.yaml"
echo "    (episode_number → 4 lub oznacz #3B published, next_concept_id →"
echo "     reel3_zobowiazanie_72h, dopisz reel3_szow_glos do published_order)."
echo "════════════════════════════════════════════════════════════════════════"
