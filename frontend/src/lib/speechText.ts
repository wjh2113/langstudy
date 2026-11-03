/**
 * Cut spoken text into short pieces so the first one can be synthesized quickly.
 * Same idea as 小树学堂: first piece ≤60 chars so sound starts soon, later pieces
 * ≤120. Decimal points and titles like "Mr." stay in one piece.
 */

const ABBREV = /^(?:Mr|Mrs|Ms|Dr|Prof|St|Sr|Jr|vs|etc|e\.g|i\.e|U\.S|U\.K)\.?$/i
// Words that start a new phrase. Cutting just before one keeps "and two glasses" together
// instead of "…and two | glasses…", which TTS reads as two half sentences.
const PHRASE_START = /\s(?=(?:and|but|or|so|because|when|while|where|which|who|whose|if|though|although|after|before|until|since|then|unless|whereas)\b)/gi
const MIN_HEAD = 20
const MIN_TAIL = 12
const ONLY_PUNCT = /^[。．.!！？?；;、，,\s'’"”]+$/

export function splitSentences(text: string, max = 120, firstMax = 60): string[] {
  const t = String(text || '').replace(/\s+/g, ' ').trim()
  if (!t) return []
  const parts = splitMarks(t)
  const out: string[] = []
  let cur = ''
  const limit = () => (out.length === 0 ? firstMax : max)

  const push = (s: string) => {
    const piece = s.trim()
    if (!piece) return
    // Never leave a lone "." / "!" chunk — it synthesizes as a blip and can abort playback.
    if (ONLY_PUNCT.test(piece)) {
      if (out.length) out[out.length - 1] = `${out[out.length - 1]}${piece}`.trim()
      else cur = `${cur}${piece}`
      return
    }
    out.push(piece)
  }

  for (const raw of parts) {
    let p = cur ? raw : raw.trimStart()
    while (p.length > limit()) {
      if (cur) {
        push(cur)
        cur = ''
        p = p.trimStart()
        continue
      }
      const lim = limit()
      const comma = Math.max(p.lastIndexOf('，', lim), p.lastIndexOf(',', lim), p.lastIndexOf('、', lim))
      let at = comma >= 12 ? comma + 1 : lim
      // No comma: cut before a conjunction / relative word ("water | and two glasses").
      const phrase = comma < 12 ? phraseCut(p, lim) : -1
      if (phrase > 0) at = phrase
      // A whole sentence that still fits in `max` is read as one clip rather than cut mid-phrase:
      // a slightly later first sound beats "two | glasses".
      else if (comma < 12 && p.length <= max) break
      // Hard cut: prefer the last space so we don't slice off a trailing "." into its own piece.
      // Skip spaces after Mr./Dr. so "Mr. Stein" stays together.
      if (comma < 12 && phrase <= 0) {
        let space = p.lastIndexOf(' ', lim)
        while (space >= 12) {
          const leftWord = p.slice(0, space).trim().split(/\s/).pop() || ''
          if (!ABBREV.test(leftWord)) break
          space = p.lastIndexOf(' ', space - 1)
        }
        if (space >= 12) at = space + 1
      }
      push(p.slice(0, at))
      p = p.slice(at).trimStart()
    }
    if (!p) continue
    // Fell out of the loop on purpose (sentence fits in max, no good cut): keep it whole.
    if (p.length > limit() && !cur) {
      push(p)
      continue
    }
    if (ONLY_PUNCT.test(p)) {
      if (cur) cur += p
      else if (out.length) out[out.length - 1] = `${out[out.length - 1]}${p}`.trim()
      else cur = p
      continue
    }
    if (cur && (cur + p).length > limit()) {
      push(cur)
      cur = p.trimStart()
    } else {
      cur += p
    }
  }
  if (cur.trim()) push(cur)
  return out.filter((s) => /[\p{L}\p{N}]/u.test(s))
}

/** Index just after the space that precedes the last phrase-starting word within `lim`, or -1. */
function phraseCut(p: string, lim: number): number {
  let best = -1
  PHRASE_START.lastIndex = 0
  let m: RegExpExecArray | null
  while ((m = PHRASE_START.exec(p))) {
    const at = m.index + 1
    if (at > lim) break
    if (at >= MIN_HEAD && p.length - at >= MIN_TAIL) best = at
  }
  return best
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
