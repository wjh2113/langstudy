<template>
  <div v-if="authState === 'loading'" class="boot" />
  <AuthView v-else-if="authState !== 'in'" :key="authState" :initial-mode="authState" :initial-code="inviteFromUrl"
    @done="onSignedIn" />
  <div v-else class="app" :data-lang="language">
    <nav class="rail">
      <div class="brand">
        <span class="brand__mark" aria-hidden="true">听说</span>
        <span class="brand__name">LangStudy</span>
      </div>
      <button :class="['rail__item', { on: view === 'home' }]" @click="go('home')">新的练习</button>
      <button v-if="session && !report && view !== 'practice'" class="rail__item" @click="go('practice')">继续当前练习</button>
      <button :class="['rail__item', { on: view === 'history' }]" @click="go('history')">历史记录</button>
      <button v-if="user.role === 'admin'" :class="['rail__item', { on: view === 'admin' }]" @click="go('admin')">用户与邀请</button>
      <button :class="['rail__item', { on: view === 'account' }]" @click="go('account')">账号 · {{ user.username }}</button>
      <p v-if="config" class="rail__foot">
        {{ config.demoMode ? '演示模式' : `模型：${config.model}` }}<br />
        语音识别：{{ config.sttServer ? '服务端' : recognitionSupported ? '浏览器' : '不可用' }}
      </p>
    </nav>

    <div class="stage">
      <p v-if="configError" class="error error--banner">{{ configError }}</p>
      <div v-if="busy && view !== 'practice'" class="loading" role="status">
        <span class="loading__bar" />正在生成练习内容，大约需要 10–30 秒…
      </div>
      <HomeView v-if="view === 'home'" :config="config" :prefs="prefs" :busy="busy" :error="error"
        @update:prefs="setPrefs" @start="start" />
      <PracticeView v-else-if="view === 'practice' && session" :key="session.id" :session="session" :env="env"
        :finishing="busy" :error="error" @update:display="setDisplay" @finish="finish" />
      <ReportView v-else-if="view === 'report' && report" :report="report" :session="session" :env="env"
        @retry="retry" @home="go('home')" />
      <HistoryView v-else-if="view === 'history'" :is-admin="user.role === 'admin'" @open="openHistory" />
      <AdminView v-else-if="view === 'admin' && user.role === 'admin'" :me="user" />
      <AccountView v-else-if="view === 'account'" :me="user" @logout="logout" />
    </div>
  </div>
</template>

<script>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import AccountView from './components/AccountView.vue'
import AdminView from './components/AdminView.vue'
import AuthView from './components/AuthView.vue'
import HomeView from './components/HomeView.vue'
import PracticeView from './components/PracticeView.vue'
import ReportView from './components/ReportView.vue'
import HistoryView from './components/HistoryView.vue'
import { api } from './api'
import { setServerTTS, stop } from './audio'
import { browserRecognitionSupported } from './useRecorder'

const DEFAULT_PREFS = { language: 'en', level: 'intermediate', mode: 'questions', count: 5, topic: '' }
const DEFAULT_DISPLAY = { rate: 1, hideText: false, showTranslation: false }

function load(key, fallback) {
  try {
    return { ...fallback, ...JSON.parse(localStorage.getItem(key) || '{}') }
  } catch {
    return { ...fallback }
  }
}
function save(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* private mode */ }
}

export default {
  name: 'App',
  components: { AccountView, AdminView, AuthView, HomeView, PracticeView, ReportView, HistoryView },
  setup() {
    const config = ref(null)
    const configError = ref('')
    const view = ref('home') // home | practice | report | history
    const prefs = ref(load('ls.prefs', DEFAULT_PREFS))
    const display = ref(load('ls.display', DEFAULT_DISPLAY))
    const session = ref(null) // { id, content }
    const report = ref(null)
    const busy = ref(false)
    const error = ref('')

    // ---- accounts: setup (first run) / login / register via ?invite=CODE
    const authState = ref('loading') // loading | setup | login | register | in
    const user = ref(null)
    const inviteFromUrl = new URLSearchParams(location.search).get('invite') || ''

    function loadConfig() {
      configError.value = ''
      api.config()
        .then((c) => { config.value = c; setServerTTS(c.ttsServer) })
        .catch((e) => (configError.value = e.message))
    }

    function onSignedIn(u) {
      user.value = u
      authState.value = 'in'
      if (inviteFromUrl) history.replaceState(null, '', location.pathname)
      loadConfig()
    }

    function signedOut() {
      stop()
      user.value = null
      session.value = null
      report.value = null
      view.value = 'home'
      authState.value = 'login'
    }

    async function logout() {
      await api.logout().catch(() => {})
      signedOut()
    }

    onMounted(async () => {
      window.addEventListener('ls:unauthorized', signedOut)
      try {
        const me = await api.me()
        if (me.setupRequired) authState.value = 'setup'
        else if (me.user) onSignedIn(me.user)
        else authState.value = inviteFromUrl ? 'register' : 'login'
      } catch (e) {
        configError.value = e.message
        authState.value = 'login'
      }
    })
    onBeforeUnmount(() => window.removeEventListener('ls:unauthorized', signedOut))

    const setPrefs = (p) => { prefs.value = p; save('ls.prefs', p) }
    const setDisplay = (d) => { display.value = d; save('ls.display', d) }

    const language = computed(() => session.value?.content.language || prefs.value.language)
    const env = computed(() => {
      const meta = config.value?.languages.find((l) => l.code === language.value)
      return {
        ...display.value,
        language: language.value,
        locale: meta?.sttLocale || 'en-US',
        serverSTT: Boolean(config.value?.sttServer),
        recognitionSupported: browserRecognitionSupported,
        pronounceServer: Boolean(config.value?.pronounceServer),
        textClass: language.value === 'ja' ? 't-ja' : 't-en',
      }
    })

    function go(v) {
      stop()
      error.value = ''
      view.value = v
    }

    async function start(p) {
      busy.value = true
      error.value = ''
      try {
        const res = await api.generate({ language: p.language, level: p.level, mode: p.mode, topic: p.topic, count: p.count })
        session.value = res
        report.value = null
        go('practice')
      } catch (e) {
        error.value = e.message
      } finally {
        busy.value = false
      }
    }

    async function finish(turns) {
      busy.value = true
      error.value = ''
      try {
        // eslint-disable-next-line no-unused-vars
        const clean = turns.map(({ id, diff, audioUrl, audioBlob, pronPending, ...t }) => t)
        report.value = await api.evaluate({ sessionId: session.value.id, turns: clean })
        go('report')
      } catch (e) {
        error.value = e.message
      } finally {
        busy.value = false
      }
    }

    async function openHistory(id) {
      try {
        const s = await api.session(id)
        session.value = { id: s.id, content: s.content }
        report.value = s.report
        go(s.report ? 'report' : 'practice')
      } catch (e) {
        error.value = e.message
      }
    }

    function retry() {
      const c = session.value.content
      start({ ...prefs.value, language: c.language, level: c.level, mode: c.mode, topic: c.topic })
    }

    return {
      authState, user, inviteFromUrl, onSignedIn, logout,
      config, configError, view, prefs, session, report, busy, error, language, env,
      recognitionSupported: browserRecognitionSupported,
      setPrefs, setDisplay, go, start, finish, openHistory, retry,
    }
  },
}
</script>
