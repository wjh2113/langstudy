// One shared player: neural TTS from the backend, browser speech synthesis as fallback.
import { shallowRef } from 'vue'
import { api } from '../api'

const LOCALES: Record<string, string> = { en: 'en-US', ja: 'ja-JP' }
const cache = new Map<string, string>() // key -> object URL
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

async function fetchAudio(text: string, language: string, voiceIndex: number, rate: number, accent: string) {
  const key = `${language}|${accent}|${voiceIndex}|${rate}|${text}`
  if (!cache.has(key)) {
    const blob = await api.tts({ text, language, voiceIndex, rate, accent })
    cache.set(key, URL.createObjectURL(blob))
  }
  return cache.get(key) as string
}

/** Play text; resolves when playback ends or is stopped. */
export interface PlayOptions {
  language?: string
  voiceIndex?: number
  rate?: number
  accent?: string
  locale?: string | null
  onStart?: () => void
}

export async function play(id: string, text: string, { language = 'en', voiceIndex = 0, rate = 1, accent, locale, onStart }: PlayOptions = {}) {
  // accent defaults to the learner's current choice (setVoiceOptions)
  if (accent === undefined) ({ accent, locale } = voiceOpts)
  stop()
  const token = current.token
  current.id = id
  emit()
  try {
    let url: string | null = null
    if (serverTTS) {
      try {
        url = await fetchAudio(text, language, voiceIndex, rate, accent || 'default')
      } catch (e) {
        console.warn('server TTS failed, falling back to browser voice', e)
      }
    }
    if (token !== current.token) return
    if (url) {
      await new Promise<void>((resolve, reject) => {
        const audio = new Audio(url as string)
        current.audio = audio
        audio.onplaying = () => onStart?.()
        audio.onended = () => resolve()
        audio.onpause = () => resolve()
        audio.onerror = () => reject(new Error('音频播放失败'))
        audio.play().catch(reject)
      })
    } else {
      await speakBrowser(text, language, rate, token, locale, onStart)
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
