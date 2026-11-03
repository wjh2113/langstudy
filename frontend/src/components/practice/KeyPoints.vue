<template>
  <section class="keypoints" aria-label="重点单词和重点句型">
    <p v-if="loading" class="hint">正在读取重点单词和句型…</p>
    <div v-else-if="busy" class="card notes__busy" role="status">
      <span class="spinner" aria-hidden="true" />正在整理重点单词和句型… {{ waited }} 秒
    </div>
    <div v-else-if="!hasNotes" class="card keypoints__empty">
      <p>这个练习还没有重点单词和重点句型。整理后会保存在学习笔记里，练习时可以直接看。</p>
      <button v-if="!locked" type="button" class="btn btn--primary btn--sm" @click="generate">
        <AppIcon name="sparkle" :size="16" /> 整理重点
      </button>
    </div>

    <template v-else>
      <section class="card keypoints__block">
        <header class="keypoints__head">
          <h2><AppIcon name="book" :size="16" /> 重点单词</h2>
          <button type="button" class="link" :aria-expanded="wordsOpen" @click="wordsOpen = !wordsOpen">{{ wordsOpen ? '收起' : '展开' }}</button>
        </header>
        <p v-if="!vocab.length" class="hint">还没有重点单词，可以到「学习笔记」里重新整理。</p>
        <div v-show="wordsOpen && vocab.length" class="keypoints__grid">
          <article v-for="(v, i) in vocab" :key="i" class="kp-word">
            <div class="kp-word__top">
              <strong :class="['kp-word__term', env.textClass]">{{ v.word }}</strong>
              <PlayButton :id="`kw-${uid}-${i}`" :text="v.word" :env="env" size="sm" />
              <StarButton v-if="!locked" :card="{ language: env.language, kind: 'word', front: v.word, reading: v.reading,
                meaning: v.meaning, example: v.example, exampleTranslation: v.exampleTranslation, sourceSession: sessionId }" />
            </div>
            <p class="kp-word__meta">
              <span v-if="v.reading">{{ v.reading }}</span>
              <span v-if="v.pos" class="tag tag--soft">{{ v.pos }}</span>
            </p>
            <p class="kp-word__meaning">{{ v.meaning }}</p>
            <p v-if="v.example" class="kp-ex" :class="env.textClass">{{ v.example }}
              <PlayButton :id="`ke-${uid}-${i}`" :text="v.example" :env="env" size="sm" />
            </p>
            <p v-if="v.exampleTranslation" class="translation">{{ v.exampleTranslation }}</p>
          </article>
        </div>
      </section>

      <section class="card keypoints__block">
        <header class="keypoints__head">
          <h2><AppIcon name="chat-dots" :size="16" /> 重点句型</h2>
          <button type="button" class="link" :aria-expanded="patternsOpen" @click="patternsOpen = !patternsOpen">{{ patternsOpen ? '收起' : '展开' }}</button>
        </header>
        <p v-if="!patterns.length" class="hint">还没有重点句型，可以到「学习笔记」里重新整理。</p>
        <div v-show="patternsOpen && patterns.length" class="keypoints__grid">
          <article v-for="(p, i) in patterns" :key="i" class="kp-pattern">
            <div class="kp-pattern__top">
              <strong :class="['kp-pattern__term', env.textClass]">{{ p.pattern }}</strong>
              <StarButton v-if="!locked" :card="{ language: env.language, kind: 'pattern', front: p.pattern, meaning: p.usage,
                example: p.examples[0] ? p.examples[0].text : '', exampleTranslation: p.examples[0] ? p.examples[0].translation : '',
                sourceSession: sessionId }" />
            </div>
            <p v-if="p.usage" class="muted">{{ p.usage }}</p>
            <div v-for="(e, k) in p.examples" :key="k" class="kp-ex">
              <p :class="env.textClass"><span v-if="e.text.trim() !== p.pattern.trim()">{{ e.text }}</span>
                <PlayButton :id="`kp-${uid}-${i}-${k}`" :text="e.text" :env="env" size="sm" /></p>
              <p v-if="e.translation" class="translation">{{ e.translation }}</p>
            </div>
          </article>
        </div>
      </section>
    </template>
    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>

<script lang="ts">
import { computed, defineComponent, onMounted, ref, watch, type PropType } from 'vue'
import AppIcon from '../ui/AppIcon.vue'
import PlayButton from '../ui/PlayButton.vue'
import StarButton from '../ui/StarButton.vue'
import { api, type NotesResponse } from '../../api'
import type { Env, Notes } from '../../api/models'
import { loadSaved } from '../../lib/cards'

let seq = 0

/** 练习进行中直接看到的重点单词和重点句型，数据来自学习笔记。 */
export default defineComponent({
  name: 'KeyPoints',
  components: { AppIcon, PlayButton, StarButton },
  props: {
    sessionId: { type: String, required: true },
    env: { type: Object as PropType<Env>, required: true },
    locked: { type: Boolean, default: false },
    version: { type: Number, default: 0 },
  },
  emits: ['generated'],
  setup(props, { emit }) {
    const uid = ++seq
    const data = ref<NotesResponse | null>(null)
    const loading = ref(true)
    const busy = ref(false)
    const waited = ref(0)
    const error = ref('')
    const wordsOpen = ref(false)
    const patternsOpen = ref(false)
    const n = computed(() => (data.value?.notes || { summary: '', vocabulary: [], grammar: [], patterns: [] }) as Notes)
    const vocab = computed(() => n.value.vocabulary || [])
    const patterns = computed(() => n.value.patterns || [])
    const hasNotes = computed(() => Boolean(data.value?.notes))

    async function load() {
      if (!data.value) loading.value = true
      error.value = ''
      try {
        data.value = await api.notes(props.sessionId)
      } catch (e: any) {
        error.value = e.message
      } finally {
        loading.value = false
      }
    }

    onMounted(() => {
      loadSaved(props.env.language)
      load()
    })
    watch(() => props.version, () => { if (props.version) load() })
    watch(() => props.sessionId, () => load())

    async function generate() {
      busy.value = true
      waited.value = 0
      error.value = ''
      try {
        data.value = await api.generateNotes(props.sessionId, (s) => (waited.value = s))
        emit('generated')
      } catch (e: any) {
        error.value = e.message
      } finally {
        busy.value = false
      }
    }

    return {
      uid, loading, busy, waited, error, wordsOpen, patternsOpen, vocab, patterns, hasNotes, generate,
      locked: computed(() => props.locked),
    }
  },
})
</script>
