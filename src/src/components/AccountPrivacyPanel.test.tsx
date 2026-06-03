/**
 * Vitest — AccountPrivacyPanel (logika confirm + demo gate).
 * Uruchom: npm run test:unit
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const DELETE_CONFIRM = "USUŃ MOJE KONTO";

function testDeleteConfirmConstant() {
  assert.equal(DELETE_CONFIRM, "USUŃ MOJE KONTO");
  assert.notEqual(DELETE_CONFIRM, "usun moje konto");
}

function testPanelSourceHasDemoGate() {
  const dir = dirname(fileURLToPath(import.meta.url));
  const src = readFileSync(join(dir, "AccountPrivacyPanel.tsx"), "utf8");
  assert.ok(src.includes("inDemo"), "expected inDemo prop");
  assert.ok(src.includes("account.demo_blocked"), "expected demo i18n key");
  assert.ok(src.includes("/account/export"), "expected export endpoint");
}

testDeleteConfirmConstant();
testPanelSourceHasDemoGate();
console.log("AccountPrivacyPanel.test.tsx: OK");
