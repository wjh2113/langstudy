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
// On phones the browser's recogniser fights MediaRecorder for the microphone (and in mainland China
// it can't reach Google anyway), so with server recognition we only record there.
const isMobile = typeof navigator !== 'undefined' && /Android|iPhone|iPad|iPod|Mobile|HarmonyOS/i.test(navigator.userAgent)

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
const RECORDER_STOP_MS = 3000 // MediaRecorder.onstop can hang on some mobile browsers
const STT_TIMEOUT_MS = 45000 // don't leave the UI on「正在识别…」forever

export interface RecordingResult {
  text: string
  confidence: number | null
  durationSec: number
  audioBlob: Blob | null
  audioUrl: string | null
  startedAt: number
  voiceStartAt: number | null
}

function pickMime(): string {
  if (typeof MediaRecorder === 'undefined' || !MediaRecorder.isTypeSupported) return ''
  const types = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4',
    'audio/aac',
    'audio/ogg;codecs=opus',
  ]
  return types.find((t) => MediaRecorder.isTypeSupported(t)) || ''
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
    if (state.value !== 'idle') return false
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
    try { await s.audioCtx.resume() } catch { /* ignore */ }
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

    // recorder — pick a mime the phone actually supports (Safari prefers mp4)
    try {
      const mime = pickMime()
      s.mime = mime
      s.recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined)
      s.recorder.ondataavailable = (e: BlobEvent) => e.data?.size && s.chunks.push(e.data)
      s.recorder.start(250) // timeslice so short taps still get data before stop
    } catch {
      s.recorder = null
    }

    // browser recognition: the transcript itself, or (with server recognition) just live feedback on desktop
    if (SR && !(serverSTT && isMobile)) {
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

  function blobFromChunks(session: any): Blob | null {
    if (!session.chunks?.length) return null
    const type = (session.recorder?.mimeType || session.mime || 'audio/webm').split(';')[0]
    return new Blob(session.chunks, { type })
  }

  /** Wait for MediaRecorder to flush; never hang the「正在识别…」UI. */
  function stopRecorder(session: any): Promise<Blob | null> {
    return new Promise((resolve) => {
      if (!session.recorder || session.recorder.state === 'inactive') return resolve(blobFromChunks(session))
      let done = false
      const finish = (blob: Blob | null) => {
        if (done) return
        done = true
        resolve(blob)
      }
      session.recorder.onstop = () => finish(blobFromChunks(session))
      session.recorder.onerror = () => finish(blobFromChunks(session))
      try {
        if (typeof session.recorder.requestData === 'function' && session.recorder.state === 'recording') {
          session.recorder.requestData()
        }
        session.recorder.stop()
      } catch {
        finish(blobFromChunks(session))
        return
      }
      setTimeout(() => finish(blobFromChunks(session)), RECORDER_STOP_MS)
    })
  }

  async function stop(): Promise<RecordingResult | null> {
    if (!s.stream || state.value === 'processing') return null
    const session = s
    state.value = 'processing'
    const endedAt = performance.now()
    session.wantRecognition = false

    try {
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
      const t0 = performance.now()
      const [blob] = await Promise.all([stopRecorder(session), recognised])
      const tFlushed = performance.now()
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
      if (session.serverSTT) {
        if (!blob || blob.size < 64) {
          if (!text) error.value = '没有录到声音，请靠近麦克风再说一次'
        } else {
          try {
            const ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null
            const timer = ctrl ? setTimeout(() => ctrl.abort(), STT_TIMEOUT_MS) : 0
            try {
              text = (await api.stt(blob, session.language, ctrl?.signal)).text
              confidence = null
              console.info(`[stt] ${blob.type} ${Math.round(blob.size / 1024)}KB · 停止录音 ${Math.round(tFlushed - t0)}ms · 上传+识别 ${Math.round(performance.now() - tFlushed)}ms`)
            } finally {
              if (timer) clearTimeout(timer)
            }
          } catch (e: any) {
            if (e?.name === 'AbortError') error.value = '识别超时了，请再试一次或改用文字输入'
            else error.value = e.message || '语音识别失败，请再试一次'
          }
        }
      }
      return {
        text, confidence, durationSec, audioBlob: blob, audioUrl: blob ? URL.createObjectURL(blob) : null,
        startedAt: session.startedAt, voiceStartAt: session.firstVoice || null, // for shadowing lag
      }
    } catch (e: any) {
      cleanup()
      level.value = 0
      interim.value = ''
      error.value = e?.message || '录音处理失败，请再试一次'
      return null
    } finally {
      state.value = 'idle'
    }
  }

  return { state, level, interim, error, elapsed, start, stop }
}
