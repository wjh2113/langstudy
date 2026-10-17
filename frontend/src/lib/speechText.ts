/**
 * Cut spoken text into short pieces so the first one can be synthesized quickly.
 * Same idea as 小树学堂: a short opening, then longer pieces. Decimal points and
 * titles like "Mr." stay in one piece.
 */

const ABBREV = /^(?:Mr|Mrs|Ms|Dr|Prof|St|Sr|Jr|vs|etc|e\.g|i\.e|U\.S|U\.K)\.?$/i

export function splitSentences(text: string, max = 140, firstMax = 80): string[] {
  const t = String(text || '').replace(/\s+/g, ' ').trim()
  if (!t) return []
  const parts = splitMarks(t)
  const out: string[] = []
  let cur = ''
  const limit = () => (out.length === 0 ? firstMax : max)
  for (const raw of parts) {
    let p = cur ? raw : raw.trimStart()
    while (p.length > limit()) {
      if (cur) {
        out.push(cur.trim())
        cur = ''
        p = p.trimStart()
        continue
      }
      const lim = limit()
      const cut = Math.max(p.lastIndexOf('，', lim), p.lastIndexOf(',', lim), p.lastIndexOf('、', lim))
      const at = cut >= 12 ? cut + 1 : lim
      out.push(p.slice(0, at).trim())
      p = p.slice(at).trimStart()
    }
    if (!p) continue
    if (cur && (cur + p).length > limit()) {
      out.push(cur.trim())
      cur = p.trimStart()
    } else {
      cur += p
    }
  }
  if (cur.trim()) out.push(cur.trim())
  return out.filter(Boolean)
}

function splitMarks(t: string): string[] {
  const out: string[] = []
  let start = 0
  for (let i = 0; i < t.length; i++) {
    const ch = t[i]
    if ('。！？!?；;'.includes(ch)) {
      out.push(t.slice(start, i + 1))
      start = i + 1
      continue
    }
    if (ch === '.' && isSentenceDot(t, i)) {
      out.push(t.slice(start, i + 1))
      start = i + 1
    }
  }
  if (start < t.length) out.push(t.slice(start))
  return out.length ? out : [t]
}

function isSentenceDot(t: string, i: number): boolean {
  const next = t[i + 1]
  if (next && next !== ' ' && next !== '\n') return false
  const after = t.slice(i + 1).trimStart()
  if (!after) return true
  if (!/^[A-Z“"「]/.test(after)) return false
  const before = t.slice(0, i).trimEnd()
  const word = before.split(/\s/).pop() || ''
  return !ABBREV.test(word)
}
