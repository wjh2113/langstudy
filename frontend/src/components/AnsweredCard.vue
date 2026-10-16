<template>
  <div class="answered">
    <p :class="['answered__text', env.textClass]">{{ turn.answer }}</p>
    <div class="answered__meta">
      <span>{{ turn.input === 'voice' ? `语音 · ${turn.durationSec}s` : '文字' }}</span>
      <audio v-if="turn.audioUrl" :src="turn.audioUrl" controls preload="metadata" />
      <button v-if="redoable" class="link" @click="$emit('redo')"><AppIcon name="repeat" /> 重新回答</button>
    </div>
  </div>
</template>

<script>
import AppIcon from './AppIcon.vue'

export default {
  name: 'AnsweredCard',
  components: { AppIcon },
  props: {
    turn: { type: Object, required: true },
    env: { type: Object, required: true },
    redoable: { type: Boolean, default: false },
  },
  emits: ['redo'],
}
</script>
