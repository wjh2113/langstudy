// App-wide state: the signed-in user, server config, practice preferences, listening
// settings and theme. A plain reactive module (small enough not to need Pinia).
import { computed, reactive, watchEffect } from 'vue'
import { api } from './api'
import type { User } from './api/types.gen'
import type { AppConfig, Env, Lang, Level, Mode } from './api/models'
import { setServerTTS, setVoiceOptions, stop } from './lib/audio'
import { resetCards, refreshDue } from './lib/cards'
import { browserRecognitionSupported } from './lib/recorder'
import { load, read, save } from './lib/storage'

export interface Prefs {
  language: Lang
  level: Level
  mode: Mode
  count: number
  topic: string
  autoLevel: boolean
}
export interface Display {
  rate: number
  hideText: boolean
  showTranslation: boolean
  handsFree: boolean
  accents: Partial<Record<Lang, string>>
}
export type Theme = 'system' | 'light' | 'dark'

const DEFAULT_PREFS: Prefs = { language: 'en', level: 'intermediate', mode: 'questions', count: 5, topic: '', autoLevel: false }
const DEFAULT_DISPLAY: Display = { rate: 1, hideText: false, showTranslation: false, handsFree: false, accents: {} }

export const store = reactive({
  auth: 'loading' as 'loading' | 'setup' | 'login' | 'register' | 'in',
  user: null as User | null,
  config: null as AppConfig | null,
  configError: '',
  prefs: load<Prefs>('ls.prefs', DEFAULT_PREFS),
  display: load<Display>('ls.display', DEFAULT_DISPLAY),
  theme: ((read('ls.theme') as Theme) || 'system') as Theme,
  /** language of the page being shown (a practice/report sets it to its own) */
  pageLanguage: null as Lang | null,
})

export const isAdmin = computed(() => store.user?.role === 'admin')
export const language = computed<Lang>(() => store.pageLanguage || store.prefs.language)

export function setPrefs(patch: Partial<Prefs>) {
  Object.assign(store.prefs, patch)
  save('ls.prefs', store.prefs)
}
export function setDisplay(patch: Partial<Display>) {
  Object.assign(store.display, patch)
  save('ls.display', store.display)
}
/** The listening accent is remembered per language. */
export function setAccent(lang: Lang, key: string) {
  setDisplay({ accents: { ...store.display.accents, [lang]: key } })
}

export function setTheme(theme: Theme) {
  store.theme = theme
  save('ls.theme', theme)
}
watchEffect(() => {
  const el = document.documentElement
  if (store.theme === 'system') delete el.dataset.theme
  else el.dataset.theme = store.theme
})
export const effectiveTheme = computed<'light' | 'dark'>(() => {
  if (store.theme !== 'system') return store.theme
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
})

/** Everything components need to know about a target language and the listening settings. */
export function envFor(lang: Lang): Env {
  const meta = store.config?.languages.find((l) => l.code === lang)
  const accents = meta?.accents || []
  const accentKey = store.display.accents?.[lang] || 'default'
  const accent = accents.find((a) => a.key === accentKey) || accents[0]
  return {
    rate: store.display.rate,
    hideText: store.display.hideText,
    showTranslation: store.display.showTranslation,
    handsFree: store.display.handsFree,
    accents,
    accent: accent?.key || 'default',
    accentLocale: accent?.locale || null,
    language: lang,
    locale: meta?.sttLocale || (lang === 'ja' ? 'ja-JP' : 'en-US'),
    serverSTT: Boolean(store.config?.sttServer),
    recognitionSupported: browserRecognitionSupported,
    pronounceServer: Boolean(store.config?.pronounceServer),
    textClass: lang === 'ja' ? 't-ja' : 't-en',
  }
}
export const env = computed(() => envFor(language.value))
watchEffect(() => setVoiceOptions({ accent: env.value.accent, locale: env.value.accentLocale }))

export async function loadConfig() {
  store.configError = ''
  try {
    store.config = await api.config()
    setServerTTS(store.config.ttsServer)
  } catch (e: any) {
    store.configError = e.message
  }
}

export function signedIn(user: User) {
  store.user = user
  store.auth = 'in'
  loadConfig()
  refreshDue()
}

export function signedOut() {
  stop()
  resetCards()
  store.user = null
  store.auth = 'login'
}

export async function logout() {
  await api.logout().catch(() => {})
  signedOut()
}

export async function boot(inviteCode: string) {
  window.addEventListener('ls:unauthorized', signedOut)
  try {
    const me = await api.me()
    if (me.setupRequired) store.auth = 'setup'
    else if (me.user) signedIn(me.user)
    else store.auth = inviteCode ? 'register' : 'login'
  } catch (e: any) {
    store.configError = e.message
    store.auth = 'login'
  }
}
