/**
 * Weryfikacja CTA „Nowa debata” / kontynuacja — scenariusze 1–4.
 * Uruchom: npm run test:unit
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { DICT } from "@/lib/i18n";

const root = dirname(fileURLToPath(import.meta.url));

function read(name: string): string {
  return readFileSync(join(root, name), "utf8");
}

function testI18nKeys() {
  assert.ok(DICT["syez.continue.unavailable"]?.pl.includes("nie została zapisana"));
  assert.ok(DICT["syez.continue.unavailable"]?.en.includes("not saved"));
  assert.equal(DICT["syez.new_debate.btn"]?.pl, "Nowa debata");
  assert.equal(DICT["syez.new_debate.btn"]?.en, "New debate");
}

/** Scenariusz 1: done + debateId → formularz kontynuacji + ghost „Nowa debata”. */
function testScenario1_doneWithDebateId() {
  const syez = read("SyezPanel.tsx");
  assert.ok(
    syez.includes("onSubmit={(e) => void handleContinueSubmit(e)}"),
    "continue form submit handler present",
  );
  assert.ok(
    syez.includes('placeholder={t("syez.continue.placeholder")}'),
    "continue textarea placeholder present",
  );
  assert.ok(
    syez.includes("isDone && onContinueThread && debateId != null && onNewDebate"),
    "ghost new-debate guard",
  );
  assert.ok(
    syez.includes('className="aw-btn-ghost w-full text-[12px] px-3 py-2"'),
    "ghost button style",
  );
}

/** Scenariusz 2: done + debateId==null → notka niedostępności + CTA. */
function testScenario2_doneWithoutDebateId() {
  const syez = read("SyezPanel.tsx");
  assert.ok(
    syez.includes("!!(onCommitStep || onContinueThread || onNewDebate)"),
    "closing column gate includes onNewDebate",
  );
  assert.ok(
    syez.includes("isDone && debateId == null && onNewDebate"),
    "unavailable block guard",
  );
  assert.ok(syez.includes('t("syez.continue.unavailable")'), "unavailable i18n");
  assert.ok(
    syez.includes("bg-teal/20 border border-teal/45"),
    "primary CTA uses teal continue styles",
  );
}

/** Scenariusz 3: error → „Nowa debata” w głównej kolumnie App. */
function testScenario3_errorStateCta() {
  const app = read("../App.tsx");
  const errorMatch = app.match(
    /\{state\.status === "error" && \([\s\S]*?\)\s*\}\s*\n\s*\{\/\* Wątek/,
  );
  assert.ok(errorMatch, "error block extractable");
  const errorBlock = errorMatch![0];
  assert.ok(errorBlock.includes("onClick={reset}"), "error CTA calls reset");
  assert.ok(errorBlock.includes('t("syez.new_debate.btn")'), "error CTA label");
  assert.ok(errorBlock.includes("no-print"), "error CTA block is no-print");
  assert.ok(app.includes("onNewDebate={reset}"), "SyezPanel wired to reset");
}

/** Scenariusz 4: debata w toku → reset disabled, brak nowych CTA poza isDone. */
function testScenario4_activeDebateNoExtraCta() {
  const header = read("WorkspaceHeader.tsx");
  const syez = read("SyezPanel.tsx");
  const app = read("../App.tsx");

  assert.ok(header.includes("disabled={isActive}"), "header reset disabled when active");
  assert.ok(header.includes('hidden sm:inline'), "reset label visible sm+");
  assert.ok(header.includes('t("app.btn.reset")'), "reset label i18n");

  assert.ok(
    app.includes(
      'state.status === "agents_speaking" || state.status === "synthesizing"',
    ),
    "isActive covers in-progress states",
  );

  const newDebateGuards = [
    "isDone && onContinueThread && debateId != null && onNewDebate",
    "isDone && debateId == null && onNewDebate",
  ];
  for (const guard of newDebateGuards) {
    assert.ok(syez.includes(guard), `new-debate CTA gated by isDone: ${guard}`);
  }
}

testI18nKeys();
testScenario1_doneWithDebateId();
testScenario2_doneWithoutDebateId();
testScenario3_errorStateCta();
testScenario4_activeDebateNoExtraCta();
console.log("debateNewCta.test.ts: OK");
