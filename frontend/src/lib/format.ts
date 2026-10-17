import type { Mode } from '../api/models'

export const MODE_NAMES: Record<Mode, string> = {
  questions: '话题问答', dialogue: '情景对话', article: '短文', chat: '自由对话', dictation: '精听填空',
}
export const LANG_NAMES: Record<string, string> = { en: 'English', ja: '日本語' }
export const LEVEL_NAMES: Record<string, string> = { beginner: '入门', intermediate: '中级', advanced: '高级' }

/** Score colour band from the design system: ≥90 green, 70–89 orange, <70 red. */
export const scoreBand = (s: number | null | undefined) => (s == null ? '' : s >= 90 ? 'good' : s >= 70 ? 'mid' : 'low')

export const dateOnly = (iso?: string | null) => (iso ? iso.slice(0, 10) : '')
export const dateTime = (iso?: string | null) => (iso ? iso.replace('T', ' ').slice(0, 16) : '')

export function mmss(seconds: number) {
  const s = Math.max(0, Math.floor(seconds))
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}
