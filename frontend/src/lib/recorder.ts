// Microphone recording + speech recognition (Vue composable).
// - MediaRecorder keeps the audio so the learner can hear themselves.
// - Transcript comes from the browser's SpeechRecognition, or from the backend
//   (/api/stt) when server recognition is configured.
// - An analyser tracks the input level (for the UI ring) and when speech
//   starts/ends, so speaking rate isn't diluted by silence before/after.
import { onBeforeUnmount, ref } from 'vue'
import { api } from '../api'

const SR: any = typeof window !== 'undefined' && ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition)
export const browserRecognitionSupported = Boolean(SR)

const SR_ERRORS: Record<string, string> = {
  network: '浏览器语音识别连不上服务（Chrome 在国内通常无法使用）。请换用 Edge 浏览器，或在后端配置服务端识别；也可以改用文字输入。',
  'not-allowed': '没有麦克风权限。请在浏览器地址栏左侧允许使用麦克风。',
  'service-not-allowed': '浏览器不允许语音识别。请换用 Edge 浏览器，或改用文字输入。',
  'audio-capture': '没有检测到麦克风。',
  'language-not-supported': '浏览器不支持这个语言的识别，请在后端配置服务端识别。',
}

const SILENCE_MS = 1500 // hands-free: this long a pause after speaking ends the answer
const NO_SPEECH_MS = 8000 // hands-free: give up if nothing is said
const MAX_MS = 90000

export interface RecordingResult {
  text: string
  confidence: number | null
  durationSec: number
  audioBlob: Blob | null
  audioUrl: string | null
  startedAt: number
  voiceStartAt: number | null
}

/**
 * Microphone + recognition for one answer box.
 * onAutoStop fires once when hands-free mode decides the answer is over.
 */
export function useRecorder(
  getEnv: () => { locale: string; language: string; serverSTT: boolean },
  options: { onAutoStop?: () => void } = {},
) {
  const state = ref<'idle' | 'recording' | 'processing'>('idle')
  const elapsed = ref(0) // seconds since recording started (for the timer)
  const level = ref(0)
  const interim = ref('')
  const error = ref('')
  let s: any = {}

  function cleanup() {
    cancelAnimationFrame(s.raf)
    clearInterval(s.clock)
    s.stream?.getTracks().forEach((t: MediaStreamTrack) => t.stop())
    s.audioCtx?.close().catch(() => {})
    s.stream = s.audioCtx = null
  }

  onBeforeUnmount(() => {
    s.wantRecognition = false
    try { s.recognition?.abort() } catch { /* ignore */ }
    cleanup()
  })

  /** autoStop: end automatically after a pause (hands-free mode). */
  async function start({ autoStop = false }: { autoStop?: boolean } = {}) {
    const { locale, language, serverSTT } = getEnv()
    error.value = ''
    interim.value = ''
    if (!navigator.mediaDevices?.getUserMedia) {
      error.value = '当前浏览器不支持录音，请使用最新版 Edge 或 Chrome，并通过 localhost 访问。'
      return false
    }
    if (!serverSTT && !SR) {
      error.value = '当前浏览器不支持语音识别。请换用 Edge 浏览器，或在后端配置服务端识别；也可以改用文字输入。'
      return false
    }
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
    } catch {
      error.value = SR_ERRORS['not-allowed']
      return false
    }
    s = { stream, chunks: [], finals: [], confidences: [], startedAt: performance.now(), language, serverSTT, autoStop }

    // level meter + voice activity
    const AC = window.AudioContext || (window as any).webkitAudioContext
    s.audioCtx = new AC()
    const analyser = s.audioCtx.createAnalyser()
    analyser.fftSize = 1024
    s.audioCtx.createMediaStreamSource(stream).connect(analyser)
    const buf = new Uint8Array(analyser.fftSize)
    const tick = () => {
      analyser.getByteTimeDomainData(buf)
      let sum = 0
      for (let i = 0; i < buf.length; i++) {
        const v = (buf[i] - 128) / 128
        sum += v * v
      }
      const rms = Math.sqrt(sum / buf.length)
      const now = performance.now()
      if (rms > 0.035) {
        if (!s.firstVoice) s.firstVoice = now
        s.lastVoice = now
      }
      level.value = Math.min(1, rms * 6)
      if (s.autoStop && !s.autoStopped) {
        const quiet = s.firstVoice ? now - s.lastVoice > SILENCE_MS : now - s.startedAt > NO_SPEECH_MS
        if (quiet || now - s.startedAt > MAX_MS) {
          s.autoStopped = true
          options.onAutoStop?.()
        }
      }
      s.raf = requestAnimationFrame(tick)
    }
    tick()

    // recorder
    try {
      s.recorder = new MediaRecorder(stream)
      s.recorder.ondataavailable = (e: BlobEvent) => e.data.size && s.chunks.push(e.data)
      s.recorder.start()
    } catch {
      s.recorder = null
    }

    // browser recognition: the transcript itself, or (with server recognition) just live feedback
    if (SR) {
      const rec = new SR()
      const session = s
      rec.lang = locale
      rec.continuous = true
      rec.interimResults = true
      rec.onresult = (e: any) => {
        let text = ''
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const res = e.results[i]
          if (res.isFinal) {
            session.finals.push(res[0].transcript)
            if (res[0].confidence > 0) session.confidences.push(res[0].confidence)
          } else text += res[0].transcript
        }
        interim.value = text
      }
      rec.onerror = (e: any) => {
        if (serverSTT) { session.recError = e.error; return } // live text is a bonus; ignore failures
        if (e.error !== 'no-speech' && e.error !== 'aborted') {
          session.recError = SR_ERRORS[e.error] || `语音识别出错：${e.error}`
          error.value = session.recError
        }
      }
      rec.onend = () => {
        // Chrome/Edge end recognition after a pause; keep it running while recording
        if (session.wantRecognition && !session.recError) {
          try { rec.start() } catch { /* already started */ }
        } else session.recEnded?.()
      }
      s.recognition = rec
      s.wantRecognition = true
      try { rec.start() } catch { /* ignore */ }
    }
    elapsed.value = 0
    s.clock = setInterval(() => (elapsed.value = Math.round((performance.now() - s.startedAt) / 1000)), 250)
    state.value = 'recording'
    return true
  }

  async function stop(): Promise<RecordingResult | null> {
    if (!s.stream) return null
    const session = s
    state.value = 'processing'
    const endedAt = performance.now()
    session.wantRecognition = false

    const recorded = new Promise<Blob | null>((resolve) => {
      if (!session.recorder || session.recorder.state === 'inactive') return resolve(null)
      session.recorder.onstop = () => resolve(new Blob(session.chunks, { type: session.recorder.mimeType || 'audio/webm' }))
      session.recorder.stop()
    })
    const recognised = new Promise<void>((resolve) => {
      if (!session.recognition) return resolve()
      if (session.serverSTT) { // live text only: don't wait for it
        try { session.recognition.abort() } catch { /* ignore */ }
        return resolve()
      }
      session.recEnded = () => resolve()
      try { session.recognition.stop() } catch { resolve() }
      setTimeout(() => resolve(), 2500) // don't hang if onend never fires
    })
    const [blob] = await Promise.all([recorded, recognised])
    cleanup()
    level.value = 0
    interim.value = ''

    const voiced = session.firstVoice && session.lastVoice ? (session.lastVoice - session.firstVoice) / 1000 + 0.4 : 0
    const total = (endedAt - session.startedAt) / 1000
    const durationSec = Math.round(Math.min(total, voiced || total) * 10) / 10

    let text = session.finals.join(session.language === 'ja' ? '' : ' ').trim()
    let confidence: number | null = session.confidences.length
      ? session.confidences.reduce((a: number, b: number) => a + b, 0) / session.confidences.length
      : null
    if (session.serverSTT && blob) {
      try {
        text = (await api.stt(blob, session.language)).text
        confidence = null
      } catch (e: any) {
        error.value = e.message
      }
    }
    state.value = 'idle'
    return {
      text, confidence, durationSec, audioBlob: blob, audioUrl: blob ? URL.createObjectURL(blob) : null,
      startedAt: session.startedAt, voiceStartAt: session.firstVoice || null, // for shadowing lag
    }
  }

  return { state, level, interim, error, elapsed, start, stop }
}
