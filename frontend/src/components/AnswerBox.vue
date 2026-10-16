<template>
  <div :class="['answer', { 'answer--compact': compact }]">
    <div v-if="!compact" class="answer__tabs" role="tablist">
      <button role="tab" :aria-selected="tab === 'voice'" :class="{ on: tab === 'voice' }" @click="tab = 'voice'">说</button>
      <button role="tab" :aria-selected="tab === 'text'" :class="{ on: tab === 'text' }" :disabled="rec.state.value !== 'idle'"
        @click="switchToText">写</button>
    </div>

    <div v-if="tab === 'voice'" class="answer__voice">
      <div class="mic">
        <span class="mic__ring" :style="{ transform: `scale(${ring})` }" aria-hidden="true" />
        <button :class="['mic__btn', { 'is-rec': rec.state.value === 'recording' }]" :disabled="rec.state.value === 'processing'"
          :aria-label="rec.state.value === 'recording' ? '停止录音' : '开始录音'" @click="toggleRecord">
          <AppIcon :name="rec.state.value === 'recording' ? 'stop' : 'mic'" :size="rec.state.value === 'recording' ? 22 : 26" />
        </button>
      </div>
      <div class="answer__live">
        <p v-if="rec.state.value === 'recording'" class="hint">
          {{ autoMode ? '正在听…说完停顿一下会自动提交' : '正在听…说完点一下停止' }}<span v-if="rec.interim.value" class="interim">{{ rec.interim.value }}</span>
        </p>
        <p v-else-if="rec.state.value === 'processing'" class="hint">正在识别…</p>
        <p v-else-if="!take" class="hint">
          {{ placeholder || (handsFree ? '免手动：轮到你时会自动开始听，说完停顿一下就提交' : '点麦克风开始说，说完再点一下') }}
        </p>
        <div v-if="take && rec.state.value === 'idle'" class="take">
          <p :class="['take__text', env.textClass]">
            <template v-if="take.text">{{ take.text }}</template>
            <em v-else class="muted">没有识别到内容，再试一次</em>
          </p>
          <audio v-if="take.audioUrl" class="take__audio" :src="take.audioUrl" controls preload="metadata" />
          <div class="take__actions">
            <button class="btn btn--ghost" @click="toggleRecord">重录</button>
            <button class="btn btn--primary" :disabled="!take.text" @click="submitVoice">{{ submitLabel }}</button>
          </div>
        </div>
        <p v-if="rec.error.value" class="error">{{ rec.error.value }}</p>
      </div>
    </div>

    <div v-else class="answer__text">
      <textarea ref="textEl" v-model="text" :class="env.textClass" rows="3"
        placeholder="用目标语言输入你的回答（Ctrl/⌘ + Enter 提交）"
        @keydown.ctrl.enter="submitText" @keydown.meta.enter="submitText" />
      <div class="take__actions">
        <button class="btn btn--primary" :disabled="!text.trim()" @click="submitText">{{ submitLabel }}</button>
      </div>
    </div>
  </div>
</template>

<script>
import { computed, nextTick, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import { useRecorder } from '../useRecorder'
import { stop as stopAudio } from '../audio'

/**
 * Voice or text answer input.
 * Emits submit({ answer, input: 'voice'|'text', durationSec, confidence, audioUrl })
 */
export default {
  name: 'AnswerBox',
  components: { AppIcon },
  props: {
    env: { type: Object, required: true },
    compact: { type: Boolean, default: false },
    submitLabel: { type: String, default: '提交回答' },
    placeholder: { type: String, default: '' },
    handsFree: { type: Boolean, default: false }, // start on listenSignal, submit after a pause
    listenSignal: { type: Number, default: 0 }, // parent bumps this when it's the learner's turn
  },
  emits: ['submit'],
  setup(props, { emit }) {
    const tab = ref('voice')
    const take = ref(null)
    const text = ref('')
    const textEl = ref(null)
    const autoMode = ref(false) // this recording was started hands-free
    const rec = useRecorder(() => props.env, { onAutoStop: () => finishAuto() })
    const ring = computed(() => (rec.state.value === 'recording' ? 1 + rec.level.value * 0.55 : 1))

    async function switchToText() {
      tab.value = 'text'
      await nextTick()
      textEl.value?.focus()
    }

    async function toggleRecord() {
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
      if (result.text) {
        take.value = result
        submitVoice() // no click needed
      } else {
        take.value = result // nothing heard: leave it for the learner to retry
      }
    }

    function submitVoice() {
      const t = take.value
      emit('submit', { answer: t.text, input: 'voice', durationSec: t.durationSec, confidence: t.confidence, audioUrl: t.audioUrl, audioBlob: t.audioBlob })
      take.value = null
    }

    function submitText() {
      if (!text.value.trim()) return
      emit('submit', { answer: text.value.trim(), input: 'text', durationSec: 0, confidence: null })
      text.value = ''
    }

    return { tab, take, text, textEl, rec, ring, autoMode, switchToText, toggleRecord, submitVoice, submitText }
  },
}
</script>
