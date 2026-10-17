<template>
  <button type="button" :class="['star', { 'is-on': on }]" :disabled="busy || readonly" :title="on ? '已在' + deckName : '加入' + deckName"
    :aria-label="on ? '已在' + deckName : '加入' + deckName" @click="save">
    <AppIcon :name="on ? 'star-fill' : 'star'" :size="16" />
    <span v-if="label">{{ on ? '已加入' : label }}</span>
  </button>
</template>

<script lang="ts">
import { computed, defineComponent, onMounted, ref, type PropType } from 'vue'
import AppIcon from './AppIcon.vue'
import type { Card } from '../../api/models'
import { isSaved, loadSaved, saveCard } from '../../lib/cards'

type CardBody = Partial<Card> & { language: string; kind: string; front: string }

/** Save a word / pattern / sentence into the review deck. `card` is the POST /api/cards body. */
export default defineComponent({
  name: 'StarButton',
  components: { AppIcon },
  props: {
    card: { type: Object as PropType<CardBody>, required: true },
    label: { type: String, default: '' },
    readonly: { type: Boolean, default: false },
  },
  setup(props) {
    const busy = ref(false)
    const on = computed(() => isSaved(props.card.language, props.card.kind, props.card.front))
    const deckName = computed(() => (props.card.kind === 'sentence' ? '错句本' : '生词本'))
    onMounted(() => { if (!props.readonly) loadSaved(props.card.language) })
    async function save() {
      if (on.value) return
      busy.value = true
      try {
        await saveCard(props.card)
      } finally {
        busy.value = false
      }
    }
    return { busy, on, deckName, save }
  },
})
</script>
