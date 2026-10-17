<template>
  <div class="dialogue">
    <section class="dlg-roles">
      <h2 class="section-title">{{ st.myRole ? '你的角色' : '1. 选择角色' }}</h2>
      <p v-if="content.scene" class="scene"><AppIcon name="info" :size="16" /> {{ content.scene }}</p>
      <div class="role-cards">
        <button v-for="r in roles" :key="r.id" type="button" :class="['role-card', { on: st.myRole === r.id }]"
          :disabled="Boolean(st.myRole) && turnsStarted" :aria-pressed="st.myRole === r.id" @click="chooseRole(r.id)">
          <AvatarFigure :variant="r.id === 'A' ? 'a' : 'b'" :size="72" />
          <span class="role-card__text">
            <strong :class="env.textClass">{{ r.name }}</strong>
            <span>{{ r.description }}</span>
          </span>
          <span v-if="st.myRole === r.id" class="role-card__check"><AppIcon name="check" :size="14" :stroke="3" /></span>
        </button>
      </div>
      <p v-if="!st.myRole" class="hint">对方的台词会自动朗读，轮到你时用语音说出你的台词。</p>
    </section>

    <section v-if="st.myRole" class="card dlg">
      <div class="radio-pills" role="radiogroup" aria-label="我的台词">
        <button type="button" role="radio" :aria-checked="!st.free" :class="{ on: !st.free }" @click="st.free = false"><span class="radio" />照着说</button>
        <button type="button" role="radio" :aria-checked="st.free" :class="{ on: st.free }" @click="st.free = true"><span class="radio" />自由说</button>
        <span class="muted">{{ st.free ? '只给中文意思，用自己的话回应' : '看着台词说，练发音和语调' }}</span>
      </div>

      <div class="dlg__log">
        <div v-for="l in shown" :key="l.id" :class="['msg', l.role === st.myRole ? 'msg--me' : 'msg--ai']">
          <AvatarFigure :variant="l.role === 'A' ? 'a' : 'b'" :size="44" />
          <div class="msg__col">
            <div class="msg__bubble">
              <template v-if="l.role === st.myRole">
                <template v-if="turnOf(l.id)">
                  <p :class="env.textClass">{{ turnOf(l.id)?.answer }}</p>
                </template>
                <template v-else-if="l.idx === st.idx">
                  <div v-if="st.free" class="msg__hint"><span class="muted">意思：</span><TranslationLine :text="l.text" :language="env.language" /></div>
                  <TargetText v-else :text="l.text" :env="env" :revealed="true" />
                </template>
                <p v-else class="muted">（跳过）</p>
              </template>
              <template v-else>
                <PlayButton :id="l.id" :text="l.text" :env="env" :voice-index="voiceOf(l.role)" size="sm" @play="tracker.count(l.id)" />
                <TargetText :text="l.text" :env="env" :revealed="!!revealed[l.id]" @reveal="revealed[l.id] = true" />
              </template>
            </div>
            <span class="msg__meta">{{ l.role === st.myRole ? '你 · ' : '' }}{{ roleName(l.role) }}</span>
          </div>
        </div>
        <p v-if="current && current.role !== st.myRole" class="hint thinking">
          <span class="dots" aria-hidden="true"><i /><i /><i /></span>对方正在说…<button type="button" class="link" @click="skipAi">跳过</button>
        </p>
        <div ref="bottom" />
      </div>

      <div v-if="lastMine" class="shadow-card">
        <span class="shadow-card__icon"><AppIcon name="wave" /></span>
        <div class="shadow-card__body">
          <div class="shadow-card__head">
            <strong>跟读结果</strong>
            <PronBadge :turn="lastMine" />
          </div>
          <DiffText v-if="lastMine.diff" :tokens="lastMine.diff.tokens" :env="env" />
          <p v-else :class="env.textClass">{{ lastMine.answer }}</p>
        </div>
      </div>

      <div v-if="current && current.role === st.myRole" class="dlg__input">
        <AnswerBox :key="current.id" compact :env="env" submit-label="提交" :hands-free="env.handsFree" :listen-signal="listen"
          :placeholder="st.free ? '用自己的话回应，点击录音开始…' : '点击录音，开始你的朗读…'" @submit="save" />
        <button type="button" class="link link--muted" @click="st.idx++">跳过这句</button>
      </div>
      <p v-if="!current" class="done-note"><AppIcon name="check-circle" /> 对话结束了，点“结束并评分”查看报告。</p>
    </section>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, nextTick, onBeforeUnmount, onMounted, ref, watch, type PropType } from 'vue'
import AnswerBox, { type AnswerPayload } from './AnswerBox.vue'
import AppIcon from '../ui/AppIcon.vue'
import AvatarFigure from '../ui/AvatarFigure.vue'
import DiffText from '../ui/DiffText.vue'
import PlayButton from '../ui/PlayButton.vue'
import PronBadge from '../ui/PronBadge.vue'
import TargetText from '../ui/TargetText.vue'
import TranslationLine from '../ui/TranslationLine.vue'
import type { Content, Env, Turn } from '../../api/models'
import { play, stop } from '../../lib/audio'
import { diffReference } from '../../lib/diff'
import { useModeState, useRevealed } from '../../lib/practice'

interface DState { myRole: string | null; idx: number; free: boolean }

export default defineComponent({
  name: 'DialoguePractice',
  components: { AnswerBox, AppIcon, AvatarFigure, DiffText, PlayButton, PronBadge, TargetText, TranslationLine },
  props: {
    content: { type: Object as PropType<Content>, required: true },
    env: { type: Object as PropType<Env>, required: true },
    turns: { type: Array as PropType<Turn[]>, required: true },
    tracker: { type: Object as PropType<{ plays: Record<string, number>; count: (id: string) => void }>, required: true },
  },
  emits: ['add-turn'],
  setup(props, { emit }) {
    const revealed = useRevealed()
    const st = useModeState<DState>('dialogue', { myRole: null, idx: 0, free: false })
    const bottom = ref<HTMLElement | null>(null)
    const listen = ref(0) // bumped when it's the learner's line (hands-free)
    const roles = computed(() => props.content.roles || [])
    const lines = computed(() => (props.content.lines || []).map((l, i) => ({ ...l, id: `l${i}`, idx: i })))
    const shown = computed(() => lines.value.slice(0, Math.min(st.idx + 1, lines.value.length)))
    const current = computed(() => lines.value[st.idx])
    const roleName = (id: string) => roles.value.find((r) => r.id === id)?.name || id
    // Voice lists are [female, male]. Avatar A wears a tie, avatar B has long hair.
    const voiceOf = (role: string) => (role === 'A' ? 1 : 0)
    const turnOf = (id: string) => props.turns.find((t) => t.id === id)
    const turnsStarted = computed(() => props.turns.length > 0)
    const lastMine = computed(() => [...props.turns].reverse().find((t) => t.kind === 'line') || null)
    let timer: ReturnType<typeof setTimeout> | undefined

    function chooseRole(id: string) {
      if (turnsStarted.value) return
      st.myRole = id
    }

    // the other side's lines play automatically, then the dialogue moves on
    function advance() {
      clearTimeout(timer)
      const line = current.value
      if (!st.myRole || !line) return
      if (line.role === st.myRole) {
        nextTick(() => listen.value++) // the learner's line: start listening once the box is shown
        return
      }
      const at = st.idx
      timer = setTimeout(() => {
        props.tracker.count(line.id)
        play(line.id, line.text, {
          language: props.env.language, rate: props.env.rate, voiceIndex: voiceOf(line.role),
          accent: props.env.accent || 'default', locale: props.env.accentLocale || null,
        })
          .catch(() => {})
          .finally(() => { if (st.idx === at) st.idx++ })
      }, 400)
    }
    watch(() => [st.idx, st.myRole], advance)
    onMounted(advance) // resuming mid-dialogue
    onBeforeUnmount(() => clearTimeout(timer))

    watch(() => [st.idx, props.turns.length], async () => {
      await nextTick()
      bottom.value?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' })
    })

    function prevAi(i: number) {
      for (let k = i - 1; k >= 0; k--) if (lines.value[k].role !== st.myRole) return lines.value[k]
      return null
    }

    function skipAi() {
      stop()
      st.idx++
    }

    function save(a: AnswerPayload) {
      const line = current.value
      const ai = prevAi(st.idx)
      emit('add-turn', {
        id: line.id, kind: 'line', prompt: ai?.text || '', reference: line.text, freeResponse: st.free, ...a,
        diff: st.free ? null : diffReference(line.text, a.answer, props.env.language),
        plays: ai ? props.tracker.plays[ai.id] || 0 : 0,
        textHidden: Boolean(ai && props.env.hideText && !revealed[ai.id]),
      })
      st.idx++
    }

    return { st, revealed, bottom, listen, roles, shown, current, roleName, voiceOf, turnOf, turnsStarted, lastMine, chooseRole, skipAi, save }
  },
})
</script>
