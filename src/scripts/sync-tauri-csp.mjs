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

const hostOrigins = new Set([
  "'self'",
  "tauri:",
  "ipc:",
  "https://fonts.googleapis.com",
  "https://fonts.gstatic.com",
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
const csp = [
  "default-src 'self'",
  `connect-src ${connectSrc}`,
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com",
  "img-src 'self' data: tauri:",
  "object-src 'none'",
  "base-uri 'self'",
].join("; ");

const conf = JSON.parse(fs.readFileSync(confPath, "utf8"));
conf.app ??= {};
conf.app.security ??= {};
conf.app.security.csp = csp;
fs.writeFileSync(confPath, `${JSON.stringify(conf, null, 2)}\n`);
console.log(`sync-tauri-csp: connect-src ← ${httpOrigin}`);
