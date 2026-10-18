<template>
  <div class="chatmode">
    <section class="card chat-brief">
      <p v-if="content.scene" class="scene"><AppIcon name="info" :size="16" /> {{ content.scene }}</p>
      <div class="chat-brief__roles">
        <div class="chat-brief__role"><AvatarFigure variant="a" :size="44" /><span><small class="muted">对方</small><strong :class="env.textClass">{{ aiRole.name }}</strong><span class="muted">{{ aiRole.description }}</span></span></div>
        <div class="chat-brief__role"><AvatarFigure variant="b" :size="44" /><span><small class="muted">你</small><strong :class="env.textClass">{{ userRole.name }}</strong><span class="muted">{{ userRole.description }}</span></span></div>
      </div>
      <p v-if="content.goal" class="chat-brief__goal"><AppIcon name="flag" :size="16" /> 你的目标：{{ content.goal }}</p>
    </section>

    <section class="card dlg">
      <div class="dlg__log">
        <div v-for="(m, i) in st.messages" :key="m.id" :class="['msg', m.role === 'ai' ? 'msg--ai' : 'msg--me']">
          <AvatarFigure :variant="m.role === 'ai' ? 'a' : 'b'" :size="44" />
          <div class="msg__col">
            <div class="msg__bubble">
              <template v-if="m.role === 'ai'">
                <PlayButton :id="m.id" :text="m.text" :env="env" :voice-index="env.voiceIndex" size="sm" @play="tracker.count(m.id)" />
                <TargetText :text="m.text" :env="env" :revealed="!!revealed[m.id] || i < st.messages.length - 1" @reveal="revealed[m.id] = true" />
              </template>
              <p v-else :class="env.textClass">{{ m.text }}</p>
            </div>
            <span class="msg__meta">{{ m.role === 'ai' ? aiRole.name : '你' }}</span>
          </div>
        </div>
        <p v-if="thinking" class="hint thinking"><span class="dots" aria-hidden="true"><i /><i /><i /></span>{{ aiRole.name }} 正在想怎么回…</p>
        <p v-if="error" class="error">{{ error }} <button type="button" class="link" @click="askAgain">重试</button></p>
        <div ref="bottom" />
      </div>

      <div v-if="!st.ended && !thinking && !error && lastIsAi" class="dlg__input">
        <AnswerBox :key="'c' + userCount" compact :env="env" submit-label="发送" :hands-free="env.handsFree" :listen-signal="listen"
          placeholder="点击录音，说出你的回答…" @submit="send" />
        <button type="button" class="link link--muted" @click="st.ended = true">结束对话</button>
      </div>
      <p v-if="st.ended" class="done-note">
        <AppIcon name="check-circle" /> {{ st.naturalEnd ? '对话自然结束了。' : '对话已结束。' }}点“结束并评分”查看报告（共 {{ userCount }} 轮）。
      </p>
    </section>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, inject, nextTick, onMounted, ref, watch, type PropType } from 'vue'
import AnswerBox, { type AnswerPayload } from './AnswerBox.vue'
import AppIcon from '../ui/AppIcon.vue'
import AvatarFigure from '../ui/AvatarFigure.vue'
import PlayButton from '../ui/PlayButton.vue'
import TargetText from '../ui/TargetText.vue'
import { api } from '../../api'
import type { Content, Env, Turn } from '../../api/models'
import { play } from '../../lib/audio'
import { SESSION_ID, useModeState, useRevealed } from '../../lib/practice'

interface Msg { id: string; role: 'ai' | 'user'; text: string }
interface CState { messages: Msg[]; ended: boolean; naturalEnd: boolean; summary: string }

/** Open-ended conversation: the AI stays in role and answers whatever the learner says. */
export default defineComponent({
  name: 'ChatPractice',
  components: { AnswerBox, AppIcon, AvatarFigure, PlayButton, TargetText },
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
    const st = useModeState<CState>('chat', {
      messages: [{ id: 'ai0', role: 'ai', text: props.content.opening || '' }], ended: false, naturalEnd: false, summary: '',
    })
    const aiRole = computed(() => props.content.aiRole || { id: 'ai', name: 'AI' })
    const userRole = computed(() => props.content.userRole || { id: 'me', name: '你' })
    const thinking = ref(false)
    const error = ref('')
    const listen = ref(0)
    const bottom = ref<HTMLElement | null>(null)
    const userCount = computed(() => st.messages.filter((m) => m.role === 'user').length)
    const lastIsAi = computed(() => st.messages[st.messages.length - 1]?.role === 'ai')

    function speak(m: Msg) {
      props.tracker.count(m.id)
      play(m.id, m.text, {
        language: props.env.language, rate: props.env.rate, voiceIndex: props.env.voiceIndex,
        accent: props.env.accent || 'default', locale: props.env.accentLocale || null,
      })
        .catch(() => {})
        .finally(() => { if (st.messages[st.messages.length - 1]?.id === m.id && !st.ended) listen.value++ })
    }
    onMounted(() => {
      if (!lastIsAi.value && !st.ended) askAgain() // resumed before the AI had replied
      else if (st.messages.length === 1) setTimeout(() => speak(st.messages[0]), 400)
    })

    async function askAgain() {
      error.value = ''
      thinking.value = true
      try {
        const history = st.messages.map((m) => ({ role: m.role, text: m.text }))
        const r = await api.chatReply({ sessionId, history, summary: st.summary })
        const m: Msg = { id: `ai${st.messages.length}`, role: 'ai', text: r.text }
        st.messages = [...st.messages, m]
        if (r.summary) st.summary = r.summary // older rounds travel as this one-line summary
        if (r.end) { st.ended = true; st.naturalEnd = true }
        speak(m)
      } catch (e: any) {
        error.value = e.message
      } finally {
        thinking.value = false
      }
    }

    function send(a: AnswerPayload) {
      const lastAi = [...st.messages].reverse().find((m) => m.role === 'ai')
      const n = userCount.value
      st.messages = [...st.messages, { id: `u${n}`, role: 'user', text: a.answer }]
      emit('add-turn', {
        id: `c${n}`, kind: 'answer', prompt: lastAi?.text || '', ...a,
        plays: (lastAi && props.tracker.plays[lastAi.id]) || 0,
        textHidden: Boolean(lastAi && props.env.hideText && !revealed[lastAi.id]),
      })
      askAgain()
    }

    watch(() => st.messages.length + (thinking.value ? 0.5 : 0), async () => {
      await nextTick()
      bottom.value?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' })
    })

    return { st, revealed, aiRole, userRole, thinking, error, listen, bottom, userCount, lastIsAi, send, askAgain }
  },
})
</script>
