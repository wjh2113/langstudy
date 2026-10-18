<template>
  <div class="home" :data-lang="prefs.language">
    <h1 class="home__title">今天练什么话题？</h1>

    <div class="home__ask">
      <form class="searchbar" @submit.prevent="submit()">
        <AppIcon name="search" :size="22" class="searchbar__icon" />
        <input v-model="topic" class="searchbar__input" maxlength="200" aria-label="话题"
          :placeholder="prefs.language === 'ja' ? '例如：日企面试、在便利店购物、预约餐厅…' : '例如：面试自我介绍、餐厅点餐、机场问路…'" />
        <button class="btn btn--primary searchbar__btn" :disabled="!topic.trim() || busy">
          {{ busy && !pasting ? '正在生成…' : '生成练习' }}<AppIcon v-if="!(busy && !pasting)" name="arrow-right" :size="18" />
        </button>
      </form>
      <button type="button" class="btn btn--ghost home__upload" :disabled="busy" @click="openUpload">
        <AppIcon name="doc" :size="18" /> 上传资料
      </button>
    </div>
    <div class="chips chips--center">
      <button v-for="s in suggestions[prefs.language] || []" :key="s" type="button" class="chip" @click="topic = s">{{ s }}</button>
    </div>

    <div v-if="busy" class="progress-card" role="status">
      <div class="progress-card__row">
        <span class="spinner" aria-hidden="true" />
        <strong>{{ pasting ? '正在整理课程包…' : '正在生成练习内容…' }}</strong>
        <span class="muted">{{ waited }} 秒</span>
      </div>
      <div class="bar"><span :style="{ width: `${Math.min(95, waited * 4)}%` }" /></div>
      <p class="muted">{{ pasting && topicImportBusy ? '正在导入话题…' : uploadOpen || pasting ? '正在本地提取文字，并整理成课程包…' : '一般需要 10–30 秒，生成好会自动进入练习。' }}</p>
    </div>
    <p v-if="error" class="banner banner--error"><AppIcon name="alert" /> {{ error }}</p>

    <section v-if="picks.length" class="resume">
      <div class="resume__head">
        <h2 class="section-title"><AppIcon name="history" /> 继续上次的练习</h2>
        <RouterLink to="/topics" class="btn btn--ghost btn--sm">话题管理</RouterLink>
      </div>
      <div ref="comboEl" class="resume__combo" :class="{ open: pickOpen }">
        <div v-if="!pickOpen && selected" class="resume__face">
          <button type="button" class="resume__item resume__item--go" :disabled="opening" @click="openPick(selected)">
            <span :class="['tag', `tag--${selected.language}`]">{{ LANG_NAMES[selected.language || 'en'] }}</span>
            <span class="tag tag--mode">{{ MODE_NAMES[selected.mode] }}</span>
            <strong>{{ selected.topic }}</strong>
            <span class="muted">{{ pickMeta(selected) }}</span>
            <AppIcon name="chevron-right" :size="16" />
          </button>
          <button
            v-if="picks.length > 1"
            type="button"
            class="resume__toggle"
            :aria-expanded="pickOpen"
            aria-label="搜索并选择练习"
            @click="openPickMenu"
          >
            <AppIcon name="chevron-down" :size="18" />
          </button>
        </div>
        <div v-else class="resume__panel">
          <label class="resume__search">
            <AppIcon name="search" :size="18" />
            <input
              ref="pickInput"
              v-model="pickQuery"
              type="search"
              enterkeyhint="search"
              placeholder="搜索话题、形式、语言…"
              aria-label="搜索练习"
              aria-controls="resume-pick-list"
              @keydown="onPickKey"
            />
            <button type="button" class="resume__toggle" aria-label="收起" @click="closePickMenu">
              <AppIcon name="chevron-down" :size="18" />
            </button>
          </label>
          <ul id="resume-pick-list" class="resume__menu" role="listbox">
            <li v-for="(s, i) in filteredPicks" :key="s.id" role="option" :aria-selected="s.id === selectedId">
              <button
                type="button"
                :class="['resume__option', { on: s.id === selectedId || i === pickActive }]"
                :disabled="opening"
                @click="choosePick(s)"
                @mouseenter="pickActive = i"
              >
                <span :class="['tag', `tag--${s.language}`]">{{ LANG_NAMES[s.language || 'en'] }}</span>
                <span class="tag tag--mode">{{ MODE_NAMES[s.mode] }}</span>
                <strong>{{ s.topic }}</strong>
                <span class="muted">{{ pickMeta(s) }}</span>
              </button>
            </li>
            <li v-if="!filteredPicks.length" class="resume__empty muted">没有匹配的练习</li>
          </ul>
        </div>
      </div>
    </section>

    <section v-if="coach && (coach.level || coach.weakest)" class="coach">
      <div v-if="coach.level" class="coach__row">
        <AppIcon name="bars" class="coach__icon" />
        <p><strong>难度建议</strong>{{ coach.reason }}</p>
        <button v-if="coach.change && prefs.level !== coach.level" type="button" class="btn btn--sm btn--ghost"
          @click="setPrefs({ level: coach.level })">改为{{ LEVEL_NAMES[coach.level] }}</button>
        <span v-else-if="coach.change && autoApplied" class="tag tag--ok">已自动调整</span>
      </div>
      <div v-if="coach.weakest" class="coach__row">
        <AppIcon name="trend" class="coach__icon" />
        <p><strong>薄弱项</strong>最近「{{ coach.weakest.name }}」平均 {{ coach.weakest.score }} 分，是你最弱的一项。</p>
        <button type="button" class="btn btn--sm btn--primary" :disabled="busy" @click="drill">专项练一组</button>
      </div>
      <label class="coach__auto">
        <ToggleSwitch :model-value="prefs.autoLevel" label="按最近成绩自动调节难度" @update:model-value="(v) => setPrefs({ autoLevel: v })" />
        <span>按最近成绩自动调节难度</span>
      </label>
    </section>

    <section class="options card">
      <div class="options__row options__row--top">
        <div class="opt opt--lang">
          <OptHead icon="globe" title="学习语言" sub="选择你想练习的语言" />
          <div class="lang-cards">
            <button v-for="l in languages" :key="l.code" type="button" :class="['lang-card', `lang-card--${l.code}`, { on: prefs.language === l.code }]"
              :aria-pressed="prefs.language === l.code" @click="setPrefs({ language: l.code })">
              <FlagIcon :lang="l.code" :size="34" />
              <span class="lang-card__text"><strong>{{ LANG_NAMES[l.code] }}</strong><small>{{ l.name }}</small></span>
              <span v-if="prefs.language === l.code" class="lang-card__check"><AppIcon name="check" :size="14" :stroke="3" /></span>
            </button>
          </div>
        </div>
        <div class="opt opt--level">
          <OptHead icon="bars" title="难度等级" sub="从简单到具有挑战性的内容" />
          <SegControl block :options="levelOptions" :model-value="prefs.level" label="难度"
            @update:model-value="(v) => setPrefs({ level: v })" />
        </div>
        <div class="opt opt--count">
          <OptHead icon="list" title="题目数量" :sub="countHint" />
          <SegControl v-if="hasCount" block :options="[3, 5, 8].map((n) => ({ value: n, label: String(n) }))"
            :model-value="prefs.count" label="题目数量" @update:model-value="(v) => setPrefs({ count: v })" />
          <p v-else class="muted opt__note">{{ prefs.mode === 'chat' ? '自由对话不限轮数，聊到自然结束为止。' : '长度按难度自动决定。' }}</p>
        </div>
      </div>

      <div class="options__row options__row--bottom">
        <div v-if="regions.length > 1" class="opt opt--accent">
          <OptHead icon="headphones" title="听力口音" :sub="`选择你想要的${prefs.language === 'ja' ? '日语' : '英语'}口音`" />
          <div class="tile-grid tile-grid--accent">
            <button v-for="r in regions" :key="r.name" type="button" :class="['tile', { on: r.name === currentRegion }]"
              :aria-pressed="r.name === currentRegion" @click="pickRegion(r)">
              <RegionIcon :region="r.name" />
              <strong>{{ r.name || '标准' }}</strong>
              <small>（{{ r.name === currentRegion ? currentAccent?.label : r.items[0].label }}）</small>
            </button>
          </div>
          <AccentSelect v-if="regionAccents.length > 1" class="opt__sub" :accents="regionAccents" :model-value="accentKey"
            @update:model-value="(k) => setAccent(prefs.language, k)" />
        </div>
        <div class="opt opt--mode">
          <OptHead icon="chat-dots" title="练习形式" sub="选择你想要的练习方式" />
          <div class="tile-grid tile-grid--mode">
            <button v-for="m in modes" :key="m.key" type="button" :class="['tile', { on: prefs.mode === m.key }]"
              :aria-pressed="prefs.mode === m.key" @click="setPrefs({ mode: m.key })">
              <span class="tile__icon"><AppIcon :name="m.icon" :size="20" /></span>
              <strong>{{ m.name }}</strong>
              <small>{{ m.desc }}</small>
            </button>
          </div>
        </div>
      </div>
    </section>

    <p v-if="store.config && store.config.demoMode" class="banner banner--info">
      <AppIcon name="info" /> 现在是演示模式：还没有配置网关或大模型，会使用内置示例内容。
    </p>

    <UploadMaterialsDialog
      :open="uploadOpen"
      @close="uploadOpen = false"
      @reopen="uploadOpen = true"
      @error="(m) => (error = m)"
      @imported="onImported"
      @busy="onUploadBusy"
    />

    <ModalDialog :open="!!reuse" title="这个话题练过了" icon="history" @close="reuse = null">
      <p v-if="reuse">上次练习「{{ reuse.title }}」是在 {{ dateTime(reuse.createdAt) }}<template v-if="reuse.done">，得了 {{ reuse.overall ?? '—' }} 分</template>。</p>
      <p class="muted">用上次的题不会再调用 AI 生成，马上就能开始，学习笔记也会一起带过来。</p>
      <div class="modal__actions">
        <button type="button" class="btn btn--ghost" @click="startNew">换一套新题</button>
        <button type="button" class="btn btn--primary" @click="useLast">用上次的题</button>
      </div>
    </ModalDialog>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, h, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import AppIcon from '../components/ui/AppIcon.vue'
import AccentSelect, { groupAccents } from '../components/ui/AccentSelect.vue'
import FlagIcon from '../components/ui/FlagIcon.vue'
import ModalDialog from '../components/ui/ModalDialog.vue'
import RegionIcon from '../components/ui/RegionIcon.vue'
import SegControl from '../components/ui/SegControl.vue'
import ToggleSwitch from '../components/ui/ToggleSwitch.vue'
import UploadMaterialsDialog from '../components/UploadMaterialsDialog.vue'
import { api, type SessionSummary } from '../api'
import type { Accent, Coach, Level, Mode } from '../api/models'
import type { PreviousSession } from '../api/types.gen'
import { accentKeyFor, setAccent, setPrefs, store } from '../store'
import { LANG_NAMES, LEVEL_NAMES, MODE_NAMES, dateTime } from '../lib/format'

const OptHead = (props: { icon: string; title: string; sub: string }) => h('div', { class: 'opt__head' }, [
  h(AppIcon, { name: props.icon, size: 22 }),
  h('div', [h('h3', props.title), h('p', props.sub)]),
])
OptHead.props = ['icon', 'title', 'sub']

const MODES: { key: Mode; name: string; desc: string; icon: string }[] = [
  { key: 'questions', name: '话题问答', desc: '围绕话题进行问答', icon: 'chats' },
  { key: 'dialogue', name: '情景对话', desc: '模拟真实场景对话', icon: 'chat' },
  { key: 'article', name: '短文', desc: '跟读并回答问题', icon: 'doc' },
  { key: 'chat', name: '自由对话', desc: 'AI 陪你一直聊', icon: 'chat-dots' },
  { key: 'dictation', name: '精听填空', desc: '听录音把词填上', icon: 'pen' },
]

const SUGGESTIONS: Record<string, string[]> = {
  en: ['面试自我介绍', '餐厅点餐', '问路', '日常寒暄', '商务会议'],
  ja: ['日企面试', '在便利店购物', '自我介绍', '预约餐厅', '聊聊周末计划'],
}

export default defineComponent({
  name: 'HomeView',
  components: { AccentSelect, AppIcon, FlagIcon, ModalDialog, OptHead, RegionIcon, SegControl, ToggleSwitch, UploadMaterialsDialog },
  setup() {
    const router = useRouter()
    const prefs = store.prefs
    const topic = ref(prefs.topic || '')
    const busy = ref(false)
    const waited = ref(0)
    const error = ref('')
    const reuse = ref<PreviousSession | null>(null)
    const uploadOpen = ref(false)
    const pasting = ref(false)
    const topicImportBusy = ref(false)
    let pending: Record<string, any> | null = null

    const languages = computed(() => store.config?.languages || [])
    const meta = computed(() => languages.value.find((l) => l.code === prefs.language))
    const levelOptions = computed(() => (meta.value?.levels || []).map((l) => ({ value: l.key, label: LEVEL_NAMES[l.key], title: l.label })))
    const accents = computed<Accent[]>(() => meta.value?.accents || [])
    const regions = computed(() => groupAccents(accents.value))
    const accentKey = computed(() => accentKeyFor(prefs.language))
    const currentAccent = computed(() =>
      accents.value.find((a) => a.key === accentKey.value)
      || accents.value.find((a) => a.key === 'gb')
      || accents.value[0])
    const currentRegion = computed(() => currentAccent.value?.group ?? '')
    const regionAccents = computed(() => regions.value.find((r) => r.name === currentRegion.value)?.items || [])
    const pickRegion = (r: { name: string; items: Accent[] }) => {
      if (r.name !== currentRegion.value) setAccent(prefs.language, r.items[0].key)
    }
    const hasCount = computed(() => prefs.mode === 'questions' || prefs.mode === 'article')
    const countHint = computed(() => (prefs.mode === 'article' ? '短文后的理解题数量' : hasCount.value ? '每次练习包含的题目数量' : '这个形式不需要设置'))

    // coaching: suggested difficulty + weakest skill for the selected language
    const coach = ref<Coach | null>(null)
    const autoApplied = ref(false)
    watch(() => prefs.language, async (lang) => {
      coach.value = null
      try {
        const c = await api.coach(lang)
        if (lang !== prefs.language) return
        coach.value = c
        if (prefs.autoLevel && c.level && c.change && prefs.level !== c.level) {
          setPrefs({ level: c.level as Level })
          autoApplied.value = true
        }
      } catch { /* coaching is optional */ }
    }, { immediate: true })

    // recent practices: default is the last unfinished one; picker also lists imports and earlier topics
    const picks = ref<SessionSummary[]>([])
    const selectedId = ref('')
    const opening = ref(false)
    const pickOpen = ref(false)
    const pickQuery = ref('')
    const pickActive = ref(0)
    const comboEl = ref<HTMLElement | null>(null)
    const pickInput = ref<HTMLInputElement | null>(null)
    const selected = computed(() => picks.value.find((s) => s.id === selectedId.value) || picks.value[0] || null)

    function byRecent(a: SessionSummary, b: SessionSummary) {
      return (b.updatedAt || b.createdAt).localeCompare(a.updatedAt || a.createdAt)
    }
    function pickHaystack(s: SessionSummary) {
      const mode = MODE_NAMES[s.mode as Mode] || s.mode || ''
      const lang = LANG_NAMES[s.language || 'en'] || ''
      const level = LEVEL_NAMES[s.level || ''] || s.level || ''
      return `${s.topic} ${s.title || ''} ${mode} ${lang} ${level} ${pickMeta(s)}`.toLowerCase()
    }
    function fuzzyMatch(hay: string, query: string) {
      const tokens = query.trim().toLowerCase().split(/\s+/).filter(Boolean)
      if (!tokens.length) return true
      return tokens.every((t) => {
        if (hay.includes(t)) return true
        let i = 0
        for (const ch of hay) {
          if (ch === t[i]) i += 1
          if (i >= t.length) return true
        }
        return false
      })
    }
    const filteredPicks = computed(() => {
      const q = pickQuery.value
      if (!q.trim()) return picks.value
      return picks.value.filter((s) => fuzzyMatch(pickHaystack(s), q))
    })
    function pickMeta(s: SessionSummary) {
      const when = dateTime(s.updatedAt || s.createdAt)
      if (!s.done && (s.answered || 0) > 0) return `已答 ${s.answered} 条 · ${when}`
      if (!s.done) return `未开始 · ${when}`
      return `${s.overall ?? '—'} 分 · 点此用同一套题再练 · ${when}`
    }
    function openPickMenu() {
      pickOpen.value = true
      pickQuery.value = ''
      pickActive.value = Math.max(0, filteredPicks.value.findIndex((s) => s.id === selectedId.value))
      nextTick(() => pickInput.value?.focus())
    }
    function closePickMenu() {
      pickOpen.value = false
      pickQuery.value = ''
      pickActive.value = 0
    }
    function onDocPointer(e: Event) {
      if (!pickOpen.value || !comboEl.value) return
      if (!comboEl.value.contains(e.target as Node)) closePickMenu()
    }
    function onPickKey(e: KeyboardEvent) {
      const list = filteredPicks.value
      if (e.key === 'Escape') {
        e.preventDefault()
        closePickMenu()
        return
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        if (!list.length) return
        pickActive.value = (pickActive.value + 1) % list.length
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        if (!list.length) return
        pickActive.value = (pickActive.value - 1 + list.length) % list.length
        return
      }
      if (e.key === 'Enter') {
        e.preventDefault()
        const s = list[pickActive.value] || list[0]
        if (s) choosePick(s)
      }
    }
    watch(filteredPicks, (list) => {
      if (pickActive.value >= list.length) pickActive.value = Math.max(0, list.length - 1)
    })
    async function openPick(s: SessionSummary) {
      if (opening.value) return
      opening.value = true
      error.value = ''
      closePickMenu()
      try {
        if (!s.done) {
          router.push(`/practice/${s.id}`)
          return
        }
        const r = await api.repeat(s.id)
        router.push(`/practice/${r.id}`)
      } catch (e: any) {
        error.value = e.message
      } finally {
        opening.value = false
      }
    }
    function choosePick(s: SessionSummary) {
      selectedId.value = s.id
      openPick(s)
    }

    function topicKey(s: { language?: string | null; level?: string | null; mode?: string | null; topic?: string | null }) {
      return `${s.language || ''}|${s.level || ''}|${s.mode || ''}|${(s.topic || '').trim().toLowerCase()}`
    }
    async function loadPicks(preferId = '') {
      try {
        const [all, topics] = await Promise.all([api.sessions(), api.topics()])
        const continuing = all.filter((s) => !s.done && (s.answered || 0) > 0).sort(byRecent)
        const fresh = all.filter((s) => !s.done && !(s.answered || 0)).sort(byRecent)
        const covered = new Set([...continuing, ...fresh].map(topicKey))
        const earlier: SessionSummary[] = []
        for (const t of topics) {
          const key = topicKey(t)
          if (!key.endsWith('|') && !covered.has(key)) {
            covered.add(key)
            earlier.push(t)
          }
        }
        const seen = new Set<string>()
        const list: SessionSummary[] = []
        for (const s of [...continuing, ...fresh, ...earlier]) {
          if (seen.has(s.id)) continue
          seen.add(s.id)
          list.push(s)
          if (list.length >= 50) break
        }
        picks.value = list
        selectedId.value = (preferId && list.some((s) => s.id === preferId) && preferId)
          || continuing[0]?.id || fresh[0]?.id || list[0]?.id || ''
      } catch { /* optional */ }
    }
    onMounted(() => {
      loadPicks()
      document.addEventListener('pointerdown', onDocPointer)
    })
    onBeforeUnmount(() => document.removeEventListener('pointerdown', onDocPointer))

    async function generate(body: Record<string, any>) {
      busy.value = true
      waited.value = 0
      error.value = ''
      try {
        const res = await api.generate(body as any, (s) => (waited.value = s))
        router.push(`/practice/${res.id}`)
      } catch (e: any) {
        error.value = e.message
      } finally {
        busy.value = false
      }
    }

    async function submit() {
      const t = topic.value.trim()
      if (!t || busy.value) return
      setPrefs({ topic: t })
      const body = { language: prefs.language, level: prefs.level, mode: prefs.mode, topic: t, count: prefs.count, focus: '' }
      try {
        const { previous } = await api.previous({ language: body.language, level: body.level, mode: body.mode, topic: t })
        if (previous) {
          pending = body
          reuse.value = previous
          return
        }
      } catch { /* just generate */ }
      generate(body)
    }

    function startNew() {
      reuse.value = null
      if (pending) generate(pending)
    }
    async function useLast() {
      const prev = reuse.value
      reuse.value = null
      if (!prev) return
      try {
        const r = await api.repeat(prev.id)
        router.push(`/practice/${r.id}`)
      } catch (e: any) {
        error.value = e.message
      }
    }

    const drill = () => coach.value?.weakest &&
      generate({ language: prefs.language, level: prefs.level, mode: '', topic: '', count: prefs.count, focus: coach.value.weakest.key })

    function openUpload() {
      uploadOpen.value = true
      error.value = ''
    }

    function onUploadBusy(p: { on: boolean; topicImport?: boolean; waited?: number }) {
      if (p.on) {
        busy.value = true
        pasting.value = true
        topicImportBusy.value = !!p.topicImport
        waited.value = typeof p.waited === 'number' ? p.waited : 0
      } else {
        busy.value = false
        pasting.value = false
        topicImportBusy.value = false
      }
    }

    async function onImported(result: { imported: { id: string }[] }) {
      if (result.imported?.length) await loadPicks(result.imported[0].id)
    }

    return {
      store, prefs, topic, busy, waited, error, reuse, uploadOpen, pasting, topicImportBusy,
      openUpload, onUploadBusy, onImported,
      languages, levelOptions, regions, accentKey, currentAccent, currentRegion,
      regionAccents, pickRegion, hasCount, countHint, coach, autoApplied,
      picks, selectedId, selected, opening, pickOpen, pickQuery, pickActive, filteredPicks,
      comboEl, pickInput, pickMeta, openPick, openPickMenu, closePickMenu, choosePick, onPickKey,
      submit, startNew, useLast, drill,
      setPrefs, setAccent, modes: MODES, suggestions: SUGGESTIONS, LANG_NAMES, LEVEL_NAMES, MODE_NAMES, dateTime,
    }
  },
})
</script>
