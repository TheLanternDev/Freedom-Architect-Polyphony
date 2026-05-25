/** Wyłuskuje prawdopodobne pytania otwarte (linie kończące się znakiem zapytania). */
export function extractLikelyOpenQuestions(text: string, max = 14): string[] {
  const trimmed = text.trim();
  if (!trimmed) return [];

  const lines = trimmed
    .split(/\n+/)
    .map((l) => l.trim())
    .filter((l) => l.length > 12 && l.endsWith("?"));

  const seen = new Set<string>();
  const out: string[] = [];
  for (const line of lines) {
    if (!seen.has(line)) {
      seen.add(line);
      out.push(line);
      if (out.length >= max) return out;
    }
  }

  if (out.length >= 2) return out;

  const sentences = trimmed.split(/(?<=[.!?])\s+/);
  for (const s of sentences) {
    const t = s.trim();
    if (t.length > 18 && t.endsWith("?") && !seen.has(t)) {
      seen.add(t);
      out.push(t);
      if (out.length >= max) break;
    }
  }
  return out;
}
