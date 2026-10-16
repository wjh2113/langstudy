<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <template v-if="name === 'mic'"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></template>
    <rect v-else-if="name === 'stop'" x="6" y="6" width="12" height="12" rx="2" fill="currentColor" />
    <path v-else-if="name === 'play'" d="M7 4.5v15l12-7.5z" fill="currentColor" stroke="none" />
    <path v-else-if="name === 'pause'" d="M8 5v14M16 5v14" stroke-width="3" />
    <template v-else-if="name === 'eye'"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></template>
    <path v-else-if="name === 'repeat'" d="M4 12a8 8 0 0 1 13.7-5.7L20 8.5M20 4v4.5h-4.5M20 12a8 8 0 0 1-13.7 5.7L4 15.5M4 20v-4.5h4.5" />
  </svg>
</template>

<script>
export default {
  name: 'AppIcon',
  props: {
    name: { type: String, required: true },
    size: { type: Number, default: 16 },
  },
}
</script>
