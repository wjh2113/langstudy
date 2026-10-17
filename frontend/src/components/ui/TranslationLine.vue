<template>
  <p v-if="text" class="translation" :aria-busy="loading">
    <template v-if="value">{{ value }}</template>
    <span v-else-if="loading" class="muted">翻译中…</span>
    <span v-else-if="error" class="muted">翻译失败 <button type="button" class="link" @click="load">重试</button></span>
  </p>
</template>

<script lang="ts">
import { defineComponent, onMounted, ref, watch } from 'vue'
import { cachedTranslation, translate } from '../../lib/translate'

/** Chinese translation of one sentence, fetched the first time it is shown (see lib/translate). */
export default defineComponent({
  name: 'TranslationLine',
  props: {
    text: { type: String, required: true },
    language: { type: String, required: true },
    given: { type: String, default: '' }, // translation already at hand (e.g. study notes)
  },
  setup(props) {
    const value = ref(props.given || cachedTranslation(props.text, props.language) || '')
    const loading = ref(false)
    const error = ref(false)
    async function load() {
      if (props.given) return (value.value = props.given)
      error.value = false
      loading.value = true
      try {
        value.value = await translate(props.text, props.language)
      } catch {
        error.value = true
      } finally {
        loading.value = false
      }
    }
    onMounted(() => { if (!value.value) load() })
    watch(() => props.text, () => { value.value = ''; load() })
    return { value, loading, error, load }
  },
})
</script>
