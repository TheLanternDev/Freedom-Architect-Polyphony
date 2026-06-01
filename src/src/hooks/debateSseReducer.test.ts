/**
 * Minimalny test reduktora SSE (safety_halt) — uruchom: npm run test:unit
 */
import assert from "assert";
import type { DebateState } from "@/types/debate";
import { applySafetyHalt, reduceDebateEvent } from "./debateSseReducer";

function testSafetyHaltClearsAgentsAndSetsStatus() {
  const prior: DebateState = {
    status: "agents_speaking",
    agents: {
      Szow: { name: "Szow", status: "speaking", text: "...", progress: 40 },
    },
    synthesis: "",
    pendingMsg: "Sprawdzam bezpieczeństwo...",
  };
  const next = reduceDebateEvent(prior, "safety_halt", {
    message: "Wykryto frazę kryzysową. Zadzwoń 116 123.",
  });
  assert.equal(next.status, "safety_halt");
  assert.equal(next.safetyMessage, "Wykryto frazę kryzysową. Zadzwoń 116 123.");
  assert.equal(next.pendingMsg, undefined);
  assert.deepEqual(next.agents, {});
}

function testApplySafetyHaltFromIdle() {
  const next = applySafetyHalt(
    { status: "idle", agents: {}, synthesis: "" },
    "halt",
  );
  assert.equal(next.status, "safety_halt");
  assert.equal(next.safetyMessage, "halt");
}

function testStreamErrorAfterDebatePendingClearsPendingMsg() {
  let state: DebateState = {
    status: "agents_speaking",
    agents: {},
    synthesis: "",
    pendingMsg: "Sprawdzam bezpieczeństwo i destyluję marzenie...",
  };
  state = reduceDebateEvent(state, "debate_pending", {
    status: "initializing",
    council_mode: "personal",
    msg: "Sprawdzam bezpieczeństwo i destyluję marzenie...",
  });
  assert.equal(state.pendingMsg, "Sprawdzam bezpieczeństwo i destyluję marzenie...");

  state = reduceDebateEvent(
    state,
    "stream_error",
    { message: "Połączenie SSE zerwane" },
    { streamErrorMessage: "Połączenie SSE zerwane" },
  );
  assert.equal(state.status, "error");
  assert.equal(state.error, "Połączenie SSE zerwane");
  assert.equal(state.pendingMsg, undefined);
}

testSafetyHaltClearsAgentsAndSetsStatus();
testApplySafetyHaltFromIdle();
testStreamErrorAfterDebatePendingClearsPendingMsg();
console.log("debateSseReducer.test.ts: OK");
