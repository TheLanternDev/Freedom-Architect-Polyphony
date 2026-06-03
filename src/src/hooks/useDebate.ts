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
  PriorTurn,
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
function debateBootstrap(
  status: DebateStatus,
  opts: { turns?: PriorTurn[]; currentPromptText?: string } = {},
): DebateState {
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
    turns: opts.turns,
    currentPromptText: opts.currentPromptText,
  };
}

/** Zbuduje snapshot bieżącej tury do archiwum. Wywoływane TYLKO przed startem kontynuacji,
 *  na podstawie state widzianego w setState-callbacku (zawsze świeży). */
function snapshotCurrentTurn(s: DebateState): PriorTurn | null {
  // Pomijamy stany puste (np. brak debateId i brak głosów — nic do zarchiwizowania).
  const hasContent =
    s.debateId != null ||
    Object.keys(s.agents).length > 0 ||
    (s.synthesis ?? "").length > 0;
  if (!hasContent) return null;
  return {
    debateId: s.debateId,
    promptText: s.currentPromptText ?? "",
    agents: s.agents,
    synthesis: s.synthesis,
    synthesisStructured: s.synthesisStructured,
    debateCost: s.debateCost,
    debateMode: s.debateMode,
  };
}

export function useDebate() {
  const { t } = useLang();
  const tRef = useRef(t);
  useEffect(() => {
    tRef.current = t;
  }, [t]);

  useEffect(() => {
    return () => {
      void readerRef.current?.cancel();
      readerRef.current = null;
    };
  }, []);

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

  // _runDebateStreamOnce: wewnętrzna warstwa SSE — jeden attempt połączenia.
  // Retry (max 1x) obsługiwany przez runDebateStream przez _retried flag.
  async function _runDebateStreamOnce(url: string, body: unknown, _retried: boolean) {
    // Deklaracja poza try/catch — dostępna w bloku catch dla guard retry.
    let receivedFirstEvent = false;
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

          receivedFirstEvent = true;
          handleEvent(eventLine, payload);
        }
      }
    } catch (err) {
      // Stage 4 resilience: jeden automatyczny retry przy przejściowym błędzie sieciowym.
      // NIE retry-ujemy gdy: (a) błąd HTTP — obsłużony wyżej przez `return`,
      // (b) backend już wysłał event (`receivedFirstEvent`) — retry = duplikat debaty w DB,
      // (c) celowe anulowanie przez użytkownika.
      const isNetworkError = err instanceof TypeError || err instanceof DOMException;
      // receivedFirstEvent jest w closurze — false jeśli błąd przed SSE, true po.
      // Gdy backend już wysłał choć jeden event: retry = duplikat debaty w DB — zabroniony.
      const safeToRetry = isNetworkError && !_retried && !receivedFirstEvent;
      if (safeToRetry) {
        setState((s) => ({
          ...s,
          pendingMsg: tRef.current("debate.reconnecting") || "Ponawiam połączenie…",
        }));
        await new Promise<void>((r) => setTimeout(r, 2_500));
        await _runDebateStreamOnce(url, body, true);
        return;
      }
      const msg = humanizeFetchFailure(err, (k) => tRef.current(k));
      setState((s) => ({
        ...s,
        status: "error",
        error: msg,
        pendingMsg: undefined,
      }));
    }
  }

  const runDebateStream = useCallback(
    async (
      url: string,
      body: unknown,
      opts: { turns?: PriorTurn[]; currentPromptText: string } = { currentPromptText: "" },
    ) => {
      readerRef.current?.cancel();
      setState(
        debateBootstrap("agents_speaking", {
          turns: opts.turns,
          currentPromptText: opts.currentPromptText,
        }),
      );
      await _runDebateStreamOnce(url, body, false);
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps
  []);

  const startDebate = useCallback(
    async (brief: Brief) => {
      // Nowy wątek — żadnych poprzednich tur do zachowania.
      await runDebateStream(
        `${getApiBase()}/debate/stream`,
        brief,
        { turns: undefined, currentPromptText: brief.description },
      );
    },
    [runDebateStream],
  );

  const continueDebateThread = useCallback(
    async (body: DebateContinueBody) => {
      // Przed bootstrapem strumienia: zarchiwizuj bieżącą turę (głosy + synteza + promptText)
      // do `turns`, żeby UI mogło w Ruchu 2 wyrenderować pełen wątek zamiast resetować widok.
      let nextTurns: PriorTurn[] | undefined;
      setState((s) => {
        const snap = snapshotCurrentTurn(s);
        const existing = s.turns ?? [];
        nextTurns = snap ? [...existing, snap] : existing;
        return s; // read-only: nie modyfikujemy stanu, tylko czytamy
      });
      await runDebateStream(
        `${getApiBase()}/debate/continue/stream`,
        body,
        { turns: nextTurns, currentPromptText: body.follow_up },
      );
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
      // /thread zwraca cały łańcuch wątku (root → liść) chronologicznie.
      const res = await fetch(`${getApiBase()}/debate/${debateId}/thread`, {
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
      type ThreadTurn = {
        debate: {
          id: number;
          brief_description?: string | null;
          synthesis_text?: string | null;
          mode?: string;
          cost_usd?: number | null;
        };
        voices: Array<{ agent_name: string; voice_text: string }>;
        synthesis_structured?: SynthesisStructuredPayload | null;
      };
      const data = (await res.json()) as { turns: ThreadTurn[] };
      const turns = data.turns ?? [];
      if (turns.length === 0) {
        setState(() => ({
          ...debateBootstrap("idle"),
          status: "error",
          error: `History: empty thread`,
        }));
        return;
      }

      function toAgents(
        voices: Array<{ agent_name: string; voice_text: string }>,
      ): Record<string, AgentState> {
        const agents: Record<string, AgentState> = {};
        for (const v of voices ?? []) {
          agents[v.agent_name] = {
            name: v.agent_name,
            status: "done",
            text: v.voice_text,
            progress: 100,
          };
        }
        return agents;
      }

      // Ostatnia tura ląduje na top-level state (bieżąca tura); poprzednie w state.turns.
      const last = turns[turns.length - 1];
      const priorTurns: PriorTurn[] = turns.slice(0, -1).map((tt) => ({
        debateId: tt.debate.id,
        promptText: tt.debate.brief_description ?? "",
        agents: toAgents(tt.voices),
        synthesis: tt.debate.synthesis_text ?? "",
        synthesisStructured: tt.synthesis_structured ?? undefined,
        debateCost: tt.debate.cost_usd ?? undefined,
        debateMode: tt.debate.mode,
      }));
      setState({
        ...debateBootstrap("done", {
          turns: priorTurns,
          currentPromptText: last.debate.brief_description ?? "",
        }),
        agents: toAgents(last.voices),
        synthesis: last.debate.synthesis_text ?? "",
        synthesisStructured: last.synthesis_structured ?? undefined,
        debateId: last.debate.id,
        debateMode: last.debate.mode,
        debateCost: last.debate.cost_usd ?? undefined,
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
