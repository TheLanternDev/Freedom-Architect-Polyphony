#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║  AW Studio — orkiestrator produkcji reela Architekt Wolności      ║
# ║  Łączy: Keynote · Motion · aw-reels(render) · Final Cut · Compressor
# ╚══════════════════════════════════════════════════════════════════╝
# Łańcuch (kolejność produkcji):
#   1) PLANSZE   Keynote  — tytuły/plansze 9:16 (opcjonalnie)
#   2) ANIMACJE  Motion   — animowane tytuły/CTA (opcjonalnie)
#   3) RENDER    aw-reels — run_today.sh: seed + narracja + publish *-ready.mp4
#   4) MONTAŻ    Final Cut— import FCPXML, przejścia, napisy, ambient
#   5) EKSPORT   Compressor — H.264 1080×1920 30fps do IG
#
# Użycie:
#   ./aw-studio.sh           # menu interaktywne
#   ./aw-studio.sh --auto    # cały łańcuch, pauzy przed każdym ręcznym etapem GUI
#   ./aw-studio.sh 3 4 5     # tylko wybrane etapy w kolejności
set -euo pipefail

IG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # .../tools/ig-reels
L="$IG/scripts/launch"

c_gold='\033[38;5;179m'; c_dim='\033[2m'; c_ok='\033[32m'; c_err='\033[31m'; c_off='\033[0m'
say(){ printf "${c_gold}▸ %s${c_off}\n" "$*"; }
dim(){ printf "${c_dim}  %s${c_off}\n" "$*"; }
ok(){  printf "${c_ok}  ✓ %s${c_off}\n" "$*"; }
die(){ printf "${c_err}  ✗ %s${c_off}\n" "$*" >&2; exit 1; }
pause(){ read -r -p "  ↵ Enter gdy gotowe (q = przerwij): " a; [[ "$a" == "q" ]] && exit 0 || true; }

latest_ready(){ ls -t "$IG"/output/*/*-ready.mp4 2>/dev/null | head -1 || true; }
latest_fcpxml(){ ls -t "$IG"/output/fcp-*/Rada-Polyphony.fcpxml 2>/dev/null | head -1 || true; }

step_keynote(){
  say "1/5 PLANSZE — Keynote"
  dim "Zbuduj plansze 1080×1920 (tytuł, cytat Syeza, CTA). Eksport PNG/wideo do output/."
  bash "$L/open-keynote.sh" || die "Keynote nie wystartował"
  pause
}
step_motion(){
  say "2/5 ANIMACJE — Motion"
  dim "Animowane tytuły/CTA 9:16, 30fps. Zapisz render do output/ (użyje go FCP)."
  bash "$L/open-motion.sh" || die "Motion nie wystartował"
  pause
}
step_render(){
  say "3/5 RENDER — aw-reels (run_today.sh)"
  if [[ ! -f "$IG/run_today.sh" ]]; then
    die "Brak run_today.sh — wygeneruje go automation 09:00 (lub utwórz ręcznie)."
  fi
  ( cd "$IG" && bash run_today.sh ) || die "Render aw-reels nie powiódł się — sprawdź klucze API / log."
  local r; r="$(latest_ready)"
  [[ -n "$r" ]] && ok "Reel gotowy: $r" || dim "Uwaga: nie znalazłem *-ready.mp4 — zweryfikuj output."
}
step_finalcut(){
  say "4/5 MONTAŻ — Final Cut Pro"
  if [[ -z "$(latest_fcpxml)" ]]; then
    dim "Brak FCPXML — buduję bundle (aw-reels fcp-bundle)…"
    ( cd "$IG" && .venv/bin/aw-reels fcp-bundle ) || die "fcp-bundle nie powiódł się"
  fi
  if ! bash "$L/open-finalcut.sh"; then
    dim "Final Cut niedostępny — pomijam montaż. *-ready.mp4 z etapu 3 nadaje się prosto na IG."
    return 0
  fi
  dim "W FCP: przejścia, napisy złoty serif, ambient ducking, Syez poza mandalą."
  dim "Eksportuj Master File ALBO przejdź do etapu 5 (Compressor)."
  pause
}
step_compressor(){
  say "5/5 EKSPORT — Compressor"
  local r; r="$(latest_ready)"
  [[ -z "$r" ]] && dim "Brak *-ready.mp4 — wskaż źródło ręcznie w Compressorze."
  if ! bash "$L/open-compressor.sh"; then
    dim "Compressor niedostępny — *-ready.mp4 jest już H.264 9:16, gotowy na IG bez dodatkowego eksportu."
    return 0
  fi
  dim "Setting: H.264 · 1080×1920 · 30fps. Weryfikuj: ffprobe duration, końcówka Syeza nieucięta."
  ok "Łańcuch zakończony. *-ready.mp4 + caption → wrzuć ręcznie na IG (chronologia serii)."
}

run_step(){ case "$1" in 1)step_keynote;;2)step_motion;;3)step_render;;4)step_finalcut;;5)step_compressor;;*)die "Nieznany etap: $1";; esac; }

menu(){
  printf "\n${c_gold}AW Studio — produkcja reela${c_off}\n"
  dim "Repo: $IG"
  cat <<EOF

  1) Keynote   — plansze/tytuły 9:16
  2) Motion    — animowane tytuły/CTA
  3) Render    — aw-reels (run_today.sh) → *-ready.mp4
  4) Final Cut — montaż osi (FCPXML)
  5) Compressor— eksport IG H.264
  a) AUTO      — pełny łańcuch 1→5 z pauzami
  q) wyjście
EOF
  read -r -p "  wybór: " ch
  case "$ch" in
    [1-5]) run_step "$ch"; menu;;
    a|A) for s in 1 2 3 4 5; do run_step "$s"; done;;
    q|Q) exit 0;;
    *) menu;;
  esac
}

# --- entry ---
if [[ "${1:-}" == "--auto" ]]; then
  for s in 1 2 3 4 5; do run_step "$s"; done
elif [[ $# -gt 0 ]]; then
  for s in "$@"; do run_step "$s"; done
else
  menu
fi
