<template>
  <svg :width="size" :height="size" viewBox="0 0 100 100" :class="['ring', band]" role="img" :aria-label="`${value ?? '—'} 分`">
    <circle cx="50" cy="50" :r="r" class="ring__track" />
    <circle cx="50" cy="50" :r="r" class="ring__value" :stroke-dasharray="`${dash} ${circ}`" transform="rotate(-90 50 50)" />
    <text x="50" y="50" dominant-baseline="central" text-anchor="middle" class="ring__text">{{ label ?? value ?? '—' }}</text>
  </svg>
</template>

<script lang="ts">
import { computed, defineComponent, type PropType } from 'vue'
import { scoreBand } from '../../lib/format'

/** Circular progress / score. Colour follows the score bands unless `tone` is given. */
export default defineComponent({
  name: 'ScoreRing',
  props: {
    value: { type: Number as PropType<number | null>, default: null },
    max: { type: Number, default: 100 },
    size: { type: Number, default: 64 },
    label: { type: String as PropType<string | null>, default: null },
    tone: { type: String, default: '' },
  },
  setup(props) {
    const r = 42
    const circ = 2 * Math.PI * r
    const dash = computed(() => (Math.max(0, Math.min(props.value ?? 0, props.max)) / props.max) * circ)
    const band = computed(() => props.tone || scoreBand(props.value))
    return { r, circ, dash, band }
  },
})
</script>
