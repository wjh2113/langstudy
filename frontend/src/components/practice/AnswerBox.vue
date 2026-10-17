<template>
  <div v-if="compact" class="answer answer--compact">
    <div class="answer-bar">
      <button type="button" :class="['rec-btn', 'rec-btn--sm', `is-${recState}`]" :disabled="recState === 'processing'"
        :aria-label="recState === 'recording' ? '停止录音' : '开始录音'" @click="toggleRecord">
        <AppIcon :name="recState === 'recording' ? 'stop' : 'mic'" :size="recState === 'recording' ? 16 : 20" />
      </button>
      <p class="answer-bar__text">
        <template v-if="recState === 'recording'">正在录音 {{ mmss(rec.elapsed.value) }}<span v-if="rec.interim.value" :class="['interim', env.textClass]">{{ rec.interim.value }}</span></template>
        <template v-else-if="recState === 'processing'">正在识别…</template>
        <span v-else-if="take" :class="env.textClass">{{ take.text || '没有识别到内容，再试一次' }}</span>
        <span v-else class="muted">{{ placeholder || '点击录音，开始你的朗读…' }}</span>
      </p>
      <button v-if="take && take.audioUrl" type="button" class="icon-btn" title="回放自己录音" @click="playback">
        <AppIcon :name="playingBack ? 'pause' : 'play-outline'" />
      </button>
      <button type="button" class="btn btn--primary" :disabled="!take || !take.text || recState !== 'idle'" @click="submitVoice">{{ submitLabel }}</button>
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
        <button type="button" :class="['rec-btn', `is-${recState}`]" :disabled="recState === 'processing'"
          :aria-label="recState === 'recording' ? '停止录音' : '开始录音'" @click="toggleRecord">
          <AppIcon :name="recState === 'recording' ? 'stop' : 'mic'" :size="recState === 'recording' ? 24 : 32" />
        </button>
      </div>
      <p class="mic__timer" :class="{ 'is-live': recState === 'recording' }">{{ mmss(recState === 'recording' ? rec.elapsed.value : take ? take.durationSec : 0) }}</p>
      <p class="mic__status">
        <template v-if="recState === 'recording'">{{ autoMode ? '正在听…说完停顿一下会自动提交' : '正在录音…说完点一下停止' }}</template>
        <template v-else-if="recState === 'processing'">正在识别…</template>
        <template v-else-if="!take">{{ placeholder || (handsFree ? '免手动：轮到你时会自动开始听' : '点击开始录音') }}</template>
        <template v-else>录好了，确认无误就提交</template>
      </p>

      <div v-if="recState === 'recording' && rec.interim.value" class="result-box">
        <p class="result-box__head"><AppIcon name="wave" :size="16" /> 实时识别</p>
        <p :class="env.textClass">{{ rec.interim.value }}</p>
      </div>
      <div v-if="take && recState === 'idle'" class="result-box">
        <p class="result-box__head"><AppIcon name="wave" :size="16" /> 识别结果</p>
        <p :class="['result-box__text', env.textClass]">
          <template v-if="take.text">{{ take.text }}</template>
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
        <button type="button" class="btn btn--primary" :disabled="!take.text" @click="submitVoice">{{ submitLabel }}</button>
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
import { useRecorder, type RecordingResult } from '../../lib/recorder'
import { stop as stopAudio } from '../../lib/audio'
import { mmss } from '../../lib/format'

export interface AnswerPayload {
  answer: string
  input: 'voice' | 'text'
  durationSec: number
  confidence: number | null
  audioUrl?: string | null
  audioBlob?: Blob | null
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
  },
  emits: ['submit'],
  setup(props, { emit }) {
    const tab = ref<'voice' | 'text'>('voice')
    const take = ref<RecordingResult | null>(null)
    const text = ref('')
    const textEl = ref<HTMLTextAreaElement | null>(null)
    const autoMode = ref(false) // this recording was started hands-free
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

    async function toggleRecord() {
      stopPlayback()
      if (rec.state.value === 'recording') {
        const result = await rec.stop()
        if (result) take.value = result
      } else if (rec.state.value === 'idle') {
        stopAudio()
        take.value = null
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
      take.value = result
      if (result.text) submitVoice() // no click needed; nothing heard: leave it for a retry
    }

    function submitVoice() {
      const t = take.value
      if (!t) return
      stopPlayback()
      emit('submit', { answer: t.text, input: 'voice', durationSec: t.durationSec, confidence: t.confidence, audioUrl: t.audioUrl, audioBlob: t.audioBlob } as AnswerPayload)
      take.value = null
    }

    function submitText() {
      if (!text.value.trim()) return
      emit('submit', { answer: text.value.trim(), input: 'text', durationSec: 0, confidence: null } as AnswerPayload)
      text.value = ''
    }

    return { tab, take, text, textEl, rec, recState, ring, autoMode, playingBack, mmss, playback, switchToText, toggleRecord, submitVoice, submitText }
  },
})
</script>
