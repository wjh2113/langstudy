// One shared player: neural TTS from the backend, browser speech synthesis as fallback.
import { shallowRef } from 'vue'
import { api } from './api'

const LOCALES = { en: 'en-US', ja: 'ja-JP' }
const cache = new Map() // key -> object URL
let current = { id: null, audio: null, token: 0 }
let serverTTS = true

/** Reactive id of the item currently playing (null when idle). */
export const playingId = shallowRef(null)

function emit() {
  playingId.value = current.id
}

export function setServerTTS(enabled) {
  serverTTS = enabled
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

function speakBrowser(text, language, rate, token) {
  return new Promise((resolve, reject) => {
    if (!window.speechSynthesis) return reject(new Error('当前浏览器不支持朗读'))
    const u = new SpeechSynthesisUtterance(text)
    u.lang = LOCALES[language] || language
    u.rate = rate
    const voice = window.speechSynthesis.getVoices().find((v) => v.lang.startsWith(u.lang.slice(0, 2)))
    if (voice) u.voice = voice
    u.onend = () => resolve()
    u.onerror = (e) => (e.error === 'interrupted' || e.error === 'canceled' || token !== current.token ? resolve() : reject(new Error('朗读失败')))
    window.speechSynthesis.speak(u)
  })
}

async function fetchAudio(text, language, voiceIndex, rate) {
  const key = `${language}|${voiceIndex}|${rate}|${text}`
  if (!cache.has(key)) {
    const blob = await api.tts({ text, language, voiceIndex, rate })
    cache.set(key, URL.createObjectURL(blob))
  }
  return cache.get(key)
}

/** Play text; resolves when playback ends or is stopped. */
export async function play(id, text, { language = 'en', voiceIndex = 0, rate = 1 } = {}) {
  stop()
  const token = current.token
  current.id = id
  emit()
  try {
    let url = null
    if (serverTTS) {
      try {
        url = await fetchAudio(text, language, voiceIndex, rate)
      } catch (e) {
        console.warn('server TTS failed, falling back to browser voice', e)
      }
    }
    if (token !== current.token) return
    if (url) {
      await new Promise((resolve, reject) => {
        const audio = new Audio(url)
        current.audio = audio
        audio.onended = resolve
        audio.onpause = resolve
        audio.onerror = () => reject(new Error('音频播放失败'))
        audio.play().catch(reject)
      })
    } else {
      await speakBrowser(text, language, rate, token)
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
export async function playSequence(items, opts) {
  for (const item of items) {
    const before = current.token
    await play(item.id, item.text, { ...opts, voiceIndex: item.voiceIndex ?? opts.voiceIndex })
    // play() increments token once at its start; anything more means interrupted
    if (current.token !== before + 1) return
  }
}
