<template>
  <span v-if="turn.pronPending" class="pill pill--info pron">发音评测中…</span>
  <span v-else-if="turn.pronScore != null" :class="['pill', 'pron', band]" :title="turn.pronNote">
    <AppIcon name="alert" :size="14" v-if="band !== 'good'" />发音 {{ Math.round(turn.pronScore) }}<template v-if="turn.pronNote"> · {{ turn.pronNote }}</template>
  </span>
  <button v-else-if="assessable && assess" type="button" class="btn btn--sm btn--ghost pron-btn" @click="assess(turn.id)">
    <AppIcon name="wave" :size="14" /> 评测发音
  </button>
</template>

<script lang="ts">
import { computed, defineComponent, inject, type PropType } from 'vue'
import AppIcon from './AppIcon.vue'
import type { Turn } from '../../api/models'
import { scoreBand } from '../../lib/format'

/**
 * Pronunciation score of a recording read from a script. Assessment is billed per call,
 * so it only runs when the learner taps 评测发音 (the practice page provides `assessPron`).
 */
export default defineComponent({
  name: 'PronBadge',
  components: { AppIcon },
  props: { turn: { type: Object as PropType<Turn>, required: true } },
  setup(props) {
    const assess = inject<((id: string) => void) | null>('assessPron', null)
    const canAssess = inject<{ value: boolean } | null>('canAssessPron', null)
    const assessable = computed(() => Boolean(canAssess?.value) && props.turn.input === 'voice' && props.turn.reference &&
      !props.turn.freeResponse && (props.turn.audioBlob || String(props.turn.audioUrl || '').startsWith('/api/')))
    const band = computed(() => scoreBand(props.turn.pronScore))
    return { assess, assessable, band }
  },
})
</script>
