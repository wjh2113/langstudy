<template>
  <span v-if="turn.pronPending" class="pill pron pron--wait">发音评测中…</span>
  <span v-else-if="turn.pronScore != null" :class="['pill', 'pron', grade]" :title="turn.pronNote">
    发音 {{ Math.round(turn.pronScore) }}<template v-if="turn.pronNote"> · {{ turn.pronNote }}</template>
  </span>
</template>

<script>
import { computed } from 'vue'

/** Gateway pronunciation score for a recording read from a script. */
export default {
  name: 'PronBadge',
  props: { turn: { type: Object, required: true } },
  setup(props) {
    const grade = computed(() => {
      const s = props.turn.pronScore
      return s >= 85 ? 'good' : s >= 70 ? 'mid' : 'low'
    })
    return { grade }
  },
}
</script>
