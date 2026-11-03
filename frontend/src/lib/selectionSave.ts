// 选中的练习原文：一个词进生词本，从句或整句进错句本。与收藏卡片的 kind 一致。

export type CardKind = 'word' | 'sentence'

export function collapsed(text: string): string {
  return (text || '').replace(/\s+/g, ' ').trim()
}

const EDGE = /[^0-9A-Za-z\u00C0-\u024F\u3040-\u30FF\u3400-\u9FFF'’]/

/** 单词去掉首尾标点；句子保留标点。过长的正面截到接口上限。 */
export function cleanFront(text: string, kind: CardKind): string {
  let t = collapsed(text)
  if (kind === 'word') {
    while (t && EDGE.test(t[0] || '')) t = t.slice(1)
    while (t && EDGE.test(t[t.length - 1] || '')) t = t.slice(0, -1)
  }
  return t.trim().slice(0, 500)
}

export function selectionKind(text: string, language: string): CardKind {
  const t = collapsed(text)
  if (!t) return 'word'
  // 句末或分句标点：整段当句子收藏
  if (/[。！？!?；;]/.test(t)) return 'sentence'
  if (language === 'ja') {
    if (/[、，,]/.test(t)) return 'sentence'
    const n = segmentWordCount(t, 'ja')
    if (n >= 2) return 'sentence'
    if (n === 1) return 'word'
    // 没有分词器时，很长的一串文字更像句子而不是一个词
    return [...t.replace(/\s/g, '')].length >= 12 ? 'sentence' : 'word'
  }
  if (/[,，、]/.test(t) && /\s/.test(t)) return 'sentence'
  return t.split(/\s+/).filter(Boolean).length >= 2 ? 'sentence' : 'word'
}

/** 单词卡用所在原句当例句；句子卡的 example 是“更地道的说法”，这里留空。 */
export function exampleFor(kind: CardKind, front: string, sentence: string): string {
  if (kind !== 'word') return ''
  const whole = collapsed(sentence)
  if (!whole || whole === front) return ''
  return whole.slice(0, 500)
}

type WordSeg = { segment: (input: string) => Iterable<{ index: number; segment: string; isWordLike?: boolean }> }

function segmenter(language: string): WordSeg | null {
  const Seg = (Intl as typeof Intl & { Segmenter?: new (locale: string, opts: { granularity: 'word' }) => WordSeg }).Segmenter
  if (typeof Seg !== 'function') return null
  try {
    return new Seg(language === 'ja' ? 'ja' : 'en', { granularity: 'word' })
  } catch {
    return null
  }
}

function segmentWordCount(text: string, language: string): number {
  const seg = segmenter(language)
  if (!seg) return 0
  let n = 0
  for (const part of seg.segment(text)) if (part.isWordLike && part.segment.trim()) n++
  return n
}

/** 手指落下的位置对应的一个词（UTF-16 偏移，和 DOM 选区一致）。 */
export function wordRangeIn(text: string, offset: number, language: string): { start: number; end: number } | null {
  if (!text) return null
  if (language === 'ja') {
    const hit = segmentHit(text, offset, 'ja')
    if (hit) return hit
  }
  const latin = latinWordAt(text, offset)
  if (latin) return latin
  if (language === 'ja') return cjkCharAt(text, offset)
  return null
}

function segmentHit(text: string, offset: number, language: string): { start: number; end: number } | null {
  const seg = segmenter(language)
  if (!seg) return null
  let prev: { start: number; end: number } | null = null
  for (const part of seg.segment(text)) {
    const start = part.index
    const end = start + part.segment.length
    if (!part.isWordLike || !part.segment.trim()) continue
    if (offset >= start && offset < end) return { start, end }
    if (offset === end) prev = { start, end }
    else if (offset < start) return prev
  }
  return prev
}

function isLatinWordChar(ch: string): boolean {
  return /[0-9A-Za-z\u00C0-\u024F'’-]/.test(ch)
}

function latinWordAt(text: string, offset: number): { start: number; end: number } | null {
  if (!text) return null
  let i = Math.max(0, Math.min(offset, text.length))
  if (i >= text.length || (i > 0 && !isLatinWordChar(text[i] || '') && isLatinWordChar(text[i - 1] || ''))) i--
  if (i < 0 || !isLatinWordChar(text[i] || '')) return null
  let a = i
  let b = i + 1
  while (a > 0 && isLatinWordChar(text[a - 1] || '')) a--
  while (b < text.length && isLatinWordChar(text[b] || '')) b++
  if (!/[0-9A-Za-z\u00C0-\u024F]/.test(text.slice(a, b))) return null
  return { start: a, end: b }
}

function cjkCharAt(text: string, offset: number): { start: number; end: number } | null {
  if (!text) return null
  let i = Math.max(0, Math.min(offset, text.length - 1))
  const ch = text[i] || ''
  if (!/[\u3040-\u30FF\u3400-\u9FFF]/.test(ch)) return null
  return { start: i, end: i + 1 }
}
