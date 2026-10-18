<template>
  <div class="article">
    <section class="card art">
      <header class="art__head">
        <h2 :class="['art__title', env.textClass]">{{ content.title }}</h2>
        <button type="button" class="btn btn--primary btn--sm" @click="playAll">
          <AppIcon :name="playingArticle ? 'pause' : 'play'" :size="14" /> {{ playingArticle ? '停止播放' : '播放全文' }}
        </button>
        <label class="inline-toggle"><span>盲听</span>
          <ToggleSwitch :model-value="env.hideText" label="盲听" @update:model-value="(v) => setDisplay({ hideText: v })" />
        </label>
      </header>
      <ol class="sent-list">
        <li v-for="s in sentences" :key="s.id" :class="['sent', { 'is-playing': playingId === s.id, open: openId === s.id }]">
          <div class="sent__row">
            <PlayButton :id="s.id" :text="s.text" :env="env" size="lg" @play="tracker.count(s.id)" />
            <span class="sent__no">{{ s.n }}.</span>
            <TargetText :text="s.text" :env="env" cls="sent__text" wrap-cls="sent__body" :revealed="!!revealed[s.id]"
              @reveal="revealed[s.id] = true" />
            <span v-if="shadowOf(s.id)" :class="['pill', band(shadowOf(s.id)?.diff?.similarity)]">{{ pct(shadowOf(s.id)?.diff?.similarity) }}%</span>
            <button type="button" class="btn btn--sm btn--ghost sent__shadow" @click="toggle(s.id)">
              <AppIcon name="mic" :size="14" /> {{ shadowOf(s.id) ? '再跟读' : '跟读' }}
            </button>
            <button type="button" class="icon-btn" :aria-label="openId === s.id ? '收起' : '展开'" @click="toggle(s.id)">
              <AppIcon :name="openId === s.id ? 'chevron-down' : 'chevron-right'" :size="18" />
            </button>
          </div>
          <div v-if="openId === s.id" class="sent__more">
            <div v-if="shadowOf(s.id)" class="shadow-result">
              <DiffText v-if="shadowOf(s.id)?.diff" :tokens="shadowOf(s.id)?.diff?.tokens || []" :env="env" />
              <div class="shadow-result__meta">
                <span :class="['pill', band(shadowOf(s.id)?.diff?.similarity)]">吻合 {{ pct(shadowOf(s.id)?.diff?.similarity) }}%</span>
                <PronBadge :turn="shadowOf(s.id)" />
                <span v-if="shadowOf(s.id)?.shadowSync && shadowOf(s.id)?.lagSec != null" class="pill pill--info">
                  影子跟读 · 晚 {{ shadowOf(s.id)?.lagSec }} 秒 · 用时 {{ shadowOf(s.id)?.durationRatio }} 倍
                </span>
              </div>
            </div>
            <AnswerBox compact :env="env" submit-label="保存跟读" placeholder="听完后点麦克风，跟着读这一句" @submit="(a) => saveShadow(s, a)" />
            <ShadowSync :id="s.id" :text="s.text" :env="env" @play="tracker.count(s.id)"
              @result="(t) => $emit('add-turn', { ...t, plays: tracker.plays[s.id] || 0 })" />
          </div>
        </li>
      </ol>
    </section>

    <section class="card">
      <h2 class="card__title"><AppIcon name="note" /> 理解题</h2>
      <div class="quiz-grid">
        <article v-for="(q, i) in questions" :key="i" :class="['quiz-card', { 'quiz-card--active': activeQ === i, done: !!turnOf(`q${i}`) }]">
          <div class="quiz-card__head">
            <span class="quiz-card__no">{{ i + 1 }}.</span>
            <TargetText :text="q.text" :env="env" cls="quiz-card__q" :revealed="!!revealed[`q${i}`]" @reveal="revealed[`q${i}`] = true" />
            <PlayButton :id="`q${i}`" :text="q.text" :env="env" size="sm" @play="tracker.count(`q${i}`)" />
          </div>
          <template v-if="activeQ === i">
            <AnswerBox :env="env" @submit="(a) => saveAnswer(q, i, a)" />
            <button type="button" class="link link--muted" @click="activeQ = -1">收起</button>
          </template>
          <template v-else-if="turnOf(`q${i}`)">
            <AnsweredCard :turn="turnOf(`q${i}`)" :env="env" redoable @redo="activeQ = i" />
          </template>
          <button v-else type="button" class="btn btn--sm btn--ghost quiz-card__go" @click="activeQ = i"><AppIcon name="mic" :size="14" /> 作答</button>
        </article>
      </div>
    </section>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, ref, type PropType } from 'vue'
import AnswerBox, { type AnswerPayload } from './AnswerBox.vue'
import AnsweredCard from './AnsweredCard.vue'
import ShadowSync from './ShadowSync.vue'
import AppIcon from '../ui/AppIcon.vue'
import DiffText from '../ui/DiffText.vue'
import PlayButton from '../ui/PlayButton.vue'
import PronBadge from '../ui/PronBadge.vue'
import TargetText from '../ui/TargetText.vue'
import ToggleSwitch from '../ui/ToggleSwitch.vue'
import type { Content, Env, Question, Turn } from '../../api/models'
import { playingId, playSequence, stop } from '../../lib/audio'
import { diffReference } from '../../lib/diff'
import { useRevealed } from '../../lib/practice'
import { setDisplay } from '../../store'

export default defineComponent({
  name: 'ArticlePractice',
  components: { AnswerBox, AnsweredCard, AppIcon, DiffText, PlayButton, PronBadge, ShadowSync, TargetText, ToggleSwitch },
  props: {
    content: { type: Object as PropType<Content>, required: true },
    env: { type: Object as PropType<Env>, required: true },
    turns: { type: Array as PropType<Turn[]>, required: true },
    tracker: { type: Object as PropType<{ plays: Record<string, number>; count: (id: string) => void }>, required: true },
  },
  emits: ['add-turn'],
  setup(props, { emit }) {
    const revealed = useRevealed()
    const openId = ref<string | null>(null)
    // Rejoin "Mr." / "Dr." fragments so an old pack that split on the title dot still plays as one line.
    const sentences = computed(() => {
      const raw = props.content.sentences || []
      const merged: { text: string }[] = []
      const titleEnd = /(?:Mr|Mrs|Ms|Dr|Prof|St|Sr|Jr)\.\s*$/i
      for (const s of raw) {
        const text = (s.text || '').trim()
        if (!text) continue
        if (merged.length && titleEnd.test(merged[merged.length - 1].text)) {
          merged[merged.length - 1] = { text: `${merged[merged.length - 1].text} ${text}`.trim() }
        } else {
          merged.push({ text })
        }
      }
      return merged.map((s, i) => ({ ...s, id: `s${i}`, n: i + 1 }))
    })
    const questions = computed(() => props.content.questions || [])
    const playingArticle = computed(() => Boolean(playingId.value?.startsWith('s')))
    const turnOf = (id: string) => props.turns.find((t) => t.id === id)
    const shadowOf = (id: string) => turnOf(`shadow-${id}`)
    const firstOpen = computed(() => questions.value.findIndex((_, k) => !turnOf(`q${k}`)))
    const activeQ = ref(firstOpen.value)
    const band = (sim?: number) => (sim == null ? '' : sim >= 0.9 ? 'good' : sim >= 0.7 ? 'mid' : 'low')
    const pct = (sim?: number) => Math.round((sim || 0) * 100)
    const allPlays = () => Math.max(0, ...sentences.value.map((s) => props.tracker.plays[s.id] || 0))
    const toggle = (id: string) => (openId.value = openId.value === id ? null : id)

    function playAll() {
      if (playingArticle.value) return stop()
      sentences.value.forEach((s) => props.tracker.count(s.id))
      playSequence(sentences.value.map((s) => ({ id: s.id, text: s.text })), { language: props.env.language, rate: props.env.rate })
    }

    function saveShadow(s: { id: string; text: string }, a: AnswerPayload) {
      emit('add-turn', {
        id: `shadow-${s.id}`, kind: 'shadow', reference: s.text, ...a,
        diff: diffReference(s.text, a.answer, props.env.language), plays: props.tracker.plays[s.id] || 0,
      })
    }

    function saveAnswer(q: Question, i: number, a: AnswerPayload) {
      const id = `q${i}`
      emit('add-turn', {
        id, kind: 'answer', prompt: q.text, reference: q.answerHint, freeResponse: true, ...a,
        plays: (props.tracker.plays[id] || 0) + allPlays(), textHidden: props.env.hideText && !revealed[id],
      })
      activeQ.value = questions.value.findIndex((_, k) => k !== i && !turnOf(`q${k}`))
    }

    return { revealed, openId, sentences, questions, playingId, playingArticle, turnOf, shadowOf, activeQ, band, pct, toggle, playAll, saveShadow, saveAnswer, setDisplay }
  },
})
</script>
