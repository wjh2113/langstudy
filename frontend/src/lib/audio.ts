// One shared player: neural TTS from the backend, browser speech synthesis as fallback.
// Long lines are read in short pieces (same idea as 小树学堂): the first piece starts
// as soon as it is ready, and the next piece is fetched while that one plays.
// The voice stays whatever the server is configured to use.
import { shallowRef } from 'vue'
import { api } from '../api'
import { splitSentences } from './speechText'

const LOCALES: Record<string, string> = { en: 'en-US', ja: 'ja-JP' }
const cache = new Map<string, string>() // key -> object URL
const pending = new Map<string, Promise<string>>() // same sentence, still downloading
let current: { id: string | null; audio: HTMLAudioElement | null; token: number } = { id: null, audio: null, token: 0 }
let serverTTS = true

/** Reactive id of the item currently playing (null when idle). */
export const playingId = shallowRef<string | null>(null)

function emit() {
  playingId.value = current.id
}

export function setServerTTS(enabled: boolean) {
  serverTTS = enabled
}

// Listening accent and reading voice chosen by the learner (applies to every play() call
// that does not name its own voice, such as a dialogue role).
let voiceOpts: { accent: string; locale: string | null; voiceIndex: number } = { accent: 'default', locale: null, voiceIndex: 0 }
export function setVoiceOptions({ accent = 'default', locale = null, voiceIndex = 0 }: { accent?: string; locale?: string | null; voiceIndex?: number } = {}) {
  voiceOpts = { accent, locale, voiceIndex }
}

export function stop() {
  current.token++
  if (current.audio) {
    const a = current.audio
    // Clear end/error first; leave onpause so playUrl can resolve on interrupt
    // (it only resolves pause when the token no longer matches).
    a.onended = null
    a.onerror = null
    a.onplaying = null
    try { a.pause() } catch { /* ignore */ }
    a.onpause = null
    current.audio = null
  }
  if (window.speechSynthesis) window.speechSynthesis.cancel()
  current.id = null
  emit()
}

function speakBrowser(text: string, language: string, rate: number, token: number, locale: string | null | undefined, onStart?: () => void) {
  return new Promise<void>((resolve, reject) => {
    if (!window.speechSynthesis) return reject(new Error('当前浏览器不支持朗读'))
    const u = new SpeechSynthesisUtterance(text)
    u.lang = locale || LOCALES[language] || language
    u.rate = rate
    const voices = window.speechSynthesis.getVoices()
    const voice = voices.find((v) => v.lang.replace('_', '-') === u.lang) || voices.find((v) => v.lang.startsWith(u.lang.slice(0, 2)))
    if (voice) u.voice = voice
    u.onstart = () => onStart?.()
    u.onend = () => resolve()
    u.onerror = (e) => (e.error === 'interrupted' || e.error === 'canceled' || token !== current.token ? resolve() : reject(new Error('朗读失败')))
    window.speechSynthesis.speak(u)
  })
}

function fetchAudio(text: string, language: string, voiceIndex: number, rate: number, accent: string): Promise<string> {
  const key = `${language}|${accent}|${voiceIndex}|${rate}|${text}`
  const hit = cache.get(key)
  if (hit) return Promise.resolve(hit)
  let job = pending.get(key)
  if (!job) {
    job = api.tts({ text, language, voiceIndex, rate, accent }).then((blob) => {
      const url = URL.createObjectURL(blob)
      cache.set(key, url)
      pending.delete(key)
      return url
    }).catch((err) => {
      pending.delete(key)
      throw err
    })
    pending.set(key, job)
  }
  return job
}

/** Warm the first short piece (and optionally the rest) so click-to-sound is quick. Same idea as 小树学堂 prefetch. */
export function prefetch(text: string, opts: PlayOptions = {}) {
  if (!serverTTS || !text?.trim()) return
  const language = opts.language ?? 'en'
  const rate = opts.rate ?? 1
  const voiceIndex = opts.voiceIndex ?? voiceOpts.voiceIndex
  let accent = opts.accent
  if (accent === undefined) ({ accent } = voiceOpts)
  const accentKey = accent || 'default'
  const first = splitSentences(text)[0]
  if (first) fetchAudio(first, language, voiceIndex, rate, accentKey).catch(() => {})
}

function playUrl(url: string, token: number, onStart?: () => void) {
  return new Promise<void>((resolve, reject) => {
    if (token !== current.token) return resolve()
    const audio = new Audio(url)
    current.audio = audio
    let settled = false
    const done = () => {
      if (settled) return
      settled = true
      resolve()
    }
    audio.onplaying = () => onStart?.()
    audio.onended = () => done()
    // Only treat pause as done when stop()/another play() bumped the token.
    // Mobile browsers also pause while buffering; resolving then cuts the clip short.
    audio.onpause = () => {
      if (token !== current.token) done()
    }
    audio.onerror = () => {
      if (settled) return
      settled = true
      reject(new Error('音频播放失败'))
    }
    audio.play().catch((err) => {
      if (settled) return
      settled = true
      reject(err)
    })
  })
}

/** Play text; resolves when playback ends or is stopped. */
export interface PlayOptions {
  language?: string
  voiceIndex?: number
  rate?: number
  accent?: string
  locale?: string | null
  /** false keeps one clip, for shadowing where a pause between sentences would throw off the timing. */
  chunked?: boolean
  onStart?: () => void
}

export async function play(id: string, text: string, opts: PlayOptions = {}) {
  const language = opts.language ?? 'en'
  const rate = opts.rate ?? 1
  const chunked = opts.chunked !== false
  const onStart = opts.onStart
  // accent and voice default to the learner's current choice (setVoiceOptions)
  const voiceIndex = opts.voiceIndex ?? voiceOpts.voiceIndex
  let accent = opts.accent
  let locale = opts.locale
  if (accent === undefined) ({ accent, locale } = voiceOpts)
  const accentKey = accent || 'default'
  // Kick off the first chunk before stop() so a warm prefetch is not thrown away.
  const parts = (chunked ? splitSentences(text) : [text.trim()]).filter((p) => /[\p{L}\p{N}]/u.test(p))
  const firstJob = serverTTS && parts[0]
    ? fetchAudio(parts[0], language, voiceIndex, rate, accentKey)
    : null
  stop()
  const token = current.token
  current.id = id
  emit()
  try {
    if (!serverTTS) {
      await speakBrowser(parts.join(' ') || text, language, rate, token, locale, onStart)
      return
    }
    let upcoming: Promise<string> | null = firstJob
    for (let i = 0; i < parts.length; i++) {
      if (token !== current.token) return
      const job = upcoming ?? fetchAudio(parts[i], language, voiceIndex, rate, accentKey)
      upcoming = null
      let url: string | null = null
      try {
        url = await job
      } catch (e) {
        console.warn('server TTS failed, falling back to browser voice', e)
      }
      if (token !== current.token) return
      if (!url) {
        await speakBrowser(parts.slice(i).join(' '), language, rate, token, locale, i === 0 ? onStart : undefined)
        return
      }
      if (i + 1 < parts.length) upcoming = fetchAudio(parts[i + 1], language, voiceIndex, rate, accentKey)
      await playUrl(url, token, i === 0 ? onStart : undefined)
    }
  } finally {
    if (token === current.token) {
      current.id = null
      current.audio = null
      emit()
    }
  }
}

/** Play several items in order; stops if another play/stop happens. */
export async function playSequence(items: { id: string; text: string; voiceIndex?: number }[], opts: PlayOptions) {
  for (let i = 0; i < items.length; i++) {
    const item = items[i]
    const before = current.token
    const next = items[i + 1]
    if (next) prefetch(next.text, { ...opts, voiceIndex: next.voiceIndex ?? opts.voiceIndex })
    await play(item.id, item.text, { ...opts, voiceIndex: item.voiceIndex ?? opts.voiceIndex })
    // play() increments token once at its start; anything more means interrupted
    if (current.token !== before + 1) return
  }
}
