# VERGE

Interactive scrollytelling experience — 10 unique Three.js worlds driven by scroll as a timeline.

## Stack

- Next.js App Router + TypeScript
- React Three Fiber / Drei / Postprocessing / Rapier
- Lenis smooth scroll + Zustand

## Run

```bash
cd scrollytelling
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Scroll to travel.

## Architecture

See `DESIGN.md` for Design Singularity Phase 0–3. Each floor is an isolated module under `src/worlds/`.
