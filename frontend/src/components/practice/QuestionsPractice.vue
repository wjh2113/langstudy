<template>
  <div class="qa">
    <p v-if="content.intro" class="scene"><AppIcon name="info" :size="16" /> {{ content.intro }}</p>

    <section v-if="history.length" class="card qa-done">
      <h2 class="card__title"><AppIcon name="history" /> 已答问题</h2>
      <div v-for="g in history" :key="g.i" :class="['qa-row', { open: openRow === g.i }]">
        <button type="button" class="qa-row__head" :aria-expanded="openRow === g.i" @click="openRow = openRow === g.i ? -1 : g.i">
          <span class="qa-row__no">Q{{ g.i + 1 }}</span>
          <span :class="['qa-row__q', env.textClass]">{{ g.main.prompt }}</span>
          <span class="pill pill--muted">已答</span>
          <span class="qa-row__a"><span class="muted">你的回答：</span><span :class="env.textClass">{{ g.main.answer }}</span></span>
          <AppIcon :name="openRow === g.i ? 'chevron-up' : 'chevron-down'" :size="18" />
        </button>
        <div v-if="openRow === g.i" class="qa-row__body">
          <AnsweredCard :turn="g.main" :env="env" />
          <div v-if="g.follow" class="qa-follow">
            <p :class="['qa-follow__q', env.textClass]"><span class="tag tag--ai"><AppIcon name="sparkle" :size="12" /> 追问</span> {{ g.follow.prompt }}</p>
            <AnsweredCard :turn="g.follow" :env="env" />
          </div>
        </div>
      </div>
    </section>

    <section v-if="question" class="card qa-current">
      <div class="qa-current__head">
        <span class="q-badge">Q{{ st.idx + 1 }}</span>
        <TargetText :text="question.text" :env="env" cls="q-text" wrap-cls="qa-current__text" :revealed="!!revealed[mainId]"
          @reveal="revealed[mainId] = true" />
        <PlayButton :id="mainId" :text="question.text" :env="env" label="再听一遍" @play="tracker.count(mainId)" />
      </div>
      <p v-if="question.tip && st.stage === 'main'" class="tip">
        <AppIcon name="bulb" :size="16" />
        <template v-if="showTip">答题思路：{{ question.tip }}</template>
        <button v-else type="button" class="link" @click="showTip = true">看看答题思路</button>
      </p>

      <div :class="['ai-box', { 'ai-box--active': st.stage !== 'main' }]">
        <div class="ai-box__head">
          <AppIcon name="sparkle" :size="18" />
          <strong>AI 追问</strong>
          <ToggleSwitch :model-value="followOn" label="AI 追问" @update:model-value="setFollowOn" />
          <span v-if="st.stage === 'main'" class="muted ai-box__hint">{{ followOn ? '答完这题后，AI 会根据你的回答再追问一句' : '已关闭' }}</span>
        </div>
        <p v-if="st.stage === 'thinking'" class="thinking"><span class="dots" aria-hidden="true"><i /><i /><i /></span>正在根据你的回答想追问…
          <button type="button" class="link" @click="next">不用追问，下一题</button></p>
        <div v-else-if="st.stage === 'follow' && followUp" class="ai-box__q">
          <PlayButton :id="followId" :text="followUp.text" :env="env" size="sm" @play="tracker.count(followId)" />
          <TargetText :text="followUp.text" :env="env" cls="ai-box__text" :revealed="!!revealed[followId]" @reveal="revealed[followId] = true" />
        </div>
      </div>

      <AnswerBox v-if="st.stage !== 'thinking'" :key="promptId" :env="env" :hands-free="env.handsFree" :listen-signal="listen" @submit="save" />
      <div class="qa-current__foot">
        <button v-if="st.stage !== 'thinking'" type="button" class="link link--muted" @click="next">{{ st.stage === 'follow' ? '跳过追问' : '跳过这题' }}</button>
        <p v-if="followError" class="error">{{ followError }}</p>
      </div>
    </section>
    <p v-else class="done-note card"><AppIcon name="check-circle" /> 所有问题都答完了，点“结束并评分”查看报告。</p>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, inject, onBeforeUnmount, onMounted, ref, watch, type PropType } from 'vue'
import AnswerBox, { type AnswerPayload } from './AnswerBox.vue'
import AnsweredCard from './AnsweredCard.vue'
import AppIcon from '../ui/AppIcon.vue'
import PlayButton from '../ui/PlayButton.vue'
import TargetText from '../ui/TargetText.vue'
import ToggleSwitch from '../ui/ToggleSwitch.vue'
import { api } from '../../api'
import type { Content, Env, Turn } from '../../api/models'
import { play, stop } from '../../lib/audio'
import { SESSION_ID, useModeState, useRevealed } from '../../lib/practice'
import { read, save as saveLocal } from '../../lib/storage'

interface QState { idx: number; stage: 'main' | 'thinking' | 'follow'; followUps: Record<number, { text: string }> }

export default defineComponent({
  name: 'QuestionsPractice',
  components: { AnswerBox, AnsweredCard, AppIcon, PlayButton, TargetText, ToggleSwitch },
  props: {
    content: { type: Object as PropType<Content>, required: true },
    env: { type: Object as PropType<Env>, required: true },
    turns: { type: Array as PropType<Turn[]>, required: true },
    tracker: { type: Object as PropType<{ plays: Record<string, number>; count: (id: string) => void }>, required: true },
  },
  emits: ['add-turn'],
  setup(props, { emit }) {
    const sessionId = inject(SESSION_ID) as string
    const revealed = useRevealed()
    const st = useModeState<QState>('questions', { idx: 0, stage: 'main', followUps: {} })
    const questions = computed(() => props.content.questions || [])
    const showTip = ref(false)
    const followOn = ref(read('ls.followup') !== '0')
    const followError = ref('')
    const listen = ref(0) // bumped when the question has been read out (hands-free)
    const openRow = ref(-1)
    let timer: ReturnType<typeof setTimeout> | undefined

    const turnOf = (id: string) => props.turns.find((t) => t.id === id)
    const question = computed(() => questions.value[st.idx] || null)
    const mainId = computed(() => `q${st.idx}`)
    const followId = computed(() => `q${st.idx}-f`)
    const followUp = computed(() => st.followUps[st.idx] || null)
    const promptId = computed(() => (st.stage === 'follow' ? followId.value : mainId.value))

    const history = computed(() => {
      const out: { i: number; main: Turn; follow?: Turn }[] = []
      questions.value.forEach((_, i) => {
        const main = turnOf(`q${i}`)
        if (main && !(i === st.idx && st.stage !== 'main')) out.push({ i, main, follow: turnOf(`q${i}-f`) })
      })
      return out
    })

    // read each new question / follow-up aloud when it appears
    function speakCurrent() {
      clearTimeout(timer)
      showTip.value = false
      if (!question.value || st.stage === 'thinking') return
      const id = promptId.value
      const text = st.stage === 'follow' ? followUp.value?.text : question.value.text
      if (!text) return
      timer = setTimeout(() => {
        props.tracker.count(id)
        play(id, text, { language: props.env.language, rate: props.env.rate })
          .catch(() => {})
          .finally(() => { if (promptId.value === id) listen.value++ }) // your turn
      }, 350)
    }
    watch(promptId, speakCurrent)
    onMounted(() => {
      // resumed while a follow-up was being generated: ask again
      const main = turnOf(mainId.value)
      if (st.stage === 'thinking' && main) askFollowUp(st.idx, main.prompt || '', main.answer || '')
      else if (st.stage === 'follow' && !followUp.value) st.stage = 'main'
      speakCurrent()
    })
    onBeforeUnmount(() => clearTimeout(timer))

    function setFollowOn(on: boolean) {
      followOn.value = on
      saveLocal('ls.followup', on ? '1' : '0')
    }

    function next() {
      stop()
      st.stage = 'main'
      st.idx++
    }

    async function askFollowUp(i: number, questionText: string, answer: string) {
      st.stage = 'thinking'
      followError.value = ''
      const pairs: { q: string; a: string }[] = []
      for (const g of history.value) {
        if (g.i === i) continue
        pairs.push({ q: g.main.prompt || '', a: g.main.answer || '' })
        if (g.follow) pairs.push({ q: g.follow.prompt || '', a: g.follow.answer || '' })
      }
      try {
        const r = await api.followup({ sessionId, question: questionText, answer, history: pairs })
        if (st.idx !== i || st.stage !== 'thinking') return // learner moved on
        st.followUps = { ...st.followUps, [i]: { text: r.text } }
        st.stage = 'follow'
      } catch (e: any) {
        if (st.idx !== i || st.stage !== 'thinking') return
        followError.value = `没能生成追问（${e.message}），已进入下一题`
        next()
      }
    }

    function save(a: AnswerPayload) {
      stop()
      const isFollow = st.stage === 'follow'
      const id = promptId.value
      const text = isFollow ? followUp.value?.text || '' : question.value?.text || ''
      const i = st.idx
      emit('add-turn', {
        id, kind: 'answer', prompt: text, followUp: isFollow, ...a,
        plays: props.tracker.plays[id] || 0, textHidden: props.env.hideText && !revealed[id],
      })
      followError.value = ''
      if (!isFollow && followOn.value) askFollowUp(i, text, a.answer)
      else next()
    }

    return { st, revealed, question, mainId, followId, followUp, promptId, history, listen, showTip, followOn, followError, openRow, setFollowOn, next, save }
  },
})
</script>
