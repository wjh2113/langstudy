<template>
  <section class="notes">
    <div class="notes__bar">
      <SegControl v-if="hasNotes" :options="tabOptions" :model-value="tab" label="笔记分类" @update:model-value="(v) => (tab = v)" />
      <h2 v-else class="section-title"><AppIcon name="book" /> 学习笔记</h2>
      <div v-if="hasNotes && !readonly" class="notes__actions">
        <span v-if="data && data.generatedAt" class="muted">生成于 {{ dateTime(data.generatedAt) }} · 已保存</span>
        <template v-if="confirming">
          <span class="muted">重新生成会替换当前笔记</span>
          <button type="button" class="btn btn--sm btn--ghost" @click="confirming = false">取消</button>
          <button type="button" class="btn btn--sm btn--primary" :disabled="busy" @click="generate">确定</button>
        </template>
        <button v-else type="button" class="link" :disabled="busy" @click="confirming = true"><AppIcon name="rotate" :size="16" /> 重新生成</button>
      </div>
    </div>

    <p v-if="loading" class="hint">正在读取…</p>
    <div v-else-if="busy" class="card notes__busy" role="status">
      <span class="spinner" aria-hidden="true" />正在整理单词、语法和句型… {{ waited }} 秒
    </div>
    <div v-else-if="!hasNotes" class="card notes__empty">
      <p>把这个话题的重点单词、语法和句型整理成一份笔记，生成后会自动保存，随时回来复习。</p>
      <button v-if="!readonly" type="button" class="btn btn--primary" @click="generate"><AppIcon name="sparkle" :size="16" /> 生成学习笔记</button>
    </div>

    <template v-else>
      <p v-if="n.summary" class="notes__summary"><AppIcon name="bulb" :size="16" /> {{ n.summary }}</p>

      <div v-if="tab === 'vocabulary'" class="word-grid">
        <article v-for="(v, i) in n.vocabulary" :key="i" class="card word-card">
          <div class="word-card__top">
            <h3 :class="['word-card__word', env.textClass]">{{ v.word }}</h3>
            <PlayButton :id="`nw-${uid}-${i}`" :text="v.word" :env="env" size="sm" />
          </div>
          <p class="word-card__meta">
            <span v-if="v.reading" class="muted">{{ v.reading }}</span>
            <span v-if="v.pos" class="tag tag--soft">{{ v.pos }}</span>
            <StarButton v-if="!readonly" class="word-card__star" :card="{ language: env.language, kind: 'word', front: v.word, reading: v.reading,
              meaning: v.meaning, example: v.example, exampleTranslation: v.exampleTranslation, sourceSession: sessionId }" />
          </p>
          <p class="word-card__meaning">{{ v.meaning }}</p>
          <div v-if="v.example" class="word-card__ex">
            <p :class="env.textClass">{{ v.example }}
              <PlayButton :id="`ne-${uid}-${i}`" :text="v.example" :env="env" size="sm" /></p>
            <p v-if="v.exampleTranslation" class="translation">{{ v.exampleTranslation }}</p>
          </div>
        </article>
      </div>

      <div v-else-if="tab === 'grammar'" class="note-grid">
        <article v-for="(g, i) in n.grammar" :key="i" class="card note-card">
          <span class="label-pill label-pill--blue"><AppIcon name="doc" :size="16" /> 语法</span>
          <h3 class="note-card__title">{{ g.point }}</h3>
          <p class="muted">{{ g.explanation }}</p>
          <div v-for="(e, k) in g.examples" :key="k" class="ex-row">
            <span class="tag tag--soft">例句</span>
            <div>
              <p :class="env.textClass">{{ e.text }} <PlayButton :id="`ng-${uid}-${i}-${k}`" :text="e.text" :env="env" size="sm" /></p>
              <p v-if="e.translation" class="translation">{{ e.translation }}</p>
            </div>
          </div>
          <p v-if="g.pitfall" class="pitfall"><AppIcon name="alert" :size="18" /><strong>注意</strong><span>{{ g.pitfall }}</span></p>
        </article>
      </div>

      <div v-else class="note-grid">
        <article v-for="(p, i) in n.patterns" :key="i" class="card note-card">
          <div class="note-card__head">
            <span class="label-pill label-pill--green"><AppIcon name="chat-dots" :size="16" /> 句型</span>
            <StarButton v-if="!readonly" :card="{ language: env.language, kind: 'pattern', front: p.pattern, meaning: p.usage,
              example: p.examples[0] ? p.examples[0].text : '', exampleTranslation: p.examples[0] ? p.examples[0].translation : '',
              sourceSession: sessionId }" />
          </div>
          <h3 :class="['note-card__title', env.textClass]">{{ p.pattern }}</h3>
          <div v-if="p.usage" class="ex-row ex-row--line"><span class="tag tag--soft">用法</span><p class="muted">{{ p.usage }}</p></div>
          <div v-for="(e, k) in p.examples" :key="k" class="ex-row">
            <span class="tag tag--soft">例句</span>
            <div>
              <p :class="env.textClass">{{ e.text }} <PlayButton :id="`np-${uid}-${i}-${k}`" :text="e.text" :env="env" size="sm" /></p>
              <p v-if="e.translation" class="translation">{{ e.translation }}</p>
            </div>
          </div>
        </article>
      </div>
    </template>
    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>

<script lang="ts">
import { computed, defineComponent, onMounted, ref, type PropType } from 'vue'
import AppIcon from '../ui/AppIcon.vue'
import PlayButton from '../ui/PlayButton.vue'
import SegControl from '../ui/SegControl.vue'
import StarButton from '../ui/StarButton.vue'
import { api, type NotesResponse } from '../../api'
import type { Env, Notes } from '../../api/models'
import { dateTime } from '../../lib/format'

let seq = 0

/** Saved study notes (vocabulary / grammar / sentence patterns) for one practice session. */
export default defineComponent({
  name: 'StudyNotes',
  components: { AppIcon, PlayButton, SegControl, StarButton },
  props: {
    sessionId: { type: String, required: true },
    env: { type: Object as PropType<Env>, required: true },
    readonly: { type: Boolean, default: false },
    initial: { type: Object as PropType<NotesResponse | null>, default: null },
  },
  emits: ['generated'],
  setup(props, { emit }) {
    const uid = ++seq
    const data = ref<NotesResponse | null>(props.initial)
    const loading = ref(!props.initial)
    const busy = ref(false)
    const waited = ref(0)
    const confirming = ref(false)
    const error = ref('')
    const tab = ref<string | number>('vocabulary')
    const n = computed(() => (data.value?.notes || { summary: '', vocabulary: [], grammar: [], patterns: [] }) as Notes)
    const hasNotes = computed(() => Boolean(data.value?.notes))
    const tabOptions = computed(() => [
      { value: 'vocabulary', label: '单词', badge: n.value.vocabulary.length },
      { value: 'grammar', label: '语法', badge: n.value.grammar.length },
      { value: 'patterns', label: '句型', badge: n.value.patterns.length },
    ])

    onMounted(async () => {
      if (props.initial) return
      try {
        data.value = await api.notes(props.sessionId)
      } catch (e: any) {
        error.value = e.message
      } finally {
        loading.value = false
      }
    })

    async function generate() {
      busy.value = true
      waited.value = 0
      confirming.value = false
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

    return { uid, data, loading, busy, waited, confirming, error, tab, n, hasNotes, tabOptions, generate, dateTime }
  },
})
</script>
