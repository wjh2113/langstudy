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

// Listening accent chosen by the learner (applies to every play() call)
let voiceOpts: { accent: string; locale: string | null } = { accent: 'default', locale: null }
export function setVoiceOptions({ accent = 'default', locale = null }: { accent?: string; locale?: string | null } = {}) {
  voiceOpts = { accent, locale }
}

export function stop() {
  current.token++
  if (current.audio) {
    current.audio.pause()
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

function playUrl(url: string, token: number, onStart?: () => void) {
  return new Promise<void>((resolve, reject) => {
    if (token !== current.token) return resolve()
    const audio = new Audio(url)
    current.audio = audio
    audio.onplaying = () => onStart?.()
    audio.onended = () => resolve()
    audio.onpause = () => resolve()
    audio.onerror = () => reject(new Error('音频播放失败'))
    audio.play().catch(reject)
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

export async function play(id: string, text: string, { language = 'en', voiceIndex = 0, rate = 1, accent, locale, chunked = true, onStart }: PlayOptions = {}) {
  // accent defaults to the learner's current choice (setVoiceOptions)
  if (accent === undefined) ({ accent, locale } = voiceOpts)
  const accentKey = accent || 'default'
  stop()
  const token = current.token
  current.id = id
  emit()
  const parts = (chunked ? splitSentences(text) : [text.trim()]).filter(Boolean)
  try {
    if (!serverTTS) {
      await speakBrowser(parts.join(' ') || text, language, rate, token, locale, onStart)
      return
    }
    let upcoming: Promise<string> | null = null
    for (let i = 0; i < parts.length; i++) {
      if (token !== current.token) return
      const job = upcoming ?? fetchAudio(parts[i], language, voiceIndex, rate, accentKey)
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
  for (const item of items) {
    const before = current.token
    await play(item.id, item.text, { ...opts, voiceIndex: item.voiceIndex ?? opts.voiceIndex })
    // play() increments token once at its start; anything more means interrupted
    if (current.token !== before + 1) return
  }
}
