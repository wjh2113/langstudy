<template>
  <div class="quiz">
    <h1>口音听辨</h1>
    <p class="muted">听一句英语，猜猜是哪里的口音。练多了，遇到不同口音的同事、客户就不容易听懵。</p>

    <p v-if="config && !config.ttsServer" class="notice">需要服务端朗读才能播放不同口音，请在后端开启 TTS。</p>

    <section v-else-if="!started" class="block quiz__start">
      <label class="switch">
        <input v-model="includeSimulated" type="checkbox" />
        <span>包含模拟口音（日本、德国、法国、拉美）</span>
      </label>
      <p class="hint">每轮 {{ ROUNDS }} 题，每题四个选项。可以反复听。</p>
      <button class="btn btn--primary btn--lg" :disabled="pool.length < 4" @click="startGame">开始</button>
    </section>

    <section v-else-if="round < ROUNDS" class="block quiz__round">
      <div class="block__head">
        <span class="counter">第 {{ round + 1 }} / {{ ROUNDS }} 题 · 答对 {{ score }}</span>
        <PlayButton :id="`quiz-${round}`" :text="q.sentence" :env="accentEnv(q.answer)" label="再听一遍" />
      </div>
      <p v-if="answered" :class="['quiz__sentence', env.textClass]">{{ q.sentence }}</p>
      <div class="quiz__options">
        <button v-for="a in q.options" :key="a.key" :class="['quiz__option', optionClass(a.key)]" :disabled="answered"
          @click="choose(a.key)">
          {{ a.label }}<small v-if="a.simulated">模拟</small>
        </button>
      </div>
      <template v-if="answered">
        <p :class="['quiz__verdict', picked === q.answer.key ? 'good' : 'low']">
          {{ picked === q.answer.key ? '答对了！' : `是「${q.answer.label}」口音` }}
        </p>
        <div class="quiz__compare">
          <span class="muted">对比听：</span>
          <PlayButton v-for="a in q.options" :key="'c' + a.key" :id="`cmp-${round}-${a.key}`" :text="q.sentence"
            :env="accentEnv(a)" :label="a.label" />
        </div>
        <button class="btn btn--primary" @click="next">{{ round + 1 < ROUNDS ? '下一题' : '看结果' }}</button>
      </template>
    </section>

    <section v-else class="block quiz__done">
      <p class="overall__num">{{ score }}<small> / {{ ROUNDS }}</small></p>
      <p>{{ score >= 8 ? '耳朵很灵！' : score >= 5 ? '不错，多听几轮会更准。' : '口音听辨需要多听，把答错的几种口音多对比几次。' }}</p>
      <ul v-if="missed.length" class="list">
        <li v-for="(m, i) in missed" :key="i">把「{{ m.answer }}」听成了「{{ m.picked }}」</li>
      </ul>
      <button class="btn btn--primary" @click="startGame">再来一轮</button>
    </section>
  </div>
</template>

<script>
import { computed, ref } from 'vue'
import PlayButton from './PlayButton.vue'
import { play } from '../audio'

const ROUNDS = 10
const SENTENCES = [
  "Could you tell me how to get to the train station?",
  "I'm afraid the meeting has been moved to Thursday afternoon.",
  "We'd like to book a table for four at around eight.",
  "Have you had a chance to look at the report I sent?",
  "The weather here is lovely in the spring, but it rains a lot.",
  "Sorry, I didn't quite catch that. Could you say it again?",
  "I usually take the bus to work, but today I walked.",
  "Our new office is right next to the shopping centre.",
  "Can we schedule a quick call tomorrow morning?",
  "I think the price is a little higher than we expected.",
  "My flight was delayed, so I missed the first session.",
  "Let's grab a coffee after the presentation.",
  "Would you mind sending me the details by email?",
  "The restaurant on the corner does a great breakfast.",
  "I've been working here for about three years now.",
  "Please make sure the door is locked when you leave.",
]

const shuffle = (arr) => arr.map((v) => [Math.random(), v]).sort((a, b) => a[0] - b[0]).map((x) => x[1])

/** Listen to a sentence in a random English accent and pick which one it is. */
export default {
  name: 'AccentQuizView',
  components: { PlayButton },
  props: {
    config: { type: Object, default: null },
    env: { type: Object, required: true }, // English env
  },
  setup(props) {
    const includeSimulated = ref(false)
    const started = ref(false)
    const round = ref(0)
    const score = ref(0)
    const picked = ref(null)
    const missed = ref([])
    const questions = ref([])
    const answered = computed(() => picked.value !== null)
    const q = computed(() => questions.value[round.value])

    const pool = computed(() => (props.config?.languages.find((l) => l.code === 'en')?.accents || [])
      .filter((a) => a.key !== 'default' && (includeSimulated.value || !a.simulated)))
    const accentEnv = (a) => ({ ...props.env, accent: a.key, accentLocale: a.locale })

    function startGame() {
      const sentences = shuffle(SENTENCES)
      questions.value = Array.from({ length: ROUNDS }, (_, i) => {
        const answer = pool.value[Math.floor(Math.random() * pool.value.length)]
        const others = shuffle(pool.value.filter((a) => a.key !== answer.key)).slice(0, 3)
        return { sentence: sentences[i % sentences.length], answer, options: shuffle([answer, ...others]) }
      })
      started.value = true
      round.value = 0
      score.value = 0
      missed.value = []
      picked.value = null
      playCurrent()
    }

    function playCurrent() {
      const cur = q.value
      setTimeout(() => {
        play(`quiz-${round.value}`, cur.sentence, {
          language: 'en', rate: props.env.rate, accent: cur.answer.key, locale: cur.answer.locale,
        }).catch(() => {})
      }, 300)
    }

    function choose(key) {
      picked.value = key
      if (key === q.value.answer.key) score.value++
      else missed.value.push({ answer: q.value.answer.label, picked: q.value.options.find((o) => o.key === key).label })
    }

    function next() {
      round.value++
      picked.value = null
      if (round.value < ROUNDS) playCurrent()
    }

    const optionClass = (key) => {
      if (!answered.value) return ''
      if (key === q.value.answer.key) return 'right'
      return key === picked.value ? 'wrong' : ''
    }

    return { ROUNDS, includeSimulated, started, round, score, picked, missed, answered, q, pool, accentEnv, startGame, choose, next, optionClass }
  },
}
</script>
