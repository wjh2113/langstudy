<template>
  <div class="practice" :data-lang="env.language">
    <header class="practice__head">
      <p class="crumbs">
        {{ modeNames[content.mode] }} / {{ content.topic }}
        <span v-if="content.focus" class="tag tag--sm">专项：{{ content.focus.name }}</span>
      </p>
      <h1 :class="['practice__title', env.textClass]">{{ content.title }}</h1>
      <p v-if="content.titleTranslation" class="muted">{{ content.titleTranslation }}</p>
    </header>

    <div class="practice__body">
      <main class="practice__main">
        <nav class="page-tabs" role="tablist">
          <button role="tab" :aria-selected="tab === 'practice'" :class="{ on: tab === 'practice' }" @click="tab = 'practice'">练习</button>
          <button role="tab" :aria-selected="tab === 'notes'" :class="{ on: tab === 'notes' }" @click="openNotes">学习笔记</button>
        </nav>
        <div v-show="tab === 'practice'" class="practice__flow">
          <component :is="modeComponent" :content="content" :env="env" :turns="turns" :tracker="tracker" @add-turn="addTurn" />
        </div>
        <StudyNotes v-if="notesOpened" v-show="tab === 'notes'" :session-id="session.id" :env="env" />
      </main>

      <aside class="panel" aria-label="练习设置">
        <div class="panel__group">
          <span class="panel__label">语速</span>
          <div class="seg seg--sm">
            <button v-for="r in [0.8, 1, 1.2]" :key="r" :class="{ on: env.rate === r }" @click="setDisplay({ rate: r })">{{ r }}×</button>
          </div>
        </div>
        <div v-if="env.accents.length > 1" class="panel__group">
          <span class="panel__label">听力口音</span>
          <AccentSelect :accents="env.accents" :model-value="env.accent" @update:model-value="(k) => $emit('update:accent', k)" />
        </div>
        <label v-if="['questions', 'dialogue', 'chat'].includes(content.mode)" class="switch">
          <input type="checkbox" :checked="env.handsFree" @change="setDisplay({ handsFree: $event.target.checked })" />
          <span>免手动：自动开麦、停顿自动提交</span>
        </label>
        <label class="switch">
          <input type="checkbox" :checked="env.hideText" @change="setDisplay({ hideText: $event.target.checked })" />
          <span>盲听：先隐藏原文</span>
        </label>
        <label class="switch">
          <input type="checkbox" :checked="env.showTranslation" @change="setDisplay({ showTranslation: $event.target.checked })" />
          <span>显示中文翻译</span>
        </label>
        <div class="panel__progress">
          <template v-if="content.mode === 'dictation'">已填 <strong>{{ answered }}</strong> / {{ turns.length }} 空</template>
          <template v-else>
            <strong>{{ answered }}</strong> 条作答
            <template v-if="shadowCount">，<strong>{{ shadowCount }}</strong> 句跟读</template>
          </template>
        </div>
        <button class="btn btn--primary btn--block" :disabled="!turns.length || finishing || waiting" @click="finish">
          {{ waiting ? '正在保存录音和发音评测…' : finishing ? '正在评分…' : '结束并评分' }}
        </button>
        <p v-if="error" class="error">{{ error }}</p>
        <p v-if="!env.serverSTT && !env.recognitionSupported" class="hint">这个浏览器不支持语音识别，可以用“写”作答，或换用 Edge。</p>
      </aside>
    </div>
  </div>
</template>

<script>
import { computed, onBeforeUnmount, provide, ref } from 'vue'
import AccentSelect from './AccentSelect.vue'
import StudyNotes from './StudyNotes.vue'
import ArticlePractice from './ArticlePractice.vue'
import ChatPractice from './ChatPractice.vue'
import DialoguePractice from './DialoguePractice.vue'
import DictationPractice from './DictationPractice.vue'
import QuestionsPractice from './QuestionsPractice.vue'
import { api } from '../api'
import { stop } from '../audio'

const MODE_NAMES = { article: '短文', dialogue: '情景对话', questions: '话题问答', chat: '自由对话', dictation: '精听填空' }
const MODE_COMPONENTS = {
  article: ArticlePractice, dialogue: DialoguePractice, questions: QuestionsPractice,
  chat: ChatPractice, dictation: DictationPractice,
}

export default {
  name: 'PracticeView',
  props: {
    session: { type: Object, required: true },
    env: { type: Object, required: true },
    finishing: { type: Boolean, default: false },
    error: { type: String, default: '' },
  },
  components: { AccentSelect, StudyNotes },
  emits: ['update:display', 'update:accent', 'finish'],
  setup(props, { emit }) {
    const content = computed(() => props.session.content)
    const turns = ref([])
    // how many times each item was played (feeds the listening score)
    const plays = {}
    const tracker = { plays, count: (id) => (plays[id] = (plays[id] || 0) + 1) }

    provide('sessionId', props.session.id)
    onBeforeUnmount(() => stop())

    const pending = new Map() // turn id -> pronunciation assessment in flight
    const replaceTurn = (turn) => {
      turns.value = [...turns.value.filter((t) => t.id !== turn.id), turn]
    }
    const patchTurn = (id, patch) => {
      turns.value = turns.value.map((t) => (t.id === id ? { ...t, ...patch } : t))
    }

    // Reading a script aloud (shadowing, or "照着说" in dialogues): score it with the gateway
    function assess(turn) {
      const blob = turn.audioBlob
      const job = api.pronounce(blob, turn.reference, props.env.language)
        .then((r) => {
          const current = turns.value.find((t) => t.id === turn.id)
          if (current?.audioBlob !== blob) return // re-recorded meanwhile
          patchTurn(turn.id, { pronScore: r.score, pronNote: r.note, pronIssues: r.issues, pronPending: false })
        })
        .catch(() => patchTurn(turn.id, { pronPending: false }))
        .finally(() => { if (pending.get(turn.id) === job) pending.delete(turn.id) })
      pending.set(turn.id, job)
    }

    const addTurn = (turn) => {
      const scorable = props.env.pronounceServer && turn.input === 'voice' && turn.audioBlob && turn.reference && !turn.freeResponse
      replaceTurn(scorable ? { ...turn, pronPending: true } : turn)
      if (scorable) assess(turn)
    }
    const answered = computed(() => turns.value.filter((t) => t.kind !== 'shadow' && (t.kind !== 'dictation' || t.answer)).length)
    const shadowCount = computed(() => turns.value.filter((t) => t.kind === 'shadow').length)
    const setDisplay = (patch) =>
      emit('update:display', {
        rate: props.env.rate, hideText: props.env.hideText, showTranslation: props.env.showTranslation, ...patch,
      })
    const tab = ref('practice')
    const notesOpened = ref(false)
    const openNotes = () => { tab.value = 'notes'; notesOpened.value = true }
    const waiting = ref(false)
    // keep recordings with the session so the report (now or later) can replay them
    async function uploadRecordings() {
      const jobs = turns.value
        .filter((t) => t.audioBlob && !String(t.audioUrl || '').startsWith('/api/'))
        .map((t) => api.uploadAudio(props.session.id, t.id, t.audioBlob)
          .then((r) => patchTurn(t.id, { audioUrl: r.url }))
          .catch(() => {}))
      await Promise.allSettled(jobs)
    }

    async function finish() {
      stop()
      waiting.value = true
      // give outstanding pronunciation scores a moment to arrive
      await Promise.race([
        Promise.allSettled([...pending.values(), uploadRecordings()]),
        new Promise((r) => setTimeout(r, 20000)),
      ])
      waiting.value = false
      emit('finish', turns.value)
    }

    return {
      content, turns, tracker, addTurn, answered, shadowCount, setDisplay, finish, waiting, tab, notesOpened, openNotes,
      modeNames: MODE_NAMES,
      modeComponent: computed(() => MODE_COMPONENTS[content.value.mode]),
    }
  },
}
</script>
