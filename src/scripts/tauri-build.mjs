#!/usr/bin/env node
/**
 * tauri-build.mjs — `tauri build` z targetami dobranymi do PLATFORMY.
 *
 * PO CO (2026-07-30): `package.json` miał na sztywno `tauri build --bundles app`.
 * `app` to target WYŁĄCZNIE macOS (`.app`). Na Windows ten sam skrypt
 * (`npm run tauri:build:release`, wołany przez job `build-windows` w
 * `.github/workflows/tauri-release.yml`) nie wyprodukowałby ŻADNEGO instalatora,
 * a `upload-artifact` szukający plików `.msi` zassałby pustkę. Job świecił się
 * na zielono i nie dawał paczki.
 *
 * Targety per platforma:
 *   macOS   — `app`  (.dmg robi osobno scripts/make-dmg.sh, dlatego nie `all`)
 *   Windows — `msi,nsis`  (NSIS = .exe, przyjaźniejszy dla odbiorcy: instalacja
 *             per-user bez praw administratora; MSI dla firmowych deploymentów)
 *   Linux   — `deb,appimage`
 *
 * Nadpisanie: AW_TAURI_BUNDLES=msi (CSV, przekazywane wprost do --bundles).
 */
import { spawnSync } from "node:child_process";
import process from "node:process";

const BUNDLES = {
  darwin: "app",
  win32: "msi,nsis",
  linux: "deb,appimage",
};

const override = (process.env.AW_TAURI_BUNDLES || "").trim();
const bundles = override || BUNDLES[process.platform];

if (!bundles) {
  console.error(
    `tauri-build: nieobsługiwana platforma ${process.platform} — ustaw AW_TAURI_BUNDLES.`,
  );
  process.exit(1);
}

const args = ["tauri", "build", "--bundles", bundles, ...process.argv.slice(2)];
console.log(`tauri-build: platforma=${process.platform} bundles=${bundles}`);

const res = spawnSync("npx", args, { stdio: "inherit", shell: process.platform === "win32" });
process.exit(res.status ?? 1);
