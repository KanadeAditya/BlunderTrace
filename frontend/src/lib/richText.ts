// Card text from the API has two inline marks (docs/API.md): `*…*` = emphasis, `[n]` = citation.
export type Segment =
  | { kind: 'text'; text: string }
  | { kind: 'em'; text: string }
  | { kind: 'cite'; n: number }

/** Split text into plain / emphasised / citation pieces. Citations outside 1..sourceCount are dropped. */
export function parseMarked(text: string, sourceCount: number): Segment[] {
  const out: Segment[] = []
  for (const part of text.split(/(\*[^*]+\*|\[\d+\])/g)) {
    if (!part) continue
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      out.push({ kind: 'em', text: part.slice(1, -1) })
    } else if (/^\[\d+\]$/.test(part)) {
      const n = Number(part.slice(1, -1))
      if (n >= 1 && n <= sourceCount) out.push({ kind: 'cite', n })
    } else {
      out.push({ kind: 'text', text: part })
    }
  }
  return out
}
