# Final Cut Pro — Rada Polyphony (9 agentów + Syez)

## Import timeline
1. Otwórz **Final Cut Pro** → **Plik → Importuj → XML…**
2. Wybierz: `Rada-Polyphony.fcpxml`
3. FCP utworzy projekt **Rada Polyphony — Moj Swiat 24.5s** z klipami na osi czasu.

## Struktura osi (24.5s)
| Segment | Klip | Start | Długość |
|---------|------|-------|---------|
| Opening | `00-opening-seed.mp4` | 0s | 3.2s |
| Agenci 01–09 | `01-…` – `09-Kidi.mp4` | 3.2s | 1.53s × 9 |
| **Syez** | `10-Syez.mp4` | 17.00s | 4.5s |
| Closing CTA | `11-Closing.mp4` | 21.50s | 3.0s |

## Po imporcie (ręcznie w FCP)
- **Przejścia:** Cross Dissolve ~8–12 klatek między portretami i przed/po Syezie.
- **Opening (0–3.2s):** tekst serif złoty #E8D5A3 — „Za każdym ważnym wyborem…"
- **Syez (17.0–21.5s):** portret + napisy; Syez **nie** wchodzi do mandali 9 twarzy.
- **Ambient:** `00-ambient-bed.mp3` na lane -2 (cały film, ducking pod Syeza).
- **Syez (audio):** `aw-reels fcp-bundle --narrate-syez` i przeimportuj XML.
- **Closing (21.5–24.5s):** mandala 9 twarzy + CTA.
- **Brakujące PNG:** zamień placeholder w `Clips/` własnym klipem lub dodaj PNG do `Portraits/` i przebuduj bundle.

## Agenci (kolejność montażu)
| # | Agent | Rola | Opis | Długość | Media |
|---|-------|------|------|---------|-------|
| 1 | Relacjan | Relacje i zaufanie | Mapuje wpływ, dynamikę i ludzi wokół decyzji | 1.53s | ✓ |
| 2 | Kogit | Logika i struktura | Zimna architektoniczna jasność | 1.53s | ✓ |
| 3 | Emojy | Emocje prewerbalne | To, czego słowa jeszcze nie niosą | 1.53s | ✓ |
| 4 | Deega | Głęboka diagnoza | Nieświadome pętle i ukryte powtórzenia | 1.53s | ✓ |
| 5 | Smaty | Somatyczny | To, co ciało już wie | 1.53s | ✓ |
| 6 | Tai | Perspektywa czasu | Długie wzorce i konsekwencje przyszłości | 1.53s | ✓ |
| 7 | Szow | Cień | To, czego najmniej chcesz usłyszeć | 1.53s | ✓ |
| 8 | Obver | Obserwator zewnętrzny | Meta-perspektywa poza twoją historią | 1.53s | ✓ |
| 9 | Kidi | Dziecięca ciekawość | Czysta fascynacja i instynkt | 1.53s | ✓ |
| 10 | Syez | Syntetyzer i orkiestrator | Lustro dziewięciu głosów — bez własnej perspektywy | 4.50s | ✓ |

## Eksport IG
- 1080×1920, 30 fps, H.264, ~24.5 s
- **Plik → Udostępnij → Master File** lub Compressor

## xAI (opcjonalnie)
Grok służy tylko do materiałów B-roll / seed — **finalny montaż = FCP**.
