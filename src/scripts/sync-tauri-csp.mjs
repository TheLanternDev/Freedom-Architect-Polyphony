#!/usr/bin/env node
/**
 * P1-A4: wstrzykuje connect-src do tauri.conf.json z VITE_API_URL (build-time).
 * Domyślnie localhost:8000. Uruchamiane przed `tauri build`.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const confPath = path.resolve(__dirname, "../src-tauri/tauri.conf.json");

const apiUrl = (process.env.VITE_API_URL || "http://127.0.0.1:8000").trim();
let origin;
try {
  origin = new URL(apiUrl);
} catch {
  console.error(`sync-tauri-csp: niepoprawny VITE_API_URL: ${apiUrl}`);
  process.exit(1);
}

// Fonty bundlowane lokalnie (@fontsource) — zero CDN, pełny offline.
const hostOrigins = new Set([
  "'self'",
  "tauri:",
  "ipc:",
]);

const httpOrigin = `${origin.protocol}//${origin.host}`;
hostOrigins.add(httpOrigin);
if (origin.hostname === "localhost" || origin.hostname === "127.0.0.1") {
  hostOrigins.add("http://localhost:8000");
  hostOrigins.add("http://127.0.0.1:8000");
  hostOrigins.add("ws://localhost:8000");
  hostOrigins.add("ws://127.0.0.1:8000");
}
if (origin.protocol === "https:") {
  hostOrigins.add(`wss://${origin.host}`);
} else if (origin.protocol === "http:") {
  hostOrigins.add(`ws://${origin.host}`);
}

const connectSrc = [...hostOrigins].join(" ");

// PRODUKCJA: script-src BEZ 'unsafe-inline'. Webview eksponuje IPC
// `get_llm_key` (Keychain) — inline-XSS w treści debaty = odczyt klucza
// Anthropic. Build Vite nie emituje inline skryptów (wszystko z /assets).
// 'unsafe-inline' dla style pozostaje (Tailwind/framer inline styles).
// worker-src/img-src BEZ `blob:` (review 2026-07-30): grep po src/src nie
// znalazł ani jednego `new Worker(...)`, a jedyne `URL.createObjectURL` idą do
// `a.href` (pobieranie .md) — co CSP `img-src`/`worker-src` nie dotyczy.
// `blob:` w worker-src to klasyczna droga z XSS do wykonania kodu, a ten webview
// eksponuje IPC `get_llm_key` (Keychain). Zero uzasadnienia = zero wpisu.
const buildCsp = (scriptSrc, extraConnect = []) => [
  "default-src 'self'",
  `connect-src ${[connectSrc, ...extraConnect].join(" ")}`,
  `script-src ${scriptSrc}`,
  "style-src 'self' 'unsafe-inline'",
  "font-src 'self' data:",
  "img-src 'self' data: tauri:",
  "worker-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
].join("; ");

const csp = buildCsp("'self'");
// DEV (`tauri dev`): @vitejs/plugin-react wstrzykuje inline preamble
// (react-refresh) + HMR po ws://localhost:1420 — stąd luźniejszy devCsp.
// Nigdy nie trafia do zbudowanej paczki.
const devCsp = buildCsp("'self' 'unsafe-inline'", [
  "ws://localhost:1420",
  "ws://127.0.0.1:1420",
]);

const conf = JSON.parse(fs.readFileSync(confPath, "utf8"));
conf.app ??= {};
conf.app.security ??= {};
conf.app.security.csp = csp;
conf.app.security.devCsp = devCsp;
fs.writeFileSync(confPath, `${JSON.stringify(conf, null, 2)}\n`);
console.log(`sync-tauri-csp: connect-src ← ${httpOrigin}; script-src 'self' (prod), devCsp z HMR`);
