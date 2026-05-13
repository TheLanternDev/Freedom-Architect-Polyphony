import { useState, useCallback, useRef, useEffect } from "react";
import { useLang } from "@/lib/i18n";
import { humanizeFetchFailure } from "@/lib/fetchErrors";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";
import type {
  Brief,
  DebateState,
  AgentState,
  DebateStartPayload,
  AgentChunkPayload,
  AgentDonePayload,
  SynthesisChunkPayload,
  SynthesisDonePayload,
  DreamArchitecturePayload,
  ProjectStatePayload,
  SynthesisStructuredPayload,
  CompletionAuditViolationPayload,
  DebateDonePayload,
  BudgetWarningPayload,
  DebateStatus,
  LiveTensionsPayload,
  DebateContinueBody,
} from "@/types/debate";

const INITIAL_STATE: DebateState = {
  status: "idle",
  agents: {},
  synthesis: "",
};

/** Stan początkowy nowego strumienia — usuwa pola z poprzedniej debaty (spread INITIAL_STATE tego nie robi). */
function debateBootstrap(status: DebateStatus): DebateState {
  return {
    status,
    agents: {},
    synthesis: "",
    debateId: undefined,
    debateCost: undefined,
    budgetWarning: undefined,
    dream: undefined,
    dreamError: undefined,
    project: undefined,
    synthesisStructured: undefined,
    auditViolation: undefined,
    liveTensions: undefined,
    continuationParentId: undefined,
    error: undefined,
    debateMode: undefined,
    lastCommitmentEcho: undefined,
  };
}

export function useDebate() {
  const { t } = useLang();
  const tRef = useRef(t);
  useEffect(() => {
    tRef.current = t;
  }, [t]);

  const [state, setState] = useState<DebateState>(INITIAL_STATE);
  const readerRef = useRef<ReadableStreamDefaultReader<string> | null>(null);

  const reset = useCallback(() => {
    readerRef.current?.cancel();
    setState(INITIAL_STATE);
  }, []);

  function handleEvent(event: string, payload: unknown) {
    switch (event) {
      // ── AKSJOMAT 1: Architektura Marzenia ─────────────────────────────
      case "dream_architecture": {
        const p = payload as DreamArchitecturePayload;
        setState((s) => ({ ...s, dream: p }));
        break;
      }

      case "dream_architecture_error": {
        const p = payload as { error: string };
        setState((s) => ({ ...s, dreamError: p.error }));
        break;
      }

      // ── AKSJOMAT 2: stan projektu ────────────────────────────────────
      case "project_state": {
        const p = payload as ProjectStatePayload;
        setState((s) => ({ ...s, project: p }));
        break;
      }

      case "completion_audit_violation": {
        const p = payload as CompletionAuditViolationPayload;
        setState((s) => ({ ...s, auditViolation: p }));
        break;
      }

      case "live_tensions": {
        const p = payload as LiveTensionsPayload;
        setState((s) => ({
          ...s,
          liveTensions: Array.isArray(p.pairs) ? p.pairs : [],
        }));
        break;
      }

      // ── Klasyczny pipeline Rady ──────────────────────────────────────
      case "debate_start": {
        const p = payload as DebateStartPayload;
        const agents: Record<string, AgentState> = {};
        for (const name of p.agents) {
          agents[name] = { name, status: "idle", text: "", progress: 0 };
        }
        setState((s) => ({
          ...s,
          status: "agents_speaking",
          agents,
          continuationParentId: p.continuation_parent_id ?? undefined,
          debateMode: p.mode,
        }));
        break;
      }

      case "agent_start": {
        const p = payload as { agent: string };
        setState((s) => ({
          ...s,
          agents: {
            ...s.agents,
            [p.agent]: { ...s.agents[p.agent], status: "analyzing", text: "", progress: 0 },
          },
        }));
        break;
      }

      case "agent_chunk": {
        const p = payload as AgentChunkPayload;
        setState((s) => ({
          ...s,
          agents: {
            ...s.agents,
            [p.agent]: {
              ...s.agents[p.agent],
              status: "speaking",
              text: (s.agents[p.agent]?.text ?? "") + p.chunk,
              progress: Math.min(
                96,
                (s.agents[p.agent]?.progress ?? 0) + 5,
              ),
            },
          },
        }));
        break;
      }

      case "agent_done": {
        const p = payload as AgentDonePayload;
        setState((s) => ({
          ...s,
          agents: {
            ...s.agents,
            [p.agent]: {
              ...s.agents[p.agent],
              status: "done",
              text: p.full_text,
              progress: 100,
            },
          },
        }));
        break;
      }

      case "synthesis_start": {
        setState((s) => ({ ...s, status: "synthesizing" }));
        break;
      }

      case "synthesis_chunk": {
        const p = payload as SynthesisChunkPayload;
        setState((s) => ({ ...s, synthesis: s.synthesis + p.chunk }));
        break;
      }

      case "synthesis_done": {
        const p = payload as SynthesisDonePayload;
        setState((s) => ({ ...s, synthesis: p.full_text }));
        break;
      }

      case "synthesis_structured": {
        const p = payload as SynthesisStructuredPayload;
        setState((s) => ({ ...s, synthesisStructured: p }));
        break;
      }

      case "debate_done": {
        const p = payload as DebateDonePayload;
        setState((s) => ({
          ...s,
          status: "done",
          debateId: p.debate_id ?? undefined,
          debateCost: p.cost_usd ?? undefined,
        }));
        break;
      }

      case "commitment_created": {
        setState((s) => ({
          ...s,
          lastCommitmentEcho: payload as Record<string, unknown>,
        }));
        break;
      }

      case "budget_warning": {
        const p = payload as BudgetWarningPayload;
        setState((s) => ({
          ...s,
          budgetWarning: p.message,
        }));
        break;
      }

      case "stream_error": {
        const p = payload as { message?: string; error?: string };
        const fb = p?.message
          ? `${p.message}${p.error ? " — " + p.error : ""}`
          : tRef.current("debate.stream.broke");
        setState((s) => ({
          ...s,
          status: "error",
          error: fb,
        }));
        break;
      }
    }
  }

  const runDebateStream = useCallback(async (url: string, body: unknown) => {
    readerRef.current?.cancel();
    setState(debateBootstrap("agents_speaking"));

    try {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getApiAuthHeaders(),
        },
        body: JSON.stringify(body),
      });

      if (!res.ok || !res.body) {
        let errorMsg = `HTTP ${res.status}`;
        try {
          const data = await res.json();
          if (res.status === 409) {
            setState((s) => ({
              ...s,
              status: "error",
              error: data?.detail?.message ?? "Active project limit reached",
              auditViolation: data?.detail,
            }));
            return;
          }
          if (res.status === 422 && Array.isArray(data?.detail)) {
            const msgs = (data.detail as Array<{ msg?: string; loc?: unknown[] }>)
              .map((e) => {
                const field = Array.isArray(e.loc) ? String(e.loc[e.loc.length - 1]) : "";
                return field ? `${field}: ${e.msg}` : (e.msg ?? "");
              })
              .filter(Boolean);
            errorMsg = msgs.join(" · ") || "Validation failed (422)";
          } else if (typeof data?.detail === "string") {
            errorMsg = data.detail;
          }
        } catch {
          /* body nie jest JSON — zostaje domyślny errorMsg */
        }
        setState((s) => ({ ...s, status: "error", error: errorMsg }));
        return;
      }

      const reader = res.body
        .pipeThrough(new TextDecoderStream())
        .getReader();
      readerRef.current = reader;

      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += value;
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";

        for (const block of blocks) {
          const eventLine = block.match(/^event: (.+)$/m)?.[1];
          const dataLine = block.match(/^data: (.+)$/ms)?.[1];
          if (!eventLine || !dataLine) continue;

          let payload: unknown;
          try {
            payload = JSON.parse(dataLine);
          } catch {
            continue;
          }

          handleEvent(eventLine, payload);
        }
      }
    } catch (err) {
      const msg = humanizeFetchFailure(err, (k) => tRef.current(k));
      setState((s) => ({
        ...s,
        status: "error",
        error: msg,
      }));
    }
  }, []);

  const startDebate = useCallback(
    async (brief: Brief) => {
      await runDebateStream(`${getApiBase()}/debate/stream`, brief);
    },
    [runDebateStream],
  );

  const continueDebateThread = useCallback(
    async (body: DebateContinueBody) => {
      await runDebateStream(`${getApiBase()}/debate/continue/stream`, body);
    },
    [runDebateStream],
  );

  const submitCommitment = useCallback(
    async (
      debateId: number | undefined,
      text: string,
      due?: string,
      followUp?: string,
      projectId?: number,
    ) => {
      if (!debateId) return;
      const res = await fetch(`${getApiBase()}/commitment`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getApiAuthHeaders(),
        },
        body: JSON.stringify({
          text,
          debate_id: debateId,
          project_id: projectId ?? null,
          due_at: due ?? null,
          follow_up_at: followUp ?? null,
        }),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || `HTTP ${res.status}`);
      }
    },
    [],
  );

  const loadHistoricalDebate = useCallback(async (debateId: number) => {
    readerRef.current?.cancel();
    setState(debateBootstrap("idle"));
    try {
      const res = await fetch(`${getApiBase()}/debate/${debateId}`, {
        headers: { ...getApiAuthHeaders() },
      });
      if (!res.ok) {
        setState(() => ({
          ...debateBootstrap("idle"),
          status: "error",
          error: `History: HTTP ${res.status}`,
        }));
        return;
      }
      const data = (await res.json()) as {
        voices: Array<{ agent_name: string; voice_text: string }>;
        debate: { synthesis_text?: string | null };
        synthesis_structured?: SynthesisStructuredPayload | null;
      };
      const agents: Record<string, AgentState> = {};
      for (const v of data.voices ?? []) {
        agents[v.agent_name] = {
          name: v.agent_name,
          status: "done",
          text: v.voice_text,
          progress: 100,
        };
      }
      setState({
        ...debateBootstrap("done"),
        agents,
        synthesis: data.debate?.synthesis_text ?? "",
        synthesisStructured: data.synthesis_structured ?? undefined,
        debateId,
        debateMode: (data.debate as { mode?: string })?.mode,
      });
    } catch (err) {
      const net = humanizeFetchFailure(err, (k) => tRef.current(k));
      setState(() => ({
        ...debateBootstrap("idle"),
        status: "error",
        error: `${tRef.current("history.title")}: ${net}`,
      }));
    }
  }, []);

  return {
    state,
    startDebate,
    continueDebateThread,
    reset,
    submitCommitment,
    loadHistoricalDebate,
  };
}
