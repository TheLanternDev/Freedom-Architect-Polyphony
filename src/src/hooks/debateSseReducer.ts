/**
 * Czysta redukcja stanu debaty z eventów SSE — testowalna bez React.
 */
import type {
  AgentState,
  CompletionAuditViolationPayload,
  DebateDonePayload,
  DebateStartPayload,
  DebateState,
  DreamArchitecturePayload,
  LiveTensionsPayload,
  ProjectStatePayload,
  SynthesisChunkPayload,
  SynthesisDonePayload,
  SynthesisStructuredPayload,
  TensionAxisPayload,
  AgentChunkPayload,
  AgentDonePayload,
  BudgetWarningPayload,
} from "@/types/debate";

export function applySafetyHalt(
  state: DebateState,
  message: string,
): DebateState {
  return {
    ...state,
    status: "safety_halt",
    safetyMessage: message,
    pendingMsg: undefined,
    agents: {},
  };
}

/** Zwraca true, gdy po evencie należy zamknąć strumień SSE (np. safety_halt). */
export function shouldCancelSseStream(event: string): boolean {
  return event === "safety_halt";
}

export function reduceDebateEvent(
  state: DebateState,
  event: string,
  payload: unknown,
  options?: { streamErrorMessage?: string },
): DebateState {
  switch (event) {
    case "dream_architecture": {
      const p = payload as DreamArchitecturePayload;
      return { ...state, dream: p };
    }
    case "dream_architecture_error": {
      const p = payload as { error: string };
      return { ...state, dreamError: p.error };
    }
    case "project_state": {
      const p = payload as ProjectStatePayload;
      return { ...state, project: p };
    }
    case "completion_audit_violation": {
      const p = payload as CompletionAuditViolationPayload;
      return { ...state, auditViolation: p };
    }
    case "live_tensions": {
      const p = payload as LiveTensionsPayload;
      return {
        ...state,
        liveTensions: Array.isArray(p.pairs) ? p.pairs : [],
      };
    }
    case "debate_pending": {
      const p = payload as { msg?: string };
      if (!p.msg) return state;
      return { ...state, pendingMsg: p.msg };
    }
    case "safety_halt": {
      const p = payload as { message?: string };
      return applySafetyHalt(state, p.message ?? "");
    }
    case "debate_start": {
      const p = payload as DebateStartPayload;
      const agents: Record<string, AgentState> = {};
      for (const name of p.agents) {
        agents[name] = { name, status: "idle", text: "", progress: 0 };
      }
      return {
        ...state,
        status: "agents_speaking",
        agents,
        continuationParentId: p.continuation_parent_id ?? undefined,
        debateMode: p.mode,
        pendingMsg: undefined,
      };
    }
    case "agent_start": {
      const p = payload as { agent: string };
      return {
        ...state,
        agents: {
          ...state.agents,
          [p.agent]: {
            ...state.agents[p.agent],
            status: "analyzing",
            text: "",
            progress: 0,
          },
        },
      };
    }
    case "agent_chunk": {
      const p = payload as AgentChunkPayload;
      return {
        ...state,
        agents: {
          ...state.agents,
          [p.agent]: {
            ...state.agents[p.agent],
            status: "speaking",
            text: (state.agents[p.agent]?.text ?? "") + p.chunk,
            progress: Math.min(
              96,
              (state.agents[p.agent]?.progress ?? 0) + 5,
            ),
          },
        },
      };
    }
    case "agent_done": {
      const p = payload as AgentDonePayload;
      return {
        ...state,
        agents: {
          ...state.agents,
          [p.agent]: {
            ...state.agents[p.agent],
            status: "done",
            text: p.full_text,
            progress: 100,
          },
        },
      };
    }
    case "synthesis_start":
      return { ...state, status: "synthesizing" };
    case "synthesis_chunk": {
      const p = payload as SynthesisChunkPayload;
      return { ...state, synthesis: state.synthesis + p.chunk };
    }
    case "synthesis_done": {
      const p = payload as SynthesisDonePayload;
      return { ...state, synthesis: p.full_text };
    }
    case "synthesis_structured": {
      const p = payload as SynthesisStructuredPayload;
      return { ...state, synthesisStructured: p };
    }
    case "tension_axis": {
      const p = payload as TensionAxisPayload;
      if (!p || !Array.isArray(p.tensions) || p.tensions.length === 0) {
        return state; // brak danych → zostaje fallback do Mermaida
      }
      return { ...state, tensionAxis: p };
    }
    case "debate_done": {
      const p = payload as DebateDonePayload;
      return {
        ...state,
        status: "done",
        debateId: p.debate_id ?? undefined,
        debateCost: p.cost_usd ?? undefined,
      };
    }
    case "commitment_created":
      return {
        ...state,
        lastCommitmentEcho: payload as Record<string, unknown>,
      };
    case "budget_warning": {
      const p = payload as BudgetWarningPayload;
      return { ...state, budgetWarning: p.message };
    }
    case "stream_error": {
      const p = payload as { message?: string };
      return {
        ...state,
        status: "error",
        error: options?.streamErrorMessage ?? p?.message ?? "Stream error",
        pendingMsg: undefined,
      };
    }
    default:
      return state;
  }
}
