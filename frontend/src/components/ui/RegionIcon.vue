<template>
  <span class="region-icon" aria-hidden="true">
    <svg viewBox="0 0 32 32" width="22" height="22">
      <path v-if="region === '美洲'" d="M9 6c3-1 6 0 7 2s-1 3-2 4 0 3 2 4 2 3 1 5-2 4-3 5c0-2 0-4-2-5s-2-3-3-5-3-3-2-6 0-3 2-4z" />
      <path v-else-if="region === '欧洲'" d="M10 8c2-2 6-2 8 0 1 1 3 1 4 2s0 3-1 4-3 1-3 3 2 2 1 4-4 2-5 0-1-3-3-4-3-3-2-5 0-3 1-4z" />
      <path v-else-if="region === '亚洲' || region === '日本'" d="M6 12c2-3 6-4 10-3s6-1 9 1 2 4 0 5-3 1-3 3-2 3-4 2-2-2-4-2-4 1-5-1-2-3 1-5z" />
      <path v-else-if="region === '大洋洲'" d="M8 15c2-3 5-4 8-3s5 0 7 2 1 5-2 6-5 1-7 0-4 1-5-1-2-2-1-4z" />
      <g v-else><circle cx="16" cy="16" r="9" fill="none" stroke-width="2" /><path d="M7 16h18M16 7c3 3 3 15 0 18M16 7c-3 3-3 15 0 18" fill="none" stroke-width="1.6" /></g>
    </svg>
  </span>
</template>

<script lang="ts">
import { defineComponent } from 'vue'

/** Simplified continent silhouette for an accent region. */
export default defineComponent({ name: 'RegionIcon', props: { region: { type: String, default: '' } } })
</script>
