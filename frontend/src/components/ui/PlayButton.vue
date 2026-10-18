<template>
  <button type="button" :class="['play', `play--${size}`, { 'play--label': label, 'is-on': active }]"
    :aria-label="active ? '停止' : label || '播放'" :title="active ? '停止' : label || '播放'"
    @pointerdown="warm" @click="toggle">
    <AppIcon :name="active ? 'pause' : 'play'" :size="size === 'lg' ? 20 : size === 'sm' ? 13 : 16" />
    <span v-if="label">{{ active ? '停止' : label }}</span>
  </button>
</template>

<script lang="ts">
import { computed, defineComponent, type PropType } from 'vue'
import AppIcon from './AppIcon.vue'
import type { Env } from '../../api/models'
import { play, playingId, prefetch, stop } from '../../lib/audio'

/** Round play/stop button for one piece of text (or an outlined pill when it has a label). Emits "play" on each start. */
export default defineComponent({
  name: 'PlayButton',
  components: { AppIcon },
  props: {
    id: { type: String, required: true },
    text: { type: String, required: true },
    env: { type: Object as PropType<Env>, required: true },
    voiceIndex: { type: Number },
    label: { type: String, default: '' },
    size: { type: String, default: 'md' }, // sm | md | lg
  },
  emits: ['play'],
  setup(props, { emit }) {
    const active = computed(() => playingId.value === props.id)
    function playOpts() {
      return {
        language: props.env.language, rate: props.env.rate,
        ...(props.voiceIndex === undefined ? {} : { voiceIndex: props.voiceIndex }),
        accent: props.env.accent || 'default', locale: props.env.accentLocale || null,
      }
    }
    function warm() {
      if (active.value) return
      prefetch(props.text, playOpts())
    }
    function toggle() {
      if (active.value) return stop()
      emit('play')
      play(props.id, props.text, playOpts()).catch(() => {})
    }
    return { active, warm, toggle }
  },
})
</script>
