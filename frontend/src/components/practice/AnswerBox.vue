<template>
  <div v-if="compact" class="answer answer--compact">
    <div class="answer-bar">
      <button type="button" :class="['rec-btn', 'rec-btn--sm', `is-${recState}`]" :disabled="recState === 'processing' || submitting"
        :aria-label="recState === 'recording' ? '停止录音' : '开始录音'" @click="toggleRecord">
        <AppIcon :name="recState === 'recording' ? 'stop' : 'mic'" :size="recState === 'recording' ? 16 : 20" />
      </button>
      <p class="answer-bar__text">
        <template v-if="recState === 'recording'">正在录音 {{ mmss(rec.elapsed.value) }}<span v-if="rec.interim.value" :class="['interim', env.textClass]">{{ rec.interim.value }}</span></template>
        <template v-else-if="recState === 'processing'">
          <span v-if="rec.interim.value" :class="env.textClass">{{ rec.interim.value }}</span>
          <template v-else>正在识别…</template>
        </template>
        <span v-else-if="take" :class="env.textClass">{{ take.text || '没有识别到内容，再试一次' }}<span v-if="refining" class="muted"> · 校对中</span></span>
        <span v-else class="muted">{{ placeholder || '点击录音，开始你的朗读…' }}</span>
      </p>
      <button v-if="take && take.audioUrl" type="button" class="icon-btn" title="回放自己录音" @click="playback">
        <AppIcon :name="playingBack ? 'pause' : 'play-outline'" />
      </button>
      <button type="button" class="btn btn--primary" :disabled="!take || !take.text || recState !== 'idle' || submitting" @click="submitVoice">{{ submitLabel }}</button>
    </div>
    <p v-if="rec.error.value" class="error">{{ rec.error.value }}</p>
  </div>

  <div v-else class="answer">
    <div class="answer__tabs seg seg--pill" role="tablist">
      <button type="button" role="tab" :aria-selected="tab === 'voice'" :class="{ on: tab === 'voice' }" @click="tab = 'voice'">
        <AppIcon name="mic" :size="16" /> 说
      </button>
      <button type="button" role="tab" :aria-selected="tab === 'text'" :class="{ on: tab === 'text' }" :disabled="recState !== 'idle'"
        @click="switchToText"><AppIcon name="pen" :size="16" /> 写</button>
    </div>

    <div v-if="tab === 'voice'" class="answer__voice">
      <div class="mic">
        <span class="mic__ring" :style="{ transform: `scale(${ring})` }" aria-hidden="true" />
        <button type="button" :class="['rec-btn', `is-${recState}`]" :disabled="recState === 'processing' || submitting"
          :aria-label="recState === 'recording' ? '停止录音' : '开始录音'" @click="toggleRecord">
          <AppIcon :name="recState === 'recording' ? 'stop' : 'mic'" :size="recState === 'recording' ? 24 : 32" />
        </button>
      </div>
      <p class="mic__timer" :class="{ 'is-live': recState === 'recording' }">{{ mmss(recState === 'recording' || recState === 'processing' ? rec.elapsed.value : take ? take.durationSec : 0) }}</p>
      <p class="mic__status">
        <template v-if="recState === 'recording'">{{ autoMode ? '正在听…说完停顿一下会自动提交' : '正在录音…说完点一下停止' }}</template>
        <template v-else-if="recState === 'processing'">{{ rec.interim.value ? '正在整理录音…' : '正在识别…请稍候' }}</template>
        <template v-else-if="!take">{{ placeholder || (handsFree ? '免手动：轮到你时会自动开始听' : '点击开始录音') }}</template>
        <template v-else>录好了，确认无误就提交</template>
      </p>

      <div v-if="(recState === 'recording' || recState === 'processing') && rec.interim.value" class="result-box">
        <p class="result-box__head"><AppIcon name="wave" :size="16" /> 实时识别</p>
        <p :class="env.textClass">{{ rec.interim.value }}</p>
      </div>
      <div v-if="take && recState === 'idle'" class="result-box">
        <p class="result-box__head"><AppIcon name="wave" :size="16" /> 识别结果</p>
        <p :class="['result-box__text', env.textClass]">
          <template v-if="take.text">{{ take.text }}<span v-if="refining" class="muted"> · 校对中</span></template>
          <em v-else class="muted">没有识别到内容，再试一次</em>
        </p>
        <TranslationLine v-if="take.text && env.showTranslation" :text="take.text" :language="env.language" />
      </div>
      <p v-if="rec.error.value" class="error">{{ rec.error.value }}</p>

      <div v-if="take && recState === 'idle'" class="answer__actions">
        <button type="button" class="btn btn--ghost" :disabled="!take.audioUrl" @click="playback">
          <AppIcon :name="playingBack ? 'pause' : 'play-outline'" :size="16" /> {{ playingBack ? '停止回放' : '回放自己录音' }}
        </button>
        <button type="button" class="btn btn--ghost" @click="toggleRecord"><AppIcon name="rotate" :size="16" /> 重录</button>
        <button type="button" class="btn btn--primary" :disabled="!take.text || submitting" @click="submitVoice">{{ submitLabel }}</button>
      </div>
    </div>

    <div v-else class="answer__text">
      <textarea ref="textEl" v-model="text" :class="env.textClass" rows="4"
        placeholder="用目标语言输入你的回答（Ctrl/⌘ + Enter 提交）"
        @keydown.ctrl.enter="submitText" @keydown.meta.enter="submitText" />
      <div class="answer__actions answer__actions--end">
        <button type="button" class="btn btn--primary" :disabled="!text.trim()" @click="submitText">{{ submitLabel }}</button>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, nextTick, onBeforeUnmount, ref, watch, type PropType } from 'vue'
import AppIcon from '../ui/AppIcon.vue'
import TranslationLine from '../ui/TranslationLine.vue'
import type { Env } from '../../api/models'
import { takeServerJob, useRecorder, type RecordingResult } from '../../lib/recorder'
import { stop as stopAudio } from '../../lib/audio'
import { mmss } from '../../lib/format'

export interface AnswerPayload {
  answer: string
  input: 'voice' | 'text'
  durationSec: number
  confidence: number | null
  audioUrl?: string | null
  audioBlob?: Blob | null
  /** 服务端识别还在后台跑时带上；调用方在已保存后用来替换成权威文本。不要放进响应式对象长期保存。 */
  serverText?: Promise<string | null> | null
}

/** Voice or text answer input. Emits submit(AnswerPayload). */
export default defineComponent({
  name: 'AnswerBox',
  components: { AppIcon, TranslationLine },
  props: {
    env: { type: Object as PropType<Env>, required: true },
    compact: { type: Boolean, default: false },
    submitLabel: { type: String, default: '提交' },
    placeholder: { type: String, default: '' },
    handsFree: { type: Boolean, default: false }, // start on listenSignal, submit after a pause
    listenSignal: { type: Number, default: 0 }, // parent bumps this when it's the learner's turn
    // 追问、自由对话会立刻把文本发给模型，提交前要等服务端校对。跟读只在本地比对，可以先交浏览器稿。
    awaitServer: { type: Boolean, default: false },
  },
  emits: ['submit'],
  setup(props, { emit }) {
    const tab = ref<'voice' | 'text'>('voice')
    const take = ref<RecordingResult | null>(null)
    const text = ref('')
    const textEl = ref<HTMLTextAreaElement | null>(null)
    const autoMode = ref(false) // this recording was started hands-free
    const refining = ref(false) // 浏览器稿已显示，服务端识别还在后台
    const submitting = ref(false)
    // Promise 不放进 take（响应式），单独拿着，避免 Vue 代理把 then 弄坏
    let pendingJob: Promise<string | null> | null = null
    let pendingId = 0
    const rec = useRecorder(() => props.env, { onAutoStop: () => finishAuto() })
    const recState = computed(() => rec.state.value)
    const ring = computed(() => (rec.state.value === 'recording' ? 1 + rec.level.value * 0.5 : 1))
    const playingBack = ref(false)
    let player: HTMLAudioElement | null = null

    function stopPlayback() {
      player?.pause()
      player = null
      playingBack.value = false
    }
    onBeforeUnmount(stopPlayback)

    function playback() {
      if (playingBack.value) return stopPlayback()
      if (!take.value?.audioUrl) return
      stopAudio()
      player = new Audio(take.value.audioUrl)
      playingBack.value = true
      player.onended = player.onpause = () => (playingBack.value = false)
      player.play().catch(() => (playingBack.value = false))
    }

    async function switchToText() {
      tab.value = 'text'
      await nextTick()
      textEl.value?.focus()
    }

    function arm(result: RecordingResult) {
      take.value = result
      const job = takeServerJob(result.startedAt)
      pendingJob = job
      pendingId = result.startedAt
      if (!job) {
        refining.value = false
        return
      }
      refining.value = true
      const id = result.startedAt
      job.then((text) => {
        if (take.value?.startedAt !== id) return
        refining.value = false
        if (text && text !== take.value.text) take.value = { ...take.value, text, confidence: null }
        if (pendingId === id) pendingJob = null
      }).catch(() => {
        if (take.value?.startedAt === id) refining.value = false
        if (pendingId === id) pendingJob = null
      })
    }

    async function toggleRecord() {
      if (submitting.value) return
      stopPlayback()
      if (rec.state.value === 'recording') {
        const result = await rec.stop()
        if (result) arm(result)
      } else if (rec.state.value === 'idle') {
        stopAudio()
        take.value = null
        pendingJob = null
        refining.value = false
        autoMode.value = false
        await rec.start()
      }
    }

    // hands-free: the parent signals "your turn" (usually right after the AI finishes speaking)
    watch(() => props.listenSignal, async () => {
      if (!props.handsFree || tab.value !== 'voice' || rec.state.value !== 'idle' || take.value) return
      autoMode.value = true
      await rec.start({ autoStop: true })
    })

    async function finishAuto() {
      if (rec.state.value !== 'recording') return
      const result = await rec.stop()
      if (!result) return
      arm(result)
      if (result.text) await submitVoice() // 没听到就留在框里重试；有浏览器稿时先显示，需要权威文本的模式会在提交里等网关
    }

    async function submitVoice() {
      if (submitting.value) return
      const started = take.value?.startedAt
      if (!take.value?.text || started == null) return
      submitting.value = true
      try {
        let pending = pendingId === started ? pendingJob : null
        if (props.awaitServer && pending) {
          const server = await pending
          pending = null
          if (server && take.value?.startedAt === started) take.value = { ...take.value, text: server, confidence: null }
        }
        const cur = take.value
        if (!cur || cur.startedAt !== started || !cur.text) return
        stopPlayback()
        emit('submit', {
          answer: cur.text, input: 'voice', durationSec: cur.durationSec, confidence: cur.confidence,
          audioUrl: cur.audioUrl, audioBlob: cur.audioBlob, serverText: pending,
        } as AnswerPayload)
        pendingJob = null
        refining.value = false
        take.value = null
      } finally {
        submitting.value = false
      }
    }

    function submitText() {
      if (!text.value.trim()) return
      emit('submit', { answer: text.value.trim(), input: 'text', durationSec: 0, confidence: null } as AnswerPayload)
      text.value = ''
    }

    return { tab, take, text, textEl, rec, recState, ring, autoMode, refining, submitting, playingBack, mmss, playback, switchToText, toggleRecord, submitVoice, submitText }
  },
})
</script>
