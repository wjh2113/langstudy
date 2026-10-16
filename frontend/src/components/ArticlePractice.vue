<template>
  <section class="block">
    <div class="block__head">
      <h2><span class="step">1</span>听短文，逐句跟读</h2>
      <button class="btn btn--accent" @click="playAll">{{ playingArticle ? '停止播放' : '播放全文' }}</button>
    </div>
    <ol class="sentences">
      <li v-for="s in sentences" :key="s.id" :class="['sentence', { 'is-playing': playingId === s.id }]">
        <PlayButton :id="s.id" :text="s.text" :env="env" size="sm" @play="tracker.count(s.id)" />
        <div class="sentence__body">
          <TargetText :text="s.text" :env="env" :revealed="!!revealed[s.id]" @reveal="revealed[s.id] = true" />
          <p v-if="env.showTranslation" class="translation">{{ s.translation }}</p>
          <div v-if="shadowOf(s.id)" class="shadow-result">
            <DiffText :tokens="shadowOf(s.id).diff.tokens" :env="env" />
            <span :class="['pill', grade(shadowOf(s.id).diff.similarity)]">吻合 {{ Math.round(shadowOf(s.id).diff.similarity * 100) }}%</span>
            <PronBadge :turn="shadowOf(s.id)" />
          </div>
          <AnswerBox v-if="shadowing === s.id" compact :env="env" submit-label="保存跟读"
            placeholder="听完后点麦克风，跟着读这一句" @submit="(a) => saveShadow(s, a)" />
          <button v-else class="link" @click="shadowing = s.id">{{ shadowOf(s.id) ? '再跟读一次' : '跟读' }}</button>
        </div>
      </li>
    </ol>
  </section>

  <section class="block">
    <div class="block__head">
      <h2><span class="step">2</span>回答理解题</h2>
    </div>
    <div v-for="(q, i) in content.questions" :key="i" class="question">
      <div class="question__head">
        <PlayButton :id="`q${i}`" :text="q.text" :env="env" size="sm" @play="tracker.count(`q${i}`)" />
        <span class="question__no">第 {{ i + 1 }} 题</span>
      </div>
      <TargetText :text="q.text" :env="env" cls="question__text" :revealed="!!revealed[`q${i}`]" @reveal="revealed[`q${i}`] = true" />
      <p v-if="env.showTranslation" class="translation">{{ q.translation }}</p>
      <AnsweredCard v-if="turnOf(`q${i}`) && !redo[`q${i}`]" :turn="turnOf(`q${i}`)" :env="env" redoable @redo="redo[`q${i}`] = true" />
      <p v-else-if="!turnOf(`q${i}`) && i !== firstOpen" class="hint">答完上一题后在这里作答</p>
      <AnswerBox v-else :env="env" @submit="(a) => saveAnswer(q, i, a)" />
    </div>
  </section>
</template>

<script>
import { computed, reactive, ref } from 'vue'
import AnswerBox from './AnswerBox.vue'
import AnsweredCard from './AnsweredCard.vue'
import DiffText from './DiffText.vue'
import PronBadge from './PronBadge.vue'
import PlayButton from './PlayButton.vue'
import TargetText from './TargetText.vue'
import { playingId, playSequence, stop } from '../audio'
import { diffReference } from '../diff'

export default {
  name: 'ArticlePractice',
  components: { AnswerBox, AnsweredCard, DiffText, PlayButton, PronBadge, TargetText },
  props: {
    content: { type: Object, required: true },
    env: { type: Object, required: true },
    turns: { type: Array, required: true },
    tracker: { type: Object, required: true },
  },
  emits: ['add-turn'],
  setup(props, { emit }) {
    const revealed = reactive({})
    const redo = reactive({})
    const shadowing = ref(null)
    const sentences = computed(() => props.content.sentences.map((s, i) => ({ ...s, id: `s${i}` })))
    const playingArticle = computed(() => playingId.value?.startsWith('s'))
    const turnOf = (id) => props.turns.find((t) => t.id === id)
    const shadowOf = (id) => turnOf(`shadow-${id}`)
    const firstOpen = computed(() => props.content.questions.findIndex((_, k) => !turnOf(`q${k}`)))
    const grade = (sim) => (sim >= 0.85 ? 'good' : sim >= 0.6 ? 'mid' : 'low')
    const allPlays = () => Math.max(0, ...sentences.value.map((s) => props.tracker.plays[s.id] || 0))

    function playAll() {
      if (playingArticle.value) return stop()
      sentences.value.forEach((s) => props.tracker.count(s.id))
      playSequence(sentences.value.map((s) => ({ id: s.id, text: s.text })), { language: props.env.language, rate: props.env.rate })
    }

    function saveShadow(s, a) {
      emit('add-turn', {
        id: `shadow-${s.id}`, kind: 'shadow', reference: s.text, ...a,
        diff: diffReference(s.text, a.answer, props.env.language), plays: props.tracker.plays[s.id] || 0,
      })
      shadowing.value = null
    }

    function saveAnswer(q, i, a) {
      const id = `q${i}`
      emit('add-turn', {
        id, kind: 'answer', prompt: q.text, reference: q.answerHint, freeResponse: true, ...a,
        plays: (props.tracker.plays[id] || 0) + allPlays(), textHidden: props.env.hideText && !revealed[id],
      })
      redo[id] = false
    }

    return { revealed, redo, shadowing, sentences, playingId, playingArticle, turnOf, shadowOf, firstOpen, grade, playAll, saveShadow, saveAnswer }
  },
}
</script>
