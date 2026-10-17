<template>
  <span :class="['figure', `figure--${variant}`]" :style="{ width: `${size}px`, height: `${size}px` }" aria-hidden="true">
    <svg viewBox="0 0 64 64">
      <circle cx="32" cy="32" r="32" class="figure__bg" />
      <path d="M12 60c2-12 10-17 20-17s18 5 20 17" class="figure__body" />
      <path v-if="variant === 'b'" d="M26 43l6 9 6-9" class="figure__shirt" />
      <path v-else d="M28 43l4 12 4-12" class="figure__tie" />
      <circle cx="32" cy="28" r="11" class="figure__face" />
      <path v-if="variant === 'b'" d="M20 31c-1-12 6-17 12-17s13 5 12 17c-2-6-5-9-12-9s-10 3-12 9zM20 31c0 6 1 11 3 13M44 31c0 6-1 11-3 13" class="figure__hair" />
      <path v-else d="M21 26c0-8 5-12 11-12s11 4 11 12c-3-4-7-5-11-5s-8 1-11 5z" class="figure__hair" />
    </svg>
  </span>
</template>

<script lang="ts">
import { defineComponent } from 'vue'

/** Simple flat avatar for dialogue roles (variant a / b, and "me"). */
export default defineComponent({
  name: 'AvatarFigure',
  props: { variant: { type: String, default: 'a' }, size: { type: Number, default: 48 } },
})
</script>
