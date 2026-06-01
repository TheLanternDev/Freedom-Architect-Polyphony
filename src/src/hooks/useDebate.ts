import { useState, useCallback, useRef, useEffect } from "react";
import { useLang } from "@/lib/i18n";
import { humanizeFetchFailure } from "@/lib/fetchErrors";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";
import type {
  AgentState,
  Brief,
  DebateState,
  DebateStatus,
  DebateContinueBody,
  SynthesisStructuredPayload,
} from "@/types/debate";
import {
  reduceDebateEvent,
  shouldCancelSseStream,
} from "@/hooks/debateSseReducer";

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
    pendingMsg: undefined,
    safetyMessage: undefined,
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
    if (shouldCancelSseStream(event)) {
      void readerRef.current?.cancel();
      readerRef.current = null;
    }
    let streamErrorMessage: string | undefined;
    if (event === "stream_error") {
      const p = payload as { message?: string };
      streamErrorMessage = p?.message ?? tRef.current("debate.stream.broke");
    }
    setState((s) =>
      reduceDebateEvent(s, event, payload, { streamErrorMessage }),
    );
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

      // WebKit/Tauri 2 ma bug w pipeThrough(TextDecoderStream) na text/event-stream
      // — dekodujemy ręcznie z Uint8Array, dzięki czemu działa tak samo w przeglądarce i w .app.
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      readerRef.current = reader as unknown as ReadableStreamDefaultReader<string>;

      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
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
        const responseText = await res.text();
        throw new Error(responseText || `HTTP ${res.status}`);
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
