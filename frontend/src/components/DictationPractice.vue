<template>
  <section class="block">
    <div class="block__head">
      <h2>听录音，把空格填上</h2>
      <button class="btn btn--accent" @click="playAll">{{ playingAll ? '停止播放' : '播放全文' }}</button>
    </div>
    <p class="hint">每句可以反复听。填完点“检查”，或者全部填完直接点右侧“结束并评分”。</p>
    <ol class="sentences">
      <li v-for="s in sentences" :key="s.id" :class="['sentence', { 'is-playing': playingId === s.id }]">
        <PlayButton :id="s.id" :text="s.text" :env="env" size="sm" @play="tracker.count(s.id)" />
        <div class="sentence__body">
          <p :class="['cloze', env.textClass]">
            <template v-for="(part, k) in s.parts" :key="k">
              <span v-if="part.text != null">{{ part.text }}</span>
              <span v-else class="cloze__slot">
                <input v-model="answers[part.key]" :class="['cloze__input', resultClass(part.key)]" :disabled="checked[s.id]"
                  :style="{ width: Math.max(4, part.answer.length + 2) + 'ch' }" :aria-label="`第 ${part.n} 个空`"
                  autocomplete="off" autocapitalize="off" spellcheck="false" @keydown.enter="check(s)" />
                <span v-if="checked[s.id] && !isRight(part)" class="cloze__answer">{{ part.answer }}</span>
              </span>
            </template>
          </p>
          <p v-if="env.showTranslation" class="translation">{{ s.translation }}</p>
          <button v-if="!checked[s.id]" class="link" @click="check(s)">检查</button>
          <span v-else :class="['pill', s.blanks.every(isRight) ? 'good' : 'low']">
            {{ s.blanks.filter(isRight).length }} / {{ s.blanks.length }} 正确
          </span>
        </div>
      </li>
    </ol>
  </section>
</template>

<script>
import { computed, reactive, watch } from 'vue'
import PlayButton from './PlayButton.vue'
import { playingId, playSequence, stop } from '../audio'
import { tokensOf } from '../diff'

/** Cloze dictation: listen and fill in the blanked words. */
export default {
  name: 'DictationPractice',
  components: { PlayButton },
  props: {
    content: { type: Object, required: true },
    env: { type: Object, required: true },
    turns: { type: Array, required: true },
    tracker: { type: Object, required: true },
  },
  emits: ['add-turn'],
  setup(props, { emit }) {
    const answers = reactive({})
    const checked = reactive({})
    // split each sentence into text pieces and blanks (first occurrence of each blank word)
    const sentences = computed(() => { let n = 0; return props.content.sentences.map((s, i) => {
      const spots = s.blanks
        .map((b, j) => ({ b, j, at: s.text.indexOf(b) }))
        .filter((x) => x.at >= 0)
        .sort((a, b) => a.at - b.at)
      const parts = []
      let pos = 0
      const blanks = []
      for (const x of spots) {
        if (x.at < pos) continue // overlapping blanks: keep the first
        if (x.at > pos) parts.push({ text: s.text.slice(pos, x.at) })
        const part = { key: `d${i}-${x.j}`, answer: x.b, n: ++n }
        parts.push(part)
        blanks.push(part)
        pos = x.at + x.b.length
      }
      if (pos < s.text.length) parts.push({ text: s.text.slice(pos) })
      return { ...s, id: `s${i}`, parts, blanks }
    }) })
    const playingAll = computed(() => playingId.value?.startsWith('s'))

    const norm = (t) => tokensOf(t || '', props.env.language).join(' ')
    const isRight = (part) => norm(answers[part.key]) === norm(part.answer) && norm(part.answer) !== ''
    const resultClass = (key) => {
      const s = sentences.value.find((x) => x.blanks.some((b) => b.key === key))
      if (!s || !checked[s.id]) return ''
      return isRight(s.blanks.find((b) => b.key === key)) ? 'ok' : 'bad'
    }

    // every blank is a turn; keep them in sync with what's typed so "finish" always has them
    function sync(s) {
      for (const part of s.blanks) {
        emit('add-turn', {
          id: part.key, kind: 'dictation', prompt: s.text, reference: part.answer,
          answer: answers[part.key] || '', input: 'text', plays: props.tracker.plays[s.id] || 0,
        })
      }
    }
    watch(answers, () => sentences.value.forEach(sync), { deep: true })
    sentences.value.forEach(sync)

    function check(s) {
      checked[s.id] = true
      sync(s)
    }

    function playAll() {
      if (playingAll.value) return stop()
      sentences.value.forEach((s) => props.tracker.count(s.id))
      playSequence(sentences.value.map((s) => ({ id: s.id, text: s.text })), { language: props.env.language, rate: props.env.rate })
    }

    return { answers, checked, sentences, playingId, playingAll, isRight, resultClass, check, playAll }
  },
}
</script>
