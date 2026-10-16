<template>
  <section class="notes">
    <div class="notes__head">
      <div>
        <h2>学习笔记</h2>
        <p v-if="data && data.generatedAt" class="muted">生成于 {{ data.generatedAt.replace('T', ' ').slice(0, 16) }} · 已保存</p>
      </div>
      <div v-if="data && data.notes" class="notes__actions">
        <template v-if="confirming">
          <span class="muted">重新生成会替换当前笔记</span>
          <button class="btn btn--ghost" @click="confirming = false">取消</button>
          <button class="btn btn--primary" :disabled="busy" @click="generate">确定重新生成</button>
        </template>
        <button v-else class="btn btn--ghost" :disabled="busy" @click="confirming = true">重新生成</button>
      </div>
    </div>

    <p v-if="loading" class="hint">正在读取…</p>
    <div v-else-if="busy" class="hint thinking"><span class="dots" aria-hidden="true"><i /><i /><i /></span>正在整理单词、语法和句型，大约 10–30 秒…</div>
    <div v-else-if="!data || !data.notes" class="notes__empty">
      <p>把这个话题的重点单词、语法和句型整理成一份笔记，生成后会自动保存，随时回来复习。</p>
      <button class="btn btn--primary" @click="generate">生成学习笔记</button>
    </div>

    <template v-else>
      <p v-if="n.summary" class="notes__summary">{{ n.summary }}</p>
      <nav class="notes__tabs" role="tablist">
        <button v-for="t in tabs" :key="t.key" role="tab" :aria-selected="tab === t.key" :class="{ on: tab === t.key }"
          @click="tab = t.key">{{ t.label }} <small>{{ (n[t.key] || []).length }}</small></button>
      </nav>

      <div v-if="tab === 'vocabulary'" class="vocab vocab--notes">
        <div v-for="(v, i) in n.vocabulary" :key="i" class="vocab__item">
          <div class="vocab__word">
            <PlayButton :id="`nw-${uid}-${i}`" :text="v.word" :env="env" size="sm" />
            <strong :class="env.textClass">{{ v.word }}</strong>
            <span v-if="v.reading" class="muted">{{ v.reading }}</span>
            <span v-if="v.pos" class="tag">{{ v.pos }}</span>
            <StarButton class="star--end" :card="{ language: env.language, kind: 'word', front: v.word, reading: v.reading, meaning: v.meaning,
              example: v.example, exampleTranslation: v.exampleTranslation, sourceSession: sessionId }" />
          </div>
          <p>{{ v.meaning }}</p>
          <div v-if="v.example" class="example">
            <PlayButton :id="`ne-${uid}-${i}`" :text="v.example" :env="env" size="sm" />
            <div>
              <p :class="env.textClass">{{ v.example }}</p>
              <p v-if="v.exampleTranslation" class="translation">{{ v.exampleTranslation }}</p>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="tab === 'grammar'" class="note-cards">
        <article v-for="(g, i) in n.grammar" :key="i" class="note-card">
          <h3 :class="env.textClass">{{ g.point }}</h3>
          <p>{{ g.explanation }}</p>
          <div v-for="(e, k) in g.examples" :key="k" class="example">
            <PlayButton :id="`ng-${uid}-${i}-${k}`" :text="e.text" :env="env" size="sm" />
            <div>
              <p :class="env.textClass">{{ e.text }}</p>
              <p v-if="e.translation" class="translation">{{ e.translation }}</p>
            </div>
          </div>
          <p v-if="g.pitfall" class="pitfall">注意：{{ g.pitfall }}</p>
        </article>
      </div>

      <div v-else class="note-cards">
        <article v-for="(p, i) in n.patterns" :key="i" class="note-card">
          <div class="note-card__head">
            <h3 :class="env.textClass">{{ p.pattern }}</h3>
            <StarButton :card="{ language: env.language, kind: 'pattern', front: p.pattern, meaning: p.usage,
              example: p.examples[0] ? p.examples[0].text : '', exampleTranslation: p.examples[0] ? p.examples[0].translation : '',
              sourceSession: sessionId }" />
          </div>
          <p v-if="p.usage" class="muted">{{ p.usage }}</p>
          <div v-for="(e, k) in p.examples" :key="k" class="example">
            <PlayButton :id="`np-${uid}-${i}-${k}`" :text="e.text" :env="env" size="sm" />
            <div>
              <p :class="env.textClass">{{ e.text }}</p>
              <p v-if="e.translation" class="translation">{{ e.translation }}</p>
            </div>
          </div>
        </article>
      </div>
    </template>
    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>

<script>
import { computed, onMounted, ref } from 'vue'
import PlayButton from './PlayButton.vue'
import StarButton from './StarButton.vue'
import { api } from '../api'

let seq = 0

/** Saved study notes (vocabulary / grammar / sentence patterns) for one practice session. */
export default {
  name: 'StudyNotes',
  components: { PlayButton, StarButton },
  props: {
    sessionId: { type: String, required: true },
    env: { type: Object, required: true },
  },
  emits: ['generated'],
  setup(props, { emit }) {
    const uid = ++seq
    const data = ref(null)
    const loading = ref(true)
    const busy = ref(false)
    const confirming = ref(false)
    const error = ref('')
    const tab = ref('vocabulary')
    const n = computed(() => data.value?.notes || {})

    onMounted(async () => {
      try {
        data.value = await api.notes(props.sessionId)
      } catch (e) {
        error.value = e.message
      } finally {
        loading.value = false
      }
    })

    async function generate() {
      busy.value = true
      confirming.value = false
      error.value = ''
      try {
        data.value = await api.generateNotes(props.sessionId)
        emit('generated')
      } catch (e) {
        error.value = e.message
      } finally {
        busy.value = false
      }
    }

    return {
      uid, data, loading, busy, confirming, error, tab, n, generate,
      tabs: [{ key: 'vocabulary', label: '单词' }, { key: 'grammar', label: '语法' }, { key: 'patterns', label: '句型' }],
    }
  },
}
</script>
