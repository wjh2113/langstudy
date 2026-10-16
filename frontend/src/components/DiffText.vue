<template>
  <p :class="['diff', env.textClass]">
    <span v-for="(t, i) in tokens" :key="i" :class="{ miss: !t.ok }">{{ t.t }}{{ env.language === 'ja' ? '' : ' ' }}</span>
  </p>
</template>

<script>
/** Reference text with the parts that weren't heard underlined. */
export default {
  name: 'DiffText',
  props: {
    tokens: { type: Array, required: true },
    env: { type: Object, required: true },
  },
}
</script>
