<template>
  <section class="chat">
    <div class="chat-brief">
      <p v-if="content.scene" class="scene">{{ content.scene }}</p>
      <p class="chat-brief__roles">
        <span>对方：<strong :class="env.textClass">{{ content.aiRole.name }}</strong> <span class="muted">{{ content.aiRole.description }}</span></span>
        <span>你：<strong :class="env.textClass">{{ content.userRole.name }}</strong> <span class="muted">{{ content.userRole.description }}</span></span>
      </p>
      <p v-if="content.goal" class="chat-brief__goal">你的目标：{{ content.goal }}</p>
    </div>

    <div v-for="(m, i) in messages" :key="m.id" :class="['bubble', m.role === 'ai' ? 'bubble--ai' : 'bubble--me']">
      <span class="bubble__who">{{ m.role === 'ai' ? content.aiRole.name : '你' }}</span>
      <template v-if="m.role === 'ai'">
        <div class="bubble__row">
          <PlayButton :id="m.id" :text="m.text" :env="env" size="sm" @play="tracker.count(m.id)" />
          <TargetText :text="m.text" :env="env" cls="bubble__text" :revealed="!!revealed[m.id] || i < messages.length - 1"
            @reveal="revealed[m.id] = true" />
        </div>
        <p v-if="env.showTranslation && m.translation" class="translation">{{ m.translation }}</p>
      </template>
      <p v-else :class="['bubble__text', env.textClass]">{{ m.text }}</p>
    </div>

    <p v-if="thinking" class="hint thinking"><span class="dots" aria-hidden="true"><i /><i /><i /></span>{{ content.aiRole.name }} 正在想怎么回…</p>
    <p v-if="error" class="error">{{ error }} <button class="link" @click="askAgain">重试</button></p>

    <div v-if="!ended && !thinking && !error" class="chat__input">
      <AnswerBox :key="'c' + userCount" :env="env" submit-label="发送" :hands-free="env.handsFree" :listen-signal="listen"
        @submit="send" />
      <button class="link link--muted" @click="ended = true">结束对话</button>
    </div>
    <p v-if="ended" class="done-note">
      {{ naturalEnd ? '对话自然结束了。' : '对话已结束。' }}点右侧“结束并评分”查看报告（共 {{ userCount }} 轮）。
    </p>
    <div ref="bottom" />
  </section>
</template>

<script>
import { computed, inject, nextTick, onMounted, reactive, ref, watch } from 'vue'
import AnswerBox from './AnswerBox.vue'
import PlayButton from './PlayButton.vue'
import TargetText from './TargetText.vue'
import { api } from '../api'
import { play } from '../audio'

/** Open-ended conversation: the AI stays in role and answers whatever the learner says. */
export default {
  name: 'ChatPractice',
  components: { AnswerBox, PlayButton, TargetText },
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
    const messages = ref([{ id: 'ai0', role: 'ai', text: props.content.opening, translation: props.content.openingTranslation }])
    const thinking = ref(false)
    const ended = ref(false)
    const naturalEnd = ref(false)
    const error = ref('')
    const listen = ref(0)
    const bottom = ref(null)
    const userCount = computed(() => messages.value.filter((m) => m.role === 'user').length)

    function speak(m) {
      props.tracker.count(m.id)
      play(m.id, m.text, { language: props.env.language, rate: props.env.rate })
        .catch(() => {})
        .finally(() => { if (messages.value.at(-1)?.id === m.id && !ended.value) listen.value++ })
    }
    onMounted(() => setTimeout(() => speak(messages.value[0]), 400))

    async function askAgain() {
      error.value = ''
      thinking.value = true
      try {
        const history = messages.value.map((m) => ({ role: m.role, text: m.text }))
        const r = await api.chatReply({ sessionId, history })
        const m = { id: `ai${messages.value.length}`, role: 'ai', text: r.text, translation: r.translation }
        messages.value = [...messages.value, m]
        if (r.end) { ended.value = true; naturalEnd.value = true }
        speak(m)
      } catch (e) {
        error.value = e.message
      } finally {
        thinking.value = false
      }
    }

    function send(a) {
      const lastAi = [...messages.value].reverse().find((m) => m.role === 'ai')
      const n = userCount.value
      messages.value = [...messages.value, { id: `u${n}`, role: 'user', text: a.answer }]
      emit('add-turn', {
        id: `c${n}`, kind: 'answer', prompt: lastAi?.text || '', ...a,
        plays: props.tracker.plays[lastAi?.id] || 0,
        textHidden: Boolean(lastAi && props.env.hideText && !revealed[lastAi.id]),
      })
      askAgain()
    }

    watch(() => messages.value.length + (thinking.value ? 0.5 : 0), async () => {
      await nextTick()
      bottom.value?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' })
    })

    return { revealed, messages, thinking, ended, naturalEnd, error, listen, bottom, userCount, send, askAgain }
  },
}
</script>
