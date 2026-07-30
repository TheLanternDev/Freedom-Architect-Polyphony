#!/usr/bin/env node
/**
 * Opcjonalna walidacja ENV przed release build Tauri (podpisywanie).
 * Uruchamiane przez `npm run tauri:build:release`.
 * AW_TAURI_SKIP_SIGN_CHECK=1|true|yes — pomiń (dev build lokalny / most bez certów).
 */
import process from "node:process";

const _skip = (process.env.AW_TAURI_SKIP_SIGN_CHECK || "").trim().toLowerCase();
if (["1", "true", "yes"].includes(_skip)) {
  // Uwaga: `workflow_dispatch` w GitHub Actions przekazuje `choice` jako
  // string "true"/"false" — poprzednia wersja porównywała tylko do "1" i
  // NIGDY nie była spełniona przez ten input (latentny bug, naprawione tu).
  console.log(`tauri-release-env-check: pominięto (AW_TAURI_SKIP_SIGN_CHECK=${_skip})`);
  process.exit(0);
}

const platform = process.platform;
const missing = [];

if (platform === "darwin") {
  for (const key of [
    "APPLE_CERTIFICATE",
    "APPLE_CERTIFICATE_PASSWORD",
    "APPLE_SIGNING_IDENTITY",
  ]) {
    if (!(process.env[key] || "").trim()) missing.push(key);
  }
} else if (platform === "win32") {
  for (const key of ["WINDOWS_CERTIFICATE", "WINDOWS_CERTIFICATE_PASSWORD"]) {
    if (!(process.env[key] || "").trim()) missing.push(key);
  }
}

if (missing.length) {
  console.warn(
    "⚠️  Brak zmiennych podpisu dla release:",
    missing.join(", "),
  );
  console.warn("   Dev build: npm run tauri:build");
  console.warn("   Release:   ustaw sekrety (docs/TAURI_RELEASE.md) lub AW_TAURI_SKIP_SIGN_CHECK=1");
  process.exit(1);
}

console.log("tauri-release-env-check: OK");
