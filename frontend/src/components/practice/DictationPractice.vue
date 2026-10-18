<template>
  <section class="card art">
    <header class="art__head">
      <h2 class="art__title">听录音，把空格填上</h2>
      <button type="button" class="btn btn--primary btn--sm" @click="playAll">
        <AppIcon :name="playingAll ? 'pause' : 'play'" :size="14" /> {{ playingAll ? '停止播放' : '播放全文' }}
      </button>
    </header>
    <p class="hint">每句可以反复听。填完点“检查”，或者全部填完直接点“结束并评分”。</p>
    <ol class="sent-list">
      <li v-for="s in sentences" :key="s.id" :class="['sent', { 'is-playing': playingId === s.id }]">
        <div class="sent__row">
          <PlayButton :id="s.id" :text="s.text" :env="env" size="lg" @play="tracker.count(s.id)" />
          <span class="sent__no">{{ s.n }}.</span>
          <div class="sent__body">
            <p :class="['cloze', env.textClass]">
              <template v-for="(part, k) in s.parts" :key="k">
                <span v-if="part.text != null">{{ part.text }}</span>
                <span v-else class="cloze__slot">
                  <input v-model="st.answers[part.key]" :class="['cloze__input', resultClass(part.key)]" :disabled="st.checked[s.id]"
                    :style="{ width: Math.max(4, part.answer.length + 2) + 'ch' }" :aria-label="`第 ${part.n} 个空`"
                    autocomplete="off" autocapitalize="off" spellcheck="false" @keydown.enter="check(s)" />
                  <span v-if="st.checked[s.id] && !isRight(part)" class="cloze__answer">{{ part.answer }}</span>
                </span>
              </template>
            </p>
            <TranslationLine v-if="env.showTranslation && st.checked[s.id]" :text="s.text" :language="env.language" />
          </div>
          <button v-if="!st.checked[s.id]" type="button" class="btn btn--sm btn--ghost" @click="check(s)">检查</button>
          <span v-else :class="['pill', s.blanks.every(isRight) ? 'good' : 'low']">{{ s.blanks.filter(isRight).length }} / {{ s.blanks.length }} 正确</span>
        </div>
      </li>
    </ol>
  </section>
</template>

<script lang="ts">
import { computed, defineComponent, watch, type PropType } from 'vue'
import AppIcon from '../ui/AppIcon.vue'
import PlayButton from '../ui/PlayButton.vue'
import TranslationLine from '../ui/TranslationLine.vue'
import type { Content, Env, Turn } from '../../api/models'
import { playingId, playSequence, stop } from '../../lib/audio'
import { tokensOf } from '../../lib/diff'
import { useModeState } from '../../lib/practice'

interface Blank { key: string; answer: string; n: number }
interface Part { text?: string; key?: string; answer?: string; n?: number }
interface DictState { answers: Record<string, string>; checked: Record<string, boolean> }

/** Cloze dictation: listen and fill in the blanked words. */
export default defineComponent({
  name: 'DictationPractice',
  components: { AppIcon, PlayButton, TranslationLine },
  props: {
    content: { type: Object as PropType<Content>, required: true },
    env: { type: Object as PropType<Env>, required: true },
    turns: { type: Array as PropType<Turn[]>, required: true },
    tracker: { type: Object as PropType<{ plays: Record<string, number>; count: (id: string) => void }>, required: true },
  },
  emits: ['add-turn'],
  setup(props, { emit }) {
    const st = useModeState<DictState>('dictation', { answers: {}, checked: {} })
    // split each sentence into text pieces and blanks (first occurrence of each blank word)
    const sentences = computed(() => {
      let n = 0
      const raw = props.content.sentences || []
      const merged: { text: string; blanks?: string[] }[] = []
      const titleEnd = /(?:Mr|Mrs|Ms|Dr|Prof|St|Sr|Jr)\.\s*$/i
      for (const s of raw) {
        const text = (s.text || '').trim()
        if (!text) continue
        if (merged.length && titleEnd.test(merged[merged.length - 1].text)) {
          const prev = merged[merged.length - 1]
          const blanks = [...(prev.blanks || [])]
          for (const b of s.blanks || []) if (b && !blanks.includes(b)) blanks.push(b)
          merged[merged.length - 1] = { text: `${prev.text} ${text}`.trim(), blanks }
        } else {
          merged.push({ text, blanks: [...(s.blanks || [])] })
        }
      }
      return merged.map((s, i) => {
        const spots = (s.blanks || [])
          .map((b, j) => ({ b, j, at: s.text.indexOf(b) }))
          .filter((x) => x.at >= 0)
          .sort((a, b) => a.at - b.at)
        const parts: Part[] = []
        const blanks: Blank[] = []
        let pos = 0
        for (const x of spots) {
          if (x.at < pos) continue // overlapping blanks: keep the first
          if (x.at > pos) parts.push({ text: s.text.slice(pos, x.at) })
          const part = { key: `d${i}-${x.j}`, answer: x.b, n: ++n }
          parts.push(part)
          blanks.push(part)
          pos = x.at + x.b.length
        }
        if (pos < s.text.length) parts.push({ text: s.text.slice(pos) })
        return { ...s, id: `s${i}`, n: i + 1, parts, blanks }
      })
    })
    const playingAll = computed(() => Boolean(playingId.value?.startsWith('s')))

    const norm = (t?: string) => tokensOf(t || '', props.env.language).join(' ')
    const isRight = (part: Part) => norm(st.answers[part.key as string]) === norm(part.answer) && norm(part.answer) !== ''
    const resultClass = (key: string) => {
      const s = sentences.value.find((x) => x.blanks.some((b) => b.key === key))
      if (!s || !st.checked[s.id]) return ''
      return isRight(s.blanks.find((b) => b.key === key) as Blank) ? 'ok' : 'bad'
    }

    // every blank is a turn; keep them in sync with what's typed so "finish" always has them
    function sync(s: { id: string; text: string; blanks: Blank[] }) {
      for (const part of s.blanks) {
        const answer = st.answers[part.key] || ''
        const existing = props.turns.find((t) => t.id === part.key)
        if (existing && existing.answer === answer) continue
        emit('add-turn', {
          id: part.key, kind: 'dictation', prompt: s.text, reference: part.answer,
          answer, input: 'text', plays: props.tracker.plays[s.id] || 0,
        })
      }
    }
    watch(() => st.answers, () => sentences.value.forEach(sync), { deep: true })
    sentences.value.forEach(sync)

    function check(s: { id: string; text: string; blanks: Blank[] }) {
      st.checked[s.id] = true
      sync(s)
    }

    function playAll() {
      if (playingAll.value) return stop()
      sentences.value.forEach((s) => props.tracker.count(s.id))
      playSequence(sentences.value.map((s) => ({ id: s.id, text: s.text })), { language: props.env.language, rate: props.env.rate })
    }

    return { st, sentences, playingId, playingAll, isRight, resultClass, check, playAll }
  },
})
</script>
