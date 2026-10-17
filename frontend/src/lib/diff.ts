// Client-side version of backend reference_diff, for instant shadowing feedback.
import type { Diff } from '../api/models'

const JA_PUNCT = /[、。！？「」『』（）・…，．：；!?,.()"'\s　]/

const kataToHira = (s: string) => s.replace(/[ァ-ヶ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60))

function key(token: string, language: string): string | null {
  const t = token.normalize('NFKC').toLowerCase()
  if (language === 'ja') return JA_PUNCT.test(t) ? null : kataToHira(t)
  const m = t.replace(/[^a-z0-9']/g, '')
  return m || null
}

export function tokensOf(text: string, language: string): string[] {
  const t = (text || '').normalize('NFKC').toLowerCase()
  if (language === 'ja') return [...kataToHira(t)].filter((c) => !JA_PUNCT.test(c))
  return t.match(/[a-z0-9']+/g) || []
}

/** LCS alignment: which reference tokens were heard. */
export function diffReference(reference: string, spoken: string, language: string): Diff {
  const display = language === 'ja' ? [...reference.normalize('NFKC')] : reference.split(/\s+/).filter(Boolean)
  const keys = display.map((d) => key(d, language))
  const a = keys.filter((k): k is string => Boolean(k))
  const b = tokensOf(spoken, language)
  const dp = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0))
  for (let i = a.length - 1; i >= 0; i--)
    for (let j = b.length - 1; j >= 0; j--)
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
  const matched = new Set<number>()
  for (let i = 0, j = 0; i < a.length && j < b.length;) {
    if (a[i] === b[j]) { matched.add(i); i++; j++ } else if (dp[i + 1][j] >= dp[i][j + 1]) i++
    else j++
  }
  let ki = 0
  const tokens = display.map((t, idx) => (keys[idx] === null ? { t, ok: true } : { t, ok: matched.has(ki++) }))
  return { tokens, similarity: a.length ? matched.size / a.length : 0 }
}
