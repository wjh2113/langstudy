<template>
  <svg v-if="lang === 'ja'" :width="size" :height="size" viewBox="0 0 32 32" class="flag" aria-hidden="true">
    <circle cx="16" cy="16" r="15" fill="#fff" stroke="#E8E6E1" />
    <circle cx="16" cy="16" r="6.5" fill="#D7263D" />
  </svg>
  <svg v-else :width="size" :height="size" viewBox="0 0 32 32" class="flag" aria-hidden="true">
    <defs><clipPath :id="clip"><circle cx="16" cy="16" r="15" /></clipPath></defs>
    <g :clip-path="`url(#${clip})`">
      <rect width="32" height="32" fill="#fff" />
      <path v-for="i in 7" :key="i" :d="`M0 ${(i - 1) * 4.6}h32v2.3H0z`" fill="#D7263D" />
      <rect width="15" height="16" fill="#3C3B8E" />
      <g fill="#fff"><circle v-for="d in dots" :key="d.join()" :cx="d[0]" :cy="d[1]" r=".9" /></g>
    </g>
    <circle cx="16" cy="16" r="15" fill="none" stroke="#E8E6E1" />
  </svg>
</template>

<script lang="ts">
import { defineComponent } from 'vue'

let n = 0
/** Round flag for a target language (English → US, 日本語 → Japan). */
export default defineComponent({
  name: 'FlagIcon',
  props: { lang: { type: String, required: true }, size: { type: Number, default: 32 } },
  setup() {
    const dots: number[][] = []
    for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) dots.push([2.5 + c * 3.4 + (r % 2) * 1.7, 2.5 + r * 3.5])
    return { clip: `flag-clip-${++n}`, dots }
  },
})
</script>
