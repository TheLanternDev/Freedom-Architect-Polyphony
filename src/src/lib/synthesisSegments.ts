export type SynthesisSegment =
  | { kind: "text"; value: string }
  | { kind: "mermaid"; value: string };

/** Dzieli syntezę na prozę i bloki diagramów Mermaid (bez zewnętrznych fence'y). */
export function splitSynthesisSegments(raw: string): SynthesisSegment[] {
  const re = /```mermaid\s*\n([\s\S]*?)```/gi;
  const out: SynthesisSegment[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(raw)) !== null) {
    const before = raw.slice(last, m.index).trimEnd();
    if (before) out.push({ kind: "text", value: before });
    out.push({ kind: "mermaid", value: m[1].trim() });
    last = m.index + m[0].length;
  }
  const tail = raw.slice(last).trimEnd();
  if (tail) out.push({ kind: "text", value: tail });
  return out.length ? out : [{ kind: "text", value: raw.trim() }];
}
