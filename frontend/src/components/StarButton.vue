<template>
  <button :class="['star', { 'is-on': on }]" :disabled="busy" :title="on ? '已在' + deckName : '加入' + deckName"
    :aria-label="on ? '已在' + deckName : '加入' + deckName" @click="save">
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.8-5.2-2.8-5.2 2.8 1-5.8-4.3-4.1 5.9-.8z"
        :fill="on ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
    </svg>
    <span v-if="label">{{ on ? '已加入' : label }}</span>
  </button>
</template>

<script>
import { computed, onMounted, ref } from 'vue'
import { isSaved, loadSaved, saveCard } from '../cards'

/** Save a word / pattern / sentence into the review deck. `card` is the POST /api/cards body. */
export default {
  name: 'StarButton',
  props: {
    card: { type: Object, required: true },
    label: { type: String, default: '' },
  },
  setup(props) {
    const busy = ref(false)
    const on = computed(() => isSaved(props.card.language, props.card.kind, props.card.front))
    const deckName = computed(() => (props.card.kind === 'sentence' ? '错句本' : '生词本'))
    onMounted(() => loadSaved(props.card.language))

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
}
</script>
