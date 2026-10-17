<template>
  <div v-if="loadError" class="page"><p class="banner banner--error"><AppIcon name="alert" /> {{ loadError }}</p>
    <RouterLink to="/" class="btn btn--ghost">回到首页</RouterLink></div>
  <div v-else-if="!session || !env" class="page"><p class="hint">正在打开练习…</p></div>
  <div v-else class="practice" :data-lang="content.language">
    <Teleport to="#header-center">
      <nav class="head-tabs" role="tablist">
        <button type="button" role="tab" :aria-selected="tab === 'practice'" :class="{ on: tab === 'practice' }" @click="tab = 'practice'">练习</button>
        <button type="button" role="tab" :aria-selected="tab === 'notes'" :class="{ on: tab === 'notes' }" @click="openNotes">学习笔记</button>
      </nav>
      <span class="head-crumb"><span class="muted">{{ MODE_NAMES[content.mode] }}</span><span class="muted">/</span><strong>{{ content.topic }}</strong>
        <span v-if="content.focus" class="tag tag--warn">专项：{{ content.focus.name }}</span></span>
    </Teleport>

    <div class="practice__body">
      <main class="practice__main">
        <div class="practice__titlebar">
          <h1 :class="['practice__title', env.textClass]"><template v-if="!['article', 'dictation'].includes(content.mode)">{{ content.title }}</template></h1>
          <button type="button" class="btn btn--ghost btn--sm practice__settings-btn" @click="drawer = true">
            <AppIcon name="settings" :size="16" /> 练习设置
          </button>
        </div>
        <div v-show="tab === 'practice'" class="practice__flow">
          <component :is="modeComponent" :content="content" :env="env" :turns="turns" :tracker="tracker" @add-turn="addTurn" />
        </div>
        <StudyNotes v-if="notesOpened" v-show="tab === 'notes'" :session-id="session.id" :env="env" />
      </main>

      <aside class="practice__aside card" aria-label="练习设置">
        <PracticeSettings v-bind="settingsProps" @finish="finish" />
      </aside>
    </div>

    <ModalDialog :open="drawer" drawer title="练习设置" icon="settings" @close="drawer = false">
      <PracticeSettings v-bind="settingsProps" in-drawer @finish="drawer = false; finish()" />
    </ModalDialog>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, onBeforeUnmount, provide, reactive, ref, shallowRef, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import AppIcon from '../components/ui/AppIcon.vue'
import ModalDialog from '../components/ui/ModalDialog.vue'
import ArticlePractice from '../components/practice/ArticlePractice.vue'
import ChatPractice from '../components/practice/ChatPractice.vue'
import DialoguePractice from '../components/practice/DialoguePractice.vue'
import DictationPractice from '../components/practice/DictationPractice.vue'
import PracticeSettings from '../components/practice/PracticeSettings.vue'
import QuestionsPractice from '../components/practice/QuestionsPractice.vue'
import StudyNotes from '../components/practice/StudyNotes.vue'
import { api, type SessionOut } from '../api'
import type { Content, PracticeState, Turn } from '../api/models'
import { stop } from '../lib/audio'
import { invalidate, refreshDue } from '../lib/cards'
import { MODE_NAMES } from '../lib/format'
import { PRACTICE_STATE, SESSION_ID, hydrateTurn, toApiTurn } from '../lib/practice'
import { cacheReport } from './reportCache'
import { envFor, store } from '../store'

const MODE_COMPONENTS = {
  article: ArticlePractice, dialogue: DialoguePractice, questions: QuestionsPractice, chat: ChatPractice, dictation: DictationPractice,
}
const SAVE_DELAY = 800

export default defineComponent({
  name: 'PracticePage',
  components: { AppIcon, ModalDialog, PracticeSettings, StudyNotes },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const id = route.params.id as string
    const session = shallowRef<SessionOut | null>(null)
    const loadError = ref('')
    const content = computed(() => (session.value?.content || {}) as Content)
    const env = computed(() => (session.value ? envFor(content.value.language) : null))
    const turns = ref<Turn[]>([])
    const state = reactive<PracticeState>({})
    const tab = ref<'practice' | 'notes'>('practice')
    const notesOpened = ref(false)
    const drawer = ref(false)
    const finishing = ref(false)
    const waited = ref(0)
    const error = ref('')
    const savedAt = ref('')
    const saveState = ref('')

    provide(SESSION_ID, id)
    provide(PRACTICE_STATE, state)

    // how many times each item was played (feeds the listening score) — saved with the state
    const tracker = {
      get plays() { return (state.plays ||= {}) },
      count: (key: string) => { const p = (state.plays ||= {}); p[key] = (p[key] || 0) + 1 },
    }

    async function load() {
      try {
        const s = await api.session(id)
        if (s.report) return router.replace(`/report/${id}`)
        store.pageLanguage = (s.content as unknown as Content).language
        turns.value = s.turns.map((t) => hydrateTurn(t as any, (s.content as any).language))
        Object.assign(state, s.state || {})
        session.value = s
        if (s.turns.length) savedAt.value = '（上次）'
      } catch (e: any) {
        loadError.value = e.status === 404 ? '这个练习不存在，或者已经被删除了。' : e.message
      }
    }
    load()
    onBeforeUnmount(() => { store.pageLanguage = null })

    // ---------------------------------------------------------- autosave
    let saveTimer: ReturnType<typeof setTimeout> | undefined
    let dirty = false
    let saving: Promise<unknown> | null = null
    const payload = () => turns.value.map(toApiTurn)

    async function saveNow(keepalive = false) {
      clearTimeout(saveTimer)
      if (!dirty || !session.value || finishing.value) return
      dirty = false
      saveState.value = 'saving'
      const job = api.saveProgress(id, payload(), JSON.parse(JSON.stringify(state)), keepalive)
      saving = job
      try {
        await job
        savedAt.value = new Date().toTimeString().slice(0, 5)
        saveState.value = ''
      } catch {
        dirty = true
        saveState.value = 'error'
        saveTimer = setTimeout(() => saveNow(), 5000)
      } finally {
        if (saving === job) saving = null
      }
    }
    watch([turns, state], () => {
      if (!session.value) return
      dirty = true
      clearTimeout(saveTimer)
      saveTimer = setTimeout(() => saveNow(), SAVE_DELAY)
    }, { deep: true })
    const onHide = () => { if (document.visibilityState === 'hidden') saveNow(true) }
    window.addEventListener('pagehide', onHide)
    document.addEventListener('visibilitychange', onHide)
    onBeforeUnmount(() => {
      window.removeEventListener('pagehide', onHide)
      document.removeEventListener('visibilitychange', onHide)
      saveNow(true)
    })
    onBeforeRouteLeave(() => { stop() })

    // ----------------------------------------------------------- turns
    const uploads = new Map<string, Promise<unknown>>()
    const patchTurn = (key: string, patch: Partial<Turn>) => {
      turns.value = turns.value.map((t) => (t.id === key ? { ...t, ...patch } : t))
    }

    /** Recordings go to the server right away, so a resumed practice (and the report) still has them. */
    function upload(turn: Turn) {
      const blob = turn.audioBlob
      if (!blob) return
      const job = api.uploadAudio(id, turn.id, blob)
        .then((r) => {
          const cur = turns.value.find((t) => t.id === turn.id)
          if (cur?.audioBlob === blob) patchTurn(turn.id, { audioUrl: r.url })
        })
        .catch(() => {})
        .finally(() => { if (uploads.get(turn.id) === job) uploads.delete(turn.id) })
      uploads.set(turn.id, job)
    }

    function addTurn(turn: Turn) {
      turns.value = [...turns.value.filter((t) => t.id !== turn.id), turn]
      if (turn.audioBlob) upload(turn)
    }

    // pronunciation assessment is billed, so it only runs when the learner asks (评测发音)
    const canAssessPron = computed(() => Boolean(env.value?.pronounceServer))
    async function assessPron(key: string) {
      const t = turns.value.find((x) => x.id === key)
      if (!t || !t.reference || !env.value) return
      patchTurn(key, { pronPending: true })
      try {
        if (uploads.has(key) && !t.audioBlob) await uploads.get(key)
        const audioName = String(turns.value.find((x) => x.id === key)?.audioUrl || '').split('/').pop() || ''
        const src = t.audioBlob ? { blob: t.audioBlob } : { sessionId: id, audioName }
        const r = await api.pronounce(src, t.reference, env.value.language)
        patchTurn(key, { pronScore: r.score, pronNote: r.note, pronIssues: r.issues as any, pronPending: false })
      } catch (e: any) {
        patchTurn(key, { pronPending: false })
        error.value = `发音评测失败：${e.message}`
      }
    }
    provide('assessPron', assessPron)
    provide('canAssessPron', canAssessPron)

    // --------------------------------------------------------- progress
    const answered = computed(() => turns.value.filter((t) => t.kind !== 'shadow' && (t.kind !== 'dictation' || t.answer)).length)
    const total = computed(() => {
      const c = content.value
      if (c.mode === 'questions') return c.questions?.length || 0
      if (c.mode === 'article') return (c.questions?.length || 0)
      if (c.mode === 'dictation') return (c.sentences || []).reduce((n, s) => n + (s.blanks?.length || 0), 0)
      if (c.mode === 'dialogue') return (c.lines || []).filter((l) => l.role === state.dialogue?.myRole).length
      return 0
    })
    const shadowCount = computed(() => turns.value.filter((t) => t.kind === 'shadow').length)
    const progressText = computed(() => {
      if (content.value.mode === 'chat') return `${answered.value} 轮`
      const base = `${Math.min(answered.value, total.value || answered.value)} / ${total.value || '—'}`
      return shadowCount.value ? `${base} · 跟读 ${shadowCount.value} 句` : base
    })
    const progressPct = computed(() => (total.value ? Math.min(100, (answered.value / total.value) * 100) : Math.min(100, answered.value * 10)))

    // ------------------------------------------------------------ finish
    async function finish() {
      if (finishing.value || !session.value) return
      stop()
      error.value = ''
      finishing.value = true
      waited.value = 0
      try {
        // recordings still uploading get a moment to arrive (the report replays them)
        await Promise.race([Promise.allSettled([...uploads.values()]), new Promise((r) => setTimeout(r, 15000))])
        if (saving) await saving.catch(() => {})
        const report = await api.evaluate(id, payload(), (s) => (waited.value = s))
        if (report.cardsAdded) {
          invalidate(content.value.language)
          refreshDue()
        }
        cacheReport(id, { ...session.value, report: report as any, turns: payload() as any })
        dirty = false
        router.replace(`/report/${id}`)
      } catch (e: any) {
        error.value = e.message
        finishing.value = false
      }
    }

    const settingsProps = computed(() => ({
      env: env.value,
      mode: content.value.mode,
      level: content.value.level,
      progressText: progressText.value,
      progressPct: progressPct.value,
      canFinish: turns.value.length > 0,
      busy: finishing.value,
      busyText: finishing.value ? (waited.value ? `正在评分… ${waited.value} 秒` : '正在保存录音…') : '',
      error: error.value,
      savedAt: savedAt.value,
      saveState: saveState.value,
    }))

    const openNotes = () => { tab.value = 'notes'; notesOpened.value = true }

    return {
      session, loadError, content, env, turns, tracker, tab, notesOpened, drawer, settingsProps, openNotes, addTurn, finish,
      modeComponent: computed(() => MODE_COMPONENTS[content.value.mode]), MODE_NAMES,
    }
  },
})
</script>
