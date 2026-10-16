<template>
  <section v-if="!myRole" class="block">
    <p v-if="content.scene" class="scene">{{ content.scene }}</p>
    <h2 class="block__title">你想扮演哪个角色？</h2>
    <div class="roles">
      <button v-for="r in content.roles" :key="r.id" class="role" @click="myRole = r.id">
        <strong :class="env.textClass">{{ r.name }}</strong>
        <span>{{ r.description }}</span>
      </button>
    </div>
    <p class="hint">对方的台词会自动朗读，轮到你时用语音说出你的台词。</p>
  </section>

  <section v-else class="chat">
    <p v-if="content.scene" class="scene">{{ content.scene }}</p>
    <div class="chat__mode">
      <span>我的台词：</span>
      <div class="seg seg--sm">
        <button :class="{ on: !free }" @click="free = false">照着说</button>
        <button :class="{ on: free }" @click="free = true">自由说</button>
      </div>
      <span class="muted">{{ free ? '只给中文意思，用自己的话回应' : '看着台词说，练发音和语调' }}</span>
    </div>

    <div v-for="(l, i) in shown" :key="l.id" :class="['bubble', l.role === myRole ? 'bubble--me' : 'bubble--ai']">
      <template v-if="l.role === myRole">
        <span class="bubble__who">你 · {{ roleName(l.role) }}</span>
        <template v-if="turnOf(l.id)">
          <p :class="['bubble__text', env.textClass]">{{ turnOf(l.id).answer }}</p>
          <DiffText v-if="turnOf(l.id).diff" :tokens="turnOf(l.id).diff.tokens" :env="env" />
          <PronBadge :turn="turnOf(l.id)" />
        </template>
        <template v-else-if="i === idx">
          <p v-if="free" class="translation">意思：{{ l.translation }}</p>
          <p v-else :class="['bubble__text', env.textClass]">{{ l.text }}</p>
          <p v-if="!free && env.showTranslation" class="translation">{{ l.translation }}</p>
        </template>
        <p v-else class="muted">（跳过）</p>
      </template>
      <template v-else>
        <span class="bubble__who">{{ roleName(l.role) }}</span>
        <div class="bubble__row">
          <PlayButton :id="l.id" :text="l.text" :env="env" :voice-index="voiceOf(l.role)" size="sm" @play="tracker.count(l.id)" />
          <TargetText :text="l.text" :env="env" cls="bubble__text" :revealed="!!revealed[l.id]" @reveal="revealed[l.id] = true" />
        </div>
        <p v-if="env.showTranslation" class="translation">{{ l.translation }}</p>
      </template>
    </div>

    <div v-if="current && current.role === myRole" class="chat__input">
      <AnswerBox :key="current.id" :env="env" submit-label="说完了，继续" :hands-free="env.handsFree" :listen-signal="listen"
        @submit="save" />
      <button class="link link--muted" @click="idx++">跳过这句</button>
    </div>
    <p v-if="current && current.role !== myRole" class="hint">
      对方正在说…<button class="link" @click="skipAi">跳过</button>
    </p>
    <p v-if="!current" class="done-note">对话结束了，点右侧“结束并评分”查看报告。</p>
    <div ref="bottom" />
  </section>
</template>

<script>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import AnswerBox from './AnswerBox.vue'
import DiffText from './DiffText.vue'
import PronBadge from './PronBadge.vue'
import PlayButton from './PlayButton.vue'
import TargetText from './TargetText.vue'
import { play, stop } from '../audio'
import { diffReference } from '../diff'

export default {
  name: 'DialoguePractice',
  components: { AnswerBox, DiffText, PlayButton, PronBadge, TargetText },
  props: {
    content: { type: Object, required: true },
    env: { type: Object, required: true },
    turns: { type: Array, required: true },
    tracker: { type: Object, required: true },
  },
  emits: ['add-turn'],
  setup(props, { emit }) {
    const revealed = reactive({})
    const myRole = ref(null)
    const idx = ref(0)
    const free = ref(false)
    const bottom = ref(null)
    const listen = ref(0) // bumped when it's the learner's line (hands-free)
    const lines = computed(() => props.content.lines.map((l, i) => ({ ...l, id: `l${i}` })))
    const shown = computed(() => lines.value.slice(0, Math.min(idx.value + 1, lines.value.length)))
    const current = computed(() => lines.value[idx.value])
    const roleName = (id) => props.content.roles.find((r) => r.id === id)?.name || id
    const voiceOf = (role) => (role === 'A' ? 0 : 1)
    const turnOf = (id) => props.turns.find((t) => t.id === id)
    let timer

    // the other side's lines play automatically, then the dialogue moves on
    watch([idx, myRole], () => {
      clearTimeout(timer)
      const line = current.value
      if (myRole.value && line && line.role === myRole.value) {
        nextTick(() => listen.value++) // the learner's line: start listening once the box is shown
        return
      }
      if (!myRole.value || !line) return
      const at = idx.value
      timer = setTimeout(() => {
        props.tracker.count(line.id)
        play(line.id, line.text, { language: props.env.language, rate: props.env.rate, voiceIndex: voiceOf(line.role) })
          .catch(() => {})
          .finally(() => { if (idx.value === at) idx.value++ })
      }, 400)
    })
    onBeforeUnmount(() => clearTimeout(timer))

    watch(() => [idx.value, props.turns.length], async () => {
      await nextTick()
      bottom.value?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' })
    })

    function prevAi(i) {
      for (let k = i - 1; k >= 0; k--) if (lines.value[k].role !== myRole.value) return lines.value[k]
      return null
    }

    function skipAi() {
      stop()
      idx.value++
    }

    function save(a) {
      const line = current.value
      const ai = prevAi(idx.value)
      emit('add-turn', {
        id: line.id, kind: 'line', prompt: ai?.text || '', reference: line.text, freeResponse: free.value, ...a,
        diff: free.value ? null : diffReference(line.text, a.answer, props.env.language),
        plays: ai ? props.tracker.plays[ai.id] || 0 : 0,
        textHidden: Boolean(ai && props.env.hideText && !revealed[ai.id]),
      })
      idx.value++
    }

    return { listen, revealed, myRole, idx, free, bottom, shown, current, roleName, voiceOf, turnOf, skipAi, save }
  },
}
</script>
