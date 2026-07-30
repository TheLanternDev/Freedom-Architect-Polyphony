#!/usr/bin/env node
/**
 * check-sidecar-fresh.mjs — twardy guard przed `tauri build`.
 *
 * PROBLEM, KTÓRY TO ROZWIĄZUJE (review 2026-07-30):
 * `npm run tauri:build` nigdy nie odbudowywał zamrożonego backendu. Binarka
 * sidecara jest gitignorowana, więc git też nie dawał sygnału. Skutek: paczka
 * z 22.07 bundlowała backend z 22.07, kod Pythona zmieniono 23.07, a appka
 * odpalana z ikony przez 8 dni serwowała STARY backend — wyglądając na
 * działającą. Żaden test tego nie łapał, bo testy chodzą po źródłach, nie po
 * artefakcie.
 *
 * ZASADA: build ma padać głośno, zanim powstanie kłamliwy artefakt.
 * Guard sprawdza dwie rzeczy:
 *   1. czy binarka sidecara dla TEGO target-triple w ogóle istnieje,
 *   2. czy jest NOWSZA niż każdy plik `.py`, który do niej wchodzi.
 *
 * Świadomie NIE odpala PyInstallera sam: freeze trwa minuty, wymaga własnego
 * venva i różni się per OS. Cichy, wolny side-effect `npm run tauri:build` jest
 * gorszy niż jawny błąd z komendą do skopiowania. Ścieżka „zbuduj wszystko"
 * to `npm run dist:mac`, która woła freeze jawnie.
 *
 * Pomijanie (świadome, np. iteracja po samym froncie bez zmian w backendzie):
 *   AW_SKIP_SIDECAR_CHECK=1|true|yes
 */
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const SRC_DIR = path.resolve(import.meta.dirname, "..");
const REPO_ROOT = path.resolve(SRC_DIR, "..");
const BIN_DIR = path.join(SRC_DIR, "src-tauri", "binaries");
const BIN_NAME = "architekt-backend";

const skip = (process.env.AW_SKIP_SIDECAR_CHECK || "").trim().toLowerCase();
if (["1", "true", "yes"].includes(skip)) {
  console.warn(
    "check-sidecar-fresh: POMINIĘTO (AW_SKIP_SIDECAR_CHECK). " +
      "Paczka może zawierać backend starszy niż kod — nie wysyłaj takiej testerowi.",
  );
  process.exit(0);
}

/** Katalogi, których nie skanujemy — nie wchodzą do zamrożonej binarki. */
const SKIP_DIRS = new Set([
  ".git", ".venv", "venv", ".venv-sidecar", "node_modules", "build", "dist",
  "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "target",
  "tests", "tools", "assets", "landing", "polifonia", "widmo", "wieza-rady",
  "reels", "docs", "data",
]);

function hostTriple() {
  try {
    return execFileSync("rustc", ["--print", "host-tuple"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    /* starszy rustc — spróbuj -Vv */
  }
  try {
    const out = execFileSync("rustc", ["-Vv"], { encoding: "utf8" });
    const m = out.match(/^host:\s*(\S+)/m);
    if (m) return m[1];
  } catch {
    /* brak rustc */
  }
  return null;
}

/** Najnowszy mtime wśród plików `.py` wchodzących do binarki + rekomendacja co pokazać w błędzie. */
function newestPythonSource(dir, acc = { mtime: 0, file: null }) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return acc;
  }
  for (const e of entries) {
    if (e.name.startsWith(".") && e.name !== ".") continue;
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (SKIP_DIRS.has(e.name)) continue;
      newestPythonSource(full, acc);
    } else if (e.isFile() && e.name.endsWith(".py")) {
      // build_info.py jest NADPISYWANY przez build script przy freeze i
      // przywracany po nim — jego mtime jest zawsze świeższy od binarki
      // i fałszywie zgłaszałby staleness po każdym udanym buildzie.
      if (full.endsWith(path.join("config", "build_info.py"))) continue;
      const { mtimeMs } = fs.statSync(full);
      if (mtimeMs > acc.mtime) {
        acc.mtime = mtimeMs;
        acc.file = path.relative(REPO_ROOT, full);
      }
    }
  }
  return acc;
}

const triple = hostTriple();
if (!triple) {
  console.error(
    "✗ check-sidecar-fresh: brak `rustc` na PATH — nie ustalę target-triple.\n" +
      "  Rust jest i tak wymagany przez `tauri build`: https://rustup.rs",
  );
  process.exit(1);
}

const ext = triple.includes("windows") ? ".exe" : "";
const binPath = path.join(BIN_DIR, `${BIN_NAME}-${triple}${ext}`);
const buildCmd = triple.includes("windows")
  ? "scripts\\windows\\build-backend-sidecar.ps1"
  : "./scripts/build-backend-sidecar.sh";

if (!fs.existsSync(binPath)) {
  console.error(
    `✗ check-sidecar-fresh: brak binarki sidecara dla ${triple}\n` +
      `  Oczekiwana: ${path.relative(REPO_ROOT, binPath)}\n\n` +
      `  Bez niej paczka NIE MA czego uruchomić jako backend — a dev fallback\n` +
      `  (python -m uvicorn z repo) jest z ikony nieosiągalny, więc appka wstanie\n` +
      `  bez backendu i pokaże tylko błąd sieci.\n\n` +
      `  Zbuduj: cd ${REPO_ROOT} && ${buildCmd}`,
  );
  process.exit(1);
}

const binMtime = fs.statSync(binPath).mtimeMs;
const newest = newestPythonSource(REPO_ROOT);

if (newest.file && newest.mtime > binMtime) {
  const fmt = (ms) => new Date(ms).toISOString().replace("T", " ").slice(0, 19);
  const hours = ((newest.mtime - binMtime) / 3_600_000).toFixed(1);
  console.error(
    `✗ check-sidecar-fresh: zamrożony backend jest STARSZY niż kod Pythona.\n\n` +
      `  binarka sidecara : ${fmt(binMtime)}  (${path.basename(binPath)})\n` +
      `  najnowszy .py    : ${fmt(newest.mtime)}  (${newest.file})\n` +
      `  różnica          : ${hours} h\n\n` +
      `  Gdyby ten build przeszedł, paczka zawierałaby backend BEZ tych zmian,\n` +
      `  a /health wyglądałby normalnie. Dokładnie ten rozjazd przez 8 dni\n` +
      `  udawał „wszystko działa" (review 2026-07-30).\n\n` +
      `  Przebuduj: cd ${REPO_ROOT} && ${buildCmd}\n` +
      `  Świadomie pomiń (tylko iteracja po froncie): AW_SKIP_SIDECAR_CHECK=1`,
  );
  process.exit(1);
}

const stampPath = path.join(BIN_DIR, "BUILD_STAMP");
const stamp = fs.existsSync(stampPath)
  ? fs.readFileSync(stampPath, "utf8").trim().split("\n")[0]
  : "(brak BUILD_STAMP — binarka z buildu przed wprowadzeniem stempla)";
console.log(`check-sidecar-fresh: OK — sidecar świeższy niż źródła. build_id=${stamp}`);
