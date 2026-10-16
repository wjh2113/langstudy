<template>
  <p v-if="content.intro" class="scene">{{ content.intro }}</p>
  <label class="switch">
    <input type="checkbox" :checked="followOn" @change="setFollowOn($event.target.checked)" />
    <span>AI 追问：每题答完后，根据你的回答再追问一句</span>
  </label>

  <div v-for="g in history" :key="g.i" class="qa-done">
    <p :class="['qa-done__q', env.textClass]">{{ g.main.prompt }}</p>
    <AnsweredCard :turn="g.main" :env="env" />
    <div v-if="g.follow" class="qa-follow">
      <p :class="['qa-done__q', env.textClass]"><span class="tag">追问</span> {{ g.follow.prompt }}</p>
      <AnsweredCard :turn="g.follow" :env="env" />
    </div>
  </div>

  <section v-if="stage === 'thinking'" class="block block--current">
    <p class="hint thinking"><span class="dots" aria-hidden="true"><i /><i /><i /></span>正在根据你的回答想追问…</p>
    <button class="link link--muted" @click="next">不用追问，下一题</button>
  </section>

  <section v-else-if="prompt" class="block block--current">
    <div class="block__head">
      <span class="counter">
        第 {{ idx + 1 }} / {{ content.questions.length }} 题<template v-if="prompt.isFollow"> · <span class="tag">追问</span></template>
      </span>
      <PlayButton :id="prompt.id" :text="prompt.text" :env="env" label="再听一遍" @play="tracker.count(prompt.id)" />
    </div>
    <TargetText :text="prompt.text" :env="env" cls="question__text question__text--lg" :revealed="!!revealed[prompt.id]"
      @reveal="revealed[prompt.id] = true" />
    <p v-if="env.showTranslation && prompt.translation" class="translation">{{ prompt.translation }}</p>
    <p v-if="prompt.tip" class="tip">
      <template v-if="showTip">答题思路：{{ prompt.tip }}</template>
      <button v-else class="link" @click="showTip = true">看看答题思路</button>
    </p>
    <AnswerBox :key="prompt.id" :env="env" @submit="save" />
    <button class="link link--muted" @click="next">{{ prompt.isFollow ? '跳过追问' : '跳过这题' }}</button>
    <p v-if="followError" class="error">{{ followError }}</p>
  </section>
  <p v-else class="done-note">所有问题都答完了，点右侧“结束并评分”查看报告。</p>
</template>

<script>
import { computed, inject, onBeforeUnmount, reactive, ref, watch } from 'vue'
import AnswerBox from './AnswerBox.vue'
import AnsweredCard from './AnsweredCard.vue'
import PlayButton from './PlayButton.vue'
import TargetText from './TargetText.vue'
import { api } from '../api'
import { play, stop } from '../audio'

function loadFollowOn() {
  try { return localStorage.getItem('ls.followup') !== '0' } catch { return true }
}

export default {
  name: 'QuestionsPractice',
  components: { AnswerBox, AnsweredCard, PlayButton, TargetText },
  props: {
    content: { type: Object, required: true },
    env: { type: Object, required: true },
    turns: { type: Array, required: true },
    tracker: { type: Object, required: true },
  },
  emits: ['add-turn'],
  setup(props, { emit }) {
    const sessionId = inject('sessionId')
    const revealed = reactive({})
    const followUps = reactive({}) // question index -> { text, translation }
    const idx = ref(0)
    const stage = ref('main') // main | thinking | follow
    const showTip = ref(false)
    const followOn = ref(loadFollowOn())
    const followError = ref('')
    let timer

    const turnOf = (id) => props.turns.find((t) => t.id === id)

    /** What the learner should answer right now. */
    const prompt = computed(() => {
      const q = props.content.questions[idx.value]
      if (!q) return null
      if (stage.value === 'follow') {
        const f = followUps[idx.value]
        return { id: `q${idx.value}-f`, text: f.text, translation: f.translation, tip: '', isFollow: true }
      }
      return { id: `q${idx.value}`, text: q.text, translation: q.translation, tip: q.tip, isFollow: false }
    })

    /** Finished questions, each with its follow-up if there was one. */
    const history = computed(() => {
      const out = []
      for (let i = 0; i < props.content.questions.length; i++) {
        const main = turnOf(`q${i}`)
        if (!main) continue
        out.push({ i, main, follow: turnOf(`q${i}-f`) })
      }
      return out
    })

    // read each new question / follow-up aloud when it appears
    watch(() => prompt.value?.id, (id) => {
      clearTimeout(timer)
      showTip.value = false
      if (!id) return
      const text = prompt.value.text
      timer = setTimeout(() => {
        props.tracker.count(id)
        play(id, text, { language: props.env.language, rate: props.env.rate }).catch(() => {})
      }, 350)
    }, { immediate: true })
    onBeforeUnmount(() => clearTimeout(timer))

    function setFollowOn(on) {
      followOn.value = on
      try { localStorage.setItem('ls.followup', on ? '1' : '0') } catch { /* ignore */ }
    }

    function next() {
      stop()
      stage.value = 'main'
      idx.value++
    }

    async function askFollowUp(i, question, answer) {
      stage.value = 'thinking'
      followError.value = ''
      const pairs = []
      for (const g of history.value) {
        if (g.i === i) continue
        pairs.push({ q: g.main.prompt, a: g.main.answer })
        if (g.follow) pairs.push({ q: g.follow.prompt, a: g.follow.answer })
      }
      try {
        const r = await api.followup({ sessionId, question, answer, history: pairs })
        if (idx.value !== i || stage.value !== 'thinking') return // learner moved on
        followUps[i] = r
        stage.value = 'follow'
      } catch (e) {
        if (idx.value !== i || stage.value !== 'thinking') return
        followError.value = `没能生成追问（${e.message}），已进入下一题`
        next()
      }
    }

    function save(a) {
      stop()
      const p = prompt.value
      const i = idx.value
      emit('add-turn', {
        id: p.id, kind: 'answer', prompt: p.text, followUp: p.isFollow, ...a,
        plays: props.tracker.plays[p.id] || 0, textHidden: props.env.hideText && !revealed[p.id],
      })
      followError.value = ''
      if (!p.isFollow && followOn.value) askFollowUp(i, p.text, a.answer)
      else next()
    }

    return { revealed, idx, stage, showTip, followOn, followError, prompt, history, setFollowOn, next, save }
  },
}
</script>
