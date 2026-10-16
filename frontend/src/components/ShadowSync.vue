<template>
  <span class="shadow-sync">
    <button class="link" :disabled="busy" @click="run">
      {{ phase === 'idle' ? '影子跟读' : phase === 'playing' ? '跟着原音一起读…' : '正在分析…' }}
    </button>
    <span v-if="error" class="error">{{ error }}</span>
  </span>
</template>

<script>
import { computed, ref } from 'vue'
import { useRecorder } from '../useRecorder'
import { play, stop } from '../audio'
import { diffReference } from '../diff'

/**
 * Shadowing: the original plays while the learner speaks along (headphones recommended).
 * Emits "result" with a shadow turn that also carries the timing: how late the learner
 * started (lagSec) and how long they took relative to the original (durationRatio).
 */
export default {
  name: 'ShadowSync',
  props: {
    id: { type: String, required: true },
    text: { type: String, required: true },
    env: { type: Object, required: true },
  },
  emits: ['result', 'play'],
  setup(props, { emit }) {
    const phase = ref('idle') // idle | playing | analysing
    const error = ref('')
    const rec = useRecorder(() => props.env)
    const busy = computed(() => phase.value !== 'idle')

    async function run() {
      error.value = ''
      stop()
      if (!(await rec.start())) {
        error.value = rec.error.value
        return
      }
      phase.value = 'playing'
      let playStart = null
      emit('play')
      await play(`${props.id}-sync`, props.text, {
        language: props.env.language, rate: props.env.rate, onStart: () => (playStart = performance.now()),
      }).catch(() => {})
      const playEnd = performance.now()
      await new Promise((r) => setTimeout(r, 900)) // let the learner finish the last word
      phase.value = 'analysing'
      const result = await rec.stop()
      phase.value = 'idle'
      if (!result || !result.text) {
        error.value = rec.error.value || '没有听到你的声音，戴上耳机再试一次'
        return
      }
      const refDur = playStart ? (playEnd - playStart) / 1000 : null
      const lagSec = playStart && result.voiceStartAt ? Math.round(((result.voiceStartAt - playStart) / 1000) * 10) / 10 : null
      emit('result', {
        id: `shadow-${props.id}`, kind: 'shadow', shadowSync: true, reference: props.text,
        answer: result.text, input: 'voice', durationSec: result.durationSec, confidence: result.confidence,
        audioUrl: result.audioUrl, audioBlob: result.audioBlob,
        lagSec, durationRatio: refDur ? Math.round((result.durationSec / refDur) * 100) / 100 : null,
        diff: diffReference(props.text, result.text, props.env.language),
      })
    }

    return { phase, error, busy, run }
  },
}
</script>
