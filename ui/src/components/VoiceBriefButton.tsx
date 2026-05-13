import { useCallback, useRef, useState } from "react";
import type { Lang } from "@/lib/i18n";

interface Props {
  disabled: boolean;
  lang: Lang;
  /** Dokleja transkrypt do istniejącego tekstu briefu (bezpłatnie — Web Speech API w przeglądarce). */
  onTranscript: (text: string) => void;
  labelListening: string;
  labelIdle: string;
  unsupportedHint: string;
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
  const recRef = useRef<SpeechRecognition | null>(null);

  const stop = useCallback(() => {
    try {
      recRef.current?.stop();
    } catch {
      /* noop */
    }
    recRef.current = null;
    setListening(false);
  }, []);

  const toggle = useCallback(() => {
    if (disabled) return;
    if (listening) {
      stop();
      return;
    }
    const R =
      typeof window !== "undefined"
        ? window.SpeechRecognition || window.webkitSpeechRecognition
        : undefined;
    if (!R) {
      window.alert(unsupportedHint);
      return;
    }
    const r = new R();
    r.lang = lang === "pl" ? "pl-PL" : "en-US";
    r.continuous = false;
    r.interimResults = false;
    r.onresult = (ev: SpeechRecognitionEvent) => {
      const said = ev.results[0]?.[0]?.transcript?.trim();
      if (said) onTranscript(said);
    };
    r.onerror = () => stop();
    r.onend = () => stop();
    recRef.current = r;
    try {
      r.start();
      setListening(true);
    } catch {
      stop();
    }
  }, [disabled, lang, listening, onTranscript, stop, unsupportedHint]);

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={disabled}
      title={listening ? labelListening : labelIdle}
      className="no-print shrink-0 text-[11px] px-3 py-2 rounded-lg border border-white/15 bg-white/[0.05] hover:border-teal/45 hover:bg-teal/10 disabled:opacity-35 transition-colors"
    >
      {listening ? labelListening : labelIdle}
    </button>
  );
}
