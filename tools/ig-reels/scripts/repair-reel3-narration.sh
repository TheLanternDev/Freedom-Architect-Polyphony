#!/usr/bin/env bash
# Offline naprawa narracji reel #3A — bez ElevenLabs API.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/output/reel-20260606-132002-a3f3"
# Preferuj kopię sprzed nadpisania; fallback na bieżący plik.
SRC="$OUT/narration-council-source.mp3"
if [[ ! -f "$SRC" ]]; then
  SRC="$OUT/narration-council.mp3"
fi
DEST="$OUT/narration-council-repaired.mp3"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

lnorm() {
  local in="$1" out="$2" lufs="$3"
  ffmpeg -y -hide_banner -loglevel error -i "$in" -af "loudnorm=I=${lufs}:TP=-1.0:LRA=8" "$out"
}

extract() {
  local in="$1" out="$2" start="$3" dur="$4"
  ffmpeg -y -hide_banner -loglevel error -ss "$start" -i "$in" -t "$dur" -c:a libmp3lame -q:a 2 "$out"
}

cta_line() {
  local text="$1" out="$2"
  say -v Zosia -r 17500 "$text" -o "${out%.mp3}.aiff"
  ffmpeg -y -hide_banner -loglevel error -i "${out%.mp3}.aiff" \
    -af "asetrate=44100*0.90,aresample=44100,atempo=0.82" "$out"
}

# Zachowaj oryginał przy pierwszym uruchomieniu
if [[ ! -f "$OUT/narration-council-source.mp3" && -f "$OUT/narration-council.mp3" ]]; then
  cp "$OUT/narration-council.mp3" "$OUT/narration-council-source.mp3"
  SRC="$OUT/narration-council-source.mp3"
fi

extract "$SRC" "$WORK/w1.mp3" 4.20 0.75
extract "$SRC" "$WORK/w2.mp3" 5.55 0.90
extract "$SRC" "$WORK/w3.mp3" 6.70 0.95
extract "$SRC" "$WORK/w4.mp3" 8.00 0.95
SEG="$OUT/narration-segments"
if [[ -f "$SEG/s1.mp3" && -f "$SEG/s2.mp3" ]]; then
  cp "$SEG/s1.mp3" "$WORK/s1.mp3"
  cp "$SEG/s2.mp3" "$WORK/s2.mp3"
else
  extract "$SRC" "$WORK/s1.mp3" 10.30 1.12
  extract "$SRC" "$WORK/s2.mp3" 12.46 1.46
fi

lnorm "$WORK/w1.mp3" "$WORK/w1n.mp3" -20
lnorm "$WORK/w2.mp3" "$WORK/w2n.mp3" -20
lnorm "$WORK/w3.mp3" "$WORK/w3n.mp3" -20
lnorm "$WORK/w4.mp3" "$WORK/w4n.mp3" -20
lnorm "$WORK/s1.mp3" "$WORK/s1n.mp3" -15.5
lnorm "$WORK/s2.mp3" "$WORK/s2n.mp3" -15.5
ffmpeg -y -hide_banner -loglevel error -i "$WORK/s1n.mp3" -i "$WORK/s2n.mp3" \
  -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1[syez]" -map "[syez]" "$WORK/syez.mp3"
lnorm "$WORK/syez.mp3" "$WORK/syezn.mp3" -15.5

# CTA — trzy frazy, mocne pauzy (offline TTS)
cta_line "Twój brief." "$WORK/cta1.mp3"
cta_line "Ich debata." "$WORK/cta2.mp3"
cta_line "Twoja decyzja." "$WORK/cta3.mp3"
lnorm "$WORK/cta1.mp3" "$WORK/c1n.mp3" -12.5
lnorm "$WORK/cta2.mp3" "$WORK/c2n.mp3" -12.5
lnorm "$WORK/cta3.mp3" "$WORK/c3n.mp3" -12.0

ffmpeg -y -hide_banner -loglevel error \
  -i "$WORK/w1n.mp3" -i "$WORK/w2n.mp3" -i "$WORK/w3n.mp3" -i "$WORK/w4n.mp3" \
  -i "$WORK/syezn.mp3" \
  -i "$WORK/c1n.mp3" -i "$WORK/c2n.mp3" -i "$WORK/c3n.mp3" \
  -filter_complex "\
[0:a]adelay=4200|4200[a0];\
[1:a]adelay=5400|5400[a1];\
[2:a]adelay=6600|6600[a2];\
[3:a]adelay=7800|7800[a3];\
[4:a]adelay=9200|9200[a4];\
[5:a]adelay=12200|12200[a5];\
[6:a]adelay=13200|13200[a6];\
[7:a]adelay=13900|13900[a7];\
[a0][a1][a2][a3][a4][a5][a6][a7]amix=inputs=8:duration=longest:dropout_transition=0:normalize=0,\
apad=whole_dur=15.000,loudnorm=I=-14:TP=-0.8:LRA=9[out]" \
  -map "[out]" "$DEST"

cp "$DEST" "$OUT/narration-council.mp3"
echo "Repaired narration → $DEST"
