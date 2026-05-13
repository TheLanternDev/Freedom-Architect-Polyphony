import { useEffect, useId, useRef } from "react";
import mermaid from "mermaid";

let configured = false;

function ensureMermaidTheme() {
  if (configured) return;
  mermaid.initialize({
    startOnLoad: false,
    theme: "dark",
    securityLevel: "strict",
    fontFamily: "ui-sans-serif, system-ui, sans-serif",
  });
  configured = true;
}

interface Props {
  chart: string;
}

export function MermaidBlock({ chart }: Props) {
  const reactId = useId().replace(/:/g, "");
  const holder = useRef<HTMLDivElement>(null);

  useEffect(() => {
    ensureMermaidTheme();
    const id = `mmd-${reactId}-${Math.random().toString(36).slice(2, 8)}`;
    let cancelled = false;
    void (async () => {
      try {
        const { svg } = await mermaid.render(id, chart);
        if (!cancelled && holder.current) holder.current.innerHTML = svg;
      } catch (e) {
        if (!cancelled && holder.current) {
          holder.current.textContent =
            e instanceof Error ? `Diagram: ${e.message}` : "Diagram: render error";
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [chart, reactId]);

  return (
    <div
      ref={holder}
      className="my-4 rounded-lg border border-teal/25 bg-black/30 px-3 py-3 overflow-x-auto text-[12px]"
    />
  );
}
