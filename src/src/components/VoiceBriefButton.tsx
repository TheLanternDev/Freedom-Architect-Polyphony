import { useCallback, useRef, useState } from "react";
import type { Lang } from "@/lib/i18n";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";

interface Props {
  disabled: boolean;
  lang: Lang;
  onTranscript: (text: string) => void;
  labelListening: string;
  labelIdle: string;
  unsupportedHint: string;
}

function hasWebSpeech(): boolean {
  return (
    typeof window !== "undefined" &&
    !!(window.SpeechRecognition || window.webkitSpeechRecognition)
  );
}

export function VoiceBriefButton({
  disabled,
  lang,
  onTranscript,
  labelListening,
  labelIdle,
  unsupportedHint,
}: Props) {
  const [listening, setListening] = useState(false);
  const listeningRef = useRef(false);
  const [interim, setInterim] = useState("");
  const recRef = useRef<SpeechRecognition | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const stop = useCallback(() => {
    try {
      recRef.current?.stop();
    } catch { /* noop */ }
    try {
      mediaRef.current?.stop();
    } catch { /* noop */ }
    recRef.current = null;
    mediaRef.current = null;
    chunksRef.current = [];
    listeningRef.current = false;
    setListening(false);
    setInterim("");
  }, []);

  const startWebSpeech = useCallback(() => {
    const R = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!R) return;
    const r = new R();
    r.lang = lang === "pl" ? "pl-PL" : "en-US";
    r.continuous = true;
    r.interimResults = true;
    r.onresult = (ev) => {
      let interimText = "";
      const startIdx = (ev as unknown as { resultIndex: number }).resultIndex ?? 0;
      for (let i = startIdx; i < ev.results.length; i++) {
        const transcript = ev.results[i][0]?.transcript?.trim();
        if (!transcript) continue;
        if (ev.results[i].isFinal) {
          onTranscript(transcript);
          setInterim("");
        } else {
          interimText += transcript + " ";
        }
      }
      if (interimText) setInterim(interimText.trim());
    };
    r.onerror = () => stop();
    r.onend = () => {
      if (listeningRef.current && recRef.current) {
        try { recRef.current.start(); } catch { stop(); }
      }
    };
    recRef.current = r;
    try {
      r.start();
      listeningRef.current = true;
      setListening(true);
    } catch {
      stop();
    }
  }, [lang, onTranscript, stop]);

  const startWhisperFallback = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        if (blob.size < 1000) return;
        const form = new FormData();
        form.append("audio", blob, "recording.webm");
        form.append("language", lang);
        try {
          const res = await fetch(`${getApiBase()}/voice/transcribe`, {
            method: "POST",
            headers: getApiAuthHeaders(),
            body: form,
          });
          if (res.ok) {
            const data = await res.json();
            if (data.text) onTranscript(data.text);
          }
        } catch { /* offline / no whisper */ }
      };
      mediaRef.current = recorder;
      recorder.start();
      setListening(true);
    } catch {
      setInterim(unsupportedHint);
      setTimeout(() => setInterim(""), 4000);
    }
  }, [lang, onTranscript, unsupportedHint]);

  const toggle = useCallback(() => {
    if (disabled) return;
    if (listening) {
      stop();
      return;
    }
    if (hasWebSpeech()) {
      startWebSpeech();
    } else {
      startWhisperFallback();
    }
  }, [disabled, listening, stop, startWebSpeech, startWhisperFallback]);

  return (
    <div className="no-print flex items-center gap-1.5">
      <button
        type="button"
        onClick={toggle}
        disabled={disabled}
        title={listening ? labelListening : labelIdle}
        className={`shrink-0 text-[11px] px-3 py-2 rounded-lg border transition-colors disabled:opacity-35 ${
          listening
            ? "border-red-500/50 bg-red-500/10 text-red-300 animate-pulse"
            : "border-white/15 bg-white/[0.05] hover:border-teal/45 hover:bg-teal/10"
        }`}
      >
        {listening ? labelListening : labelIdle}
      </button>
      {interim && (
        <span className="text-[10px] text-white/35 italic truncate max-w-[200px]">
          {interim}
        </span>
      )}
    </div>
  );
}
