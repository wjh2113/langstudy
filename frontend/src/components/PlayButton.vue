<template>
  <button :class="['play', `play--${size}`, { 'is-on': active }]" :aria-label="active ? '停止' : label || '播放'"
    :title="active ? '停止' : label || '播放'" @click="toggle">
    <AppIcon :name="active ? 'pause' : 'play'" />
    <span v-if="label">{{ active ? '停止' : label }}</span>
  </button>
</template>

<script>
import { computed } from 'vue'
import AppIcon from './AppIcon.vue'
import { play, playingId, stop } from '../audio'

/** Round play/stop button for one piece of text. Emits "play" each time playback starts. */
export default {
  name: 'PlayButton',
  components: { AppIcon },
  props: {
    id: { type: String, required: true },
    text: { type: String, required: true },
    env: { type: Object, required: true },
    voiceIndex: { type: Number, default: 0 },
    label: { type: String, default: '' },
    size: { type: String, default: 'md' },
  },
  emits: ['play'],
  setup(props, { emit }) {
    const active = computed(() => playingId.value === props.id)
    function toggle() {
      if (active.value) return stop()
      emit('play')
      play(props.id, props.text, { language: props.env.language, rate: props.env.rate, voiceIndex: props.voiceIndex }).catch(() => {})
    }
    return { active, toggle }
  },
}
</script>
