<template>
  <div class="page review">
    <header class="page-head">
      <h1>复习</h1>
      <SegControl :options="langOptions" :model-value="language" label="语言" @update:model-value="(v) => (language = v)" />
    </header>
    <div class="chips">
      <button type="button" v-for="t in tabs" :key="t.key" :class="['chip', { on: tab === t.key }]" @click="tab = t.key">{{ t.label }}</button>
    </div>

    <!-- today's reviews -->
    <template v-if="tab === 'review'">
      <p v-if="loading" class="hint">正在读取…</p>
      <div v-else-if="!card" class="empty card">
        <template v-if="reviewed">今天该复习的 {{ reviewed }} 张都完成了。</template>
        <template v-else-if="total">现在没有到期的卡片。下一张在 {{ nextDueText }} 到期。</template>
        <template v-else>还没有卡片。在学习笔记、报告里点 ☆ 收藏单词和句型；报告里改正过的句子会自动进入错句本。</template>
      </div>

      <section v-else class="card flash">
        <div class="flash__meta">
          <span class="tag">{{ kindName[card.kind] }}</span>
          <span class="muted">还剩 {{ queue.length - idx }} 张</span>
        </div>

        <!-- question side -->
        <template v-if="direction === 'listen'">
          <p class="flash__ask">听一听，想想它是什么意思</p>
          <PlayButton :id="`card-${card.id}`" :text="card.front" :env="cardEnv" label="播放" />
        </template>
        <template v-else-if="card.kind === 'sentence'">
          <p class="flash__ask">说出改正后的句子</p>
          <p class="flash__hint">你原来说的：<span :class="cardEnv.textClass">{{ card.extra }}</span></p>
          <p v-if="card.meaning" class="flash__hint">要点：{{ card.meaning }}</p>
        </template>
        <template v-else>
          <p class="flash__ask">用{{ language === 'ja' ? '日语' : '英语' }}说出这个意思</p>
          <p class="flash__meaning">{{ card.meaning }}</p>
          <p v-if="card.exampleTranslation" class="flash__hint">例句：{{ card.exampleTranslation }}</p>
        </template>

        <AnswerBox v-if="direction === 'speak' && !revealed" :key="'a' + card.id" compact :env="cardEnv" submit-label="核对"
          placeholder="点麦克风说出来" @submit="checkSpoken" />
        <p v-if="checking" class="hint">正在评测发音…</p>
        <button type="button" v-if="direction === 'listen' && !revealed" class="btn btn--primary" @click="revealed = true">显示答案</button>
        <button type="button" v-if="direction === 'speak' && !revealed && !checking" class="link link--muted" @click="revealed = true">想不起来，看答案</button>

        <!-- answer side -->
        <div v-if="revealed" class="flash__answer">
          <div v-if="attempt" :class="['flash__result', attempt.pass ? 'good' : 'low']">
            <span>{{ attempt.pass ? '说对了' : '还差一点' }}</span>
            <span v-if="attempt.score != null">发音 {{ Math.round(attempt.score) }}</span>
            <button type="button" v-else-if="canPronounce && attempt.blob" class="btn btn--sm btn--ghost" :disabled="checking" @click="assess">评测发音</button>
            <DiffText v-if="attempt.diff" :tokens="attempt.diff.tokens" :env="cardEnv" />
            <span v-else class="muted">你说的：{{ attempt.text }}</span>
          </div>
          <div class="flash__front">
            <PlayButton :id="`card-a-${card.id}`" :text="card.front" :env="cardEnv" size="sm" />
            <strong :class="cardEnv.textClass">{{ card.front }}</strong>
            <span v-if="card.reading" class="muted">{{ card.reading }}</span>
          </div>
          <p v-if="card.kind !== 'sentence'" class="flash__meaning">{{ card.meaning }}</p>
          <div v-if="card.example" class="example">
            <PlayButton :id="`card-e-${card.id}`" :text="card.example" :env="cardEnv" size="sm" />
            <div>
              <p :class="cardEnv.textClass"><span v-if="card.kind === 'sentence'" class="muted">更地道：</span>{{ card.example }}</p>
              <p v-if="card.exampleTranslation" class="translation">{{ card.exampleTranslation }}</p>
            </div>
          </div>
          <div class="grades">
            <button type="button" v-for="g in grades" :key="g.key" :class="['grade', g.key, { suggested: suggested === g.key }]" @click="grade(g.key)">
              {{ g.label }}<small>{{ g.hint }}</small>
            </button>
          </div>
        </div>
        <p v-if="error" class="error">{{ error }}</p>
      </section>
    </template>

    <!-- word / mistake lists -->
    <template v-else>
      <label class="input input--search review__search"><AppIcon name="search" :size="18" /><input v-model="search" placeholder="搜索" aria-label="搜索" /></label>
      <p v-if="!listItems.length" class="empty card">{{ tab === 'sentence' ? '错句本是空的。报告里改正过的句子会自动加进来。' : '生词本是空的。在学习笔记或报告里点 ☆ 收藏。' }}</p>
      <div v-else class="card card--flush table-wrap"><table class="table">
        <thead><tr><th>{{ tab === 'sentence' ? '正确说法' : '单词 / 句型' }}</th><th>{{ tab === 'sentence' ? '你原来说的' : '意思' }}</th><th>下次复习</th><th /></tr></thead>
        <tbody>
          <tr v-for="c in listItems" :key="c.id">
            <td>
              <span class="cell-front">
                <PlayButton :id="`list-${c.id}`" :text="c.front" :env="cardEnv" size="sm" />
                <span :class="cardEnv.textClass">{{ c.front }}</span>
              </span>
              <span v-if="c.reading" class="muted table__title">{{ c.reading }}</span>
            </td>
            <td :class="tab === 'sentence' ? cardEnv.textClass : ''">{{ tab === 'sentence' ? c.extra : c.meaning }}</td>
            <td class="nowrap">{{ dueText(c.dueAt) }}</td>
            <td><button type="button" class="icon-btn icon-btn--danger" aria-label="删除" @click="remove(c)"><AppIcon name="trash" :size="16" /></button></td>
          </tr>
        </tbody>
      </table></div>
    </template>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, ref, watch } from 'vue'
import AnswerBox, { type AnswerPayload } from '../components/practice/AnswerBox.vue'
import AppIcon from '../components/ui/AppIcon.vue'
import DiffText from '../components/ui/DiffText.vue'
import PlayButton from '../components/ui/PlayButton.vue'
import SegControl from '../components/ui/SegControl.vue'
import { api } from '../api'
import type { Card, Diff, Lang } from '../api/models'
import { play, prefetch } from '../lib/audio'
import { forget, refreshDue } from '../lib/cards'
import { diffReference, tokensOf } from '../lib/diff'
import { envFor, store } from '../store'

const GRADES = [
  { key: 'again', label: '忘了', hint: '10 分钟后' },
  { key: 'hard', label: '模糊', hint: '稍后' },
  { key: 'good', label: '记得', hint: '按计划' },
  { key: 'easy', label: '很熟', hint: '隔久一点' },
]

interface Attempt { text: string; diff: Diff | null; score: number | null; pass: boolean; blob: Blob | null }

/** Spaced-repetition review of saved words, patterns and corrected sentences, plus the deck lists. */
export default defineComponent({
  name: 'ReviewView',
  components: { AnswerBox, AppIcon, DiffText, PlayButton, SegControl },
  setup() {
    const language = ref<Lang>(store.prefs.language)
    const tab = ref('review')
    const queue = ref<Card[]>([])
    const all = ref<Card[]>([])
    const idx = ref(0)
    const reviewed = ref(0)
    const revealed = ref(false)
    const attempt = ref<Attempt | null>(null)
    const checking = ref(false)
    const loading = ref(true)
    const error = ref('')
    const search = ref('')
    const summary = ref<Record<string, { due: number; total: number }>>({})
    const cardEnv = computed(() => envFor(language.value))
    const card = computed(() => queue.value[idx.value] || null)
    const total = computed(() => all.value.length)
    const canPronounce = computed(() => Boolean(store.config?.pronounceServer))
    const langOptions = computed(() => (['en', 'ja'] as Lang[]).map((l) => ({
      value: l, label: l === 'ja' ? '日本語' : 'English', badge: summary.value[l]?.due || undefined,
    })))

    // words alternate between "hear it → recall" and "see meaning → say it"; patterns are recall only;
    // mistake sentences are always said aloud
    const direction = computed(() => {
      const c = card.value
      if (!c) return null
      if (c.kind === 'sentence') return 'speak'
      if (c.kind === 'pattern') return 'listen'
      return c.reps % 2 === 0 ? 'listen' : 'speak'
    })
    const suggested = computed(() => (attempt.value ? (attempt.value.pass ? 'good' : 'again') : ''))

    async function load() {
      loading.value = true
      error.value = ''
      try {
        const [due, everything, s] = await Promise.all([
          api.cards({ language: language.value, due: true }),
          api.cards({ language: language.value }),
          refreshDue(),
        ])
        queue.value = due
        all.value = everything
        summary.value = s || {}
        idx.value = 0
        reviewed.value = 0
        resetCard()
      } catch (e: any) {
        error.value = e.message
      } finally {
        loading.value = false
      }
    }
    watch(language, load, { immediate: true })

    function resetCard() {
      revealed.value = false
      attempt.value = null
      checking.value = false
      if (card.value && direction.value === 'listen') {
        const c = card.value
        warmCard(c)
        setTimeout(() => { if (card.value === c && !revealed.value) playCard(c) }, 300)
      }
    }
    function cardPlayOpts() {
      const e = cardEnv.value
      return {
        language: language.value, rate: e.rate, voiceIndex: e.voiceIndex,
        accent: e.accent || 'default', locale: e.accentLocale || null,
      }
    }
    const warmCard = (c: Card) => prefetch(c.front, cardPlayOpts())
    const playCard = (c: Card) => play(`card-${c.id}`, c.front, cardPlayOpts()).catch(() => {})

    // judged by comparing the text; pronunciation assessment is billed, so it only runs on request
    function checkSpoken(a: AnswerPayload) {
      const c = card.value as Card
      const diff = c.kind === 'sentence' ? diffReference(c.front, a.answer, language.value) : null
      const said = tokensOf(a.answer, language.value).join(' ')
      const target = tokensOf(c.front, language.value).join(' ')
      const pass = c.kind === 'sentence' ? (diff as Diff).similarity >= 0.85 : target !== '' && said.includes(target)
      attempt.value = { text: a.answer, diff, score: null, pass, blob: c.kind === 'sentence' ? a.audioBlob || null : null }
      revealed.value = true
    }

    async function assess() {
      const at = attempt.value
      const c = card.value
      if (!at?.blob || !c) return
      checking.value = true
      try {
        const score = (await api.pronounce({ blob: at.blob }, c.front, language.value)).score
        attempt.value = { ...at, score, pass: score != null ? score >= 80 && (at.diff?.similarity || 0) >= 0.7 : at.pass }
      } catch (e: any) {
        error.value = e.message
      } finally {
        checking.value = false
      }
    }

    async function grade(g: string) {
      const c = card.value as Card
      error.value = ''
      try {
        await api.reviewCard(c.id, g)
      } catch (e: any) {
        error.value = e.message
        return
      }
      reviewed.value++
      if (g === 'again') queue.value = [...queue.value, c] // see it again in this session
      idx.value++
      resetCard()
      refreshDue().then((s) => s && (summary.value = s))
    }

    const listItems = computed(() => {
      const kinds = tab.value === 'sentence' ? ['sentence'] : ['word', 'pattern']
      const q = search.value.trim().toLowerCase()
      return all.value.filter((c) => kinds.includes(c.kind) &&
        (!q || [c.front, c.meaning, c.extra].some((t) => (t || '').toLowerCase().includes(q))))
    })

    async function remove(c: Card) {
      await api.deleteCard(c.id).catch(() => {})
      forget(c.language, c.kind, c.front)
      all.value = all.value.filter((x) => x.id !== c.id)
      queue.value = queue.value.filter((x, i) => x.id !== c.id || i < idx.value)
      refreshDue().then((s) => s && (summary.value = s))
    }

    function dueText(at: string) {
      const days = (new Date(at).getTime() - Date.now()) / 86400000
      if (days <= 0) return '现在'
      if (days < 1) return `${Math.max(1, Math.round(days * 24))} 小时后`
      return `${Math.round(days)} 天后`
    }
    const nextDueText = computed(() => {
      const next = [...all.value].sort((a, b) => a.dueAt.localeCompare(b.dueAt))[0]
      return next ? dueText(next.dueAt) : ''
    })

    return {
      language, tab, queue, idx, reviewed, revealed, attempt, checking, loading, error, search, summary, langOptions, canPronounce,
      cardEnv, card, total, direction, suggested, checkSpoken, assess, grade, listItems, remove, dueText, nextDueText,
      grades: GRADES,
      kindName: { word: '单词', pattern: '句型', sentence: '错句' } as Record<string, string>,
      tabs: [{ key: 'review', label: '今日复习' }, { key: 'word', label: '生词本' }, { key: 'sentence', label: '错句本' }],
    }
  },
})
</script>
