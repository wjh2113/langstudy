<template>
  <p :class="['diff', env.textClass]">
    <span v-for="(t, i) in tokens" :key="i" :class="{ miss: !t.ok }">{{ t.t }}{{ env.language === 'ja' ? '' : ' ' }}</span>
  </p>
</template>

<script lang="ts">
import { defineComponent, type PropType } from 'vue'
import type { DiffToken, Env } from '../../api/models'

/** Reference text with the parts that weren't heard underlined in red. */
export default defineComponent({
  name: 'DiffText',
  props: {
    tokens: { type: Array as PropType<DiffToken[]>, required: true },
    env: { type: Object as PropType<Env>, required: true },
  },
})
</script>
