<template>
  <div class="answered">
    <p :class="['answered__text', env.textClass]">{{ turn.answer }}</p>
    <div class="answered__meta">
      <span class="muted">{{ turn.input === 'voice' ? `语音 · ${turn.durationSec}s` : '文字' }}</span>
      <audio v-if="turn.audioUrl" :src="turn.audioUrl" controls preload="none" />
      <button v-if="redoable" type="button" class="link" @click="$emit('redo')"><AppIcon name="repeat" :size="14" /> 重新回答</button>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, type PropType } from 'vue'
import AppIcon from '../ui/AppIcon.vue'
import type { Env, Turn } from '../../api/models'

export default defineComponent({
  name: 'AnsweredCard',
  components: { AppIcon },
  props: {
    turn: { type: Object as PropType<Turn>, required: true },
    env: { type: Object as PropType<Env>, required: true },
    redoable: { type: Boolean, default: false },
  },
  emits: ['redo'],
})
</script>
