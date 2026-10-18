<template>
  <div class="page topics">
    <header class="page-head">
      <h1>话题管理</h1>
      <div class="page-head__actions">
        <button type="button" class="btn btn--outline btn--sm" :disabled="!!busy" @click="openUpload">
          <AppIcon name="doc" :size="16" /> 上传资料
        </button>
        <button type="button" class="btn btn--primary btn--sm" @click="openCreate">
          <AppIcon name="plus" :size="16" /> 新增话题
        </button>
      </div>
    </header>

    <div class="topics-toolbar">
      <label class="input input--search"><AppIcon name="search" :size="18" />
        <input v-model="q" placeholder="搜索话题、标题…" aria-label="搜索话题" /></label>
      <button type="button" class="btn btn--ghost btn--sm topics-filter-toggle" @click="filtersOpen = !filtersOpen">
        <AppIcon :name="filtersOpen ? 'chevron-up' : 'chevron-down'" :size="16" />
        筛选条件
        <span v-if="filterSummary" class="topics-filter-toggle__sum">{{ filterSummary }}</span>
      </button>
      <p class="topics-toolbar__meta muted">
        {{ groups.length }} 个话题 · {{ flatShown.length }} 条
        <button v-if="hasActiveFilters" type="button" class="btn btn--ghost btn--sm" @click="clearFilters">清除</button>
      </p>
    </div>

    <div v-show="filtersOpen" class="topics-filters">
      <div class="topics-filters__row">
        <span class="topics-filters__label">语言</span>
        <div class="chips">
          <button type="button" :class="['chip', { on: !lang }]" @click="lang = ''">全部</button>
          <button type="button" :class="['chip', { on: lang === 'en' }]" @click="lang = 'en'">英语</button>
          <button type="button" :class="['chip', { on: lang === 'ja' }]" @click="lang = 'ja'">日语</button>
        </div>
      </div>
      <div class="topics-filters__row">
        <span class="topics-filters__label">级别</span>
        <div class="chips">
          <button type="button" :class="['chip', { on: !level }]" @click="level = ''">全部</button>
          <button v-for="l in levels" :key="l.key" type="button" :class="['chip', { on: level === l.key }]" @click="level = l.key">{{ l.label }}</button>
        </div>
      </div>
      <div class="topics-filters__row">
        <span class="topics-filters__label">形式</span>
        <div class="chips">
          <button type="button" :class="['chip', { on: !mode }]" @click="mode = ''">全部</button>
          <button v-for="m in modes" :key="m.key" type="button" :class="['chip', { on: mode === m.key }]" @click="mode = m.key">{{ m.name }}</button>
        </div>
      </div>
      <div class="topics-filters__row">
        <span class="topics-filters__label">状态</span>
        <div class="chips">
          <button type="button" :class="['chip', { on: !status }]" @click="status = ''">全部</button>
          <button type="button" :class="['chip', { on: status === 'todo' }]" @click="status = 'todo'">未开始</button>
          <button type="button" :class="['chip', { on: status === 'progress' }]" @click="status = 'progress'">未完成</button>
          <button type="button" :class="['chip', { on: status === 'done' }]" @click="status = 'done'">已完成</button>
        </div>
      </div>
    </div>

    <p v-if="error" class="banner banner--error"><AppIcon name="alert" /> {{ error }}</p>
    <p v-if="busy" class="banner banner--info"><span class="spinner" /> {{ busyLabel }} {{ waited ? waited + ' 秒' : '' }}</p>

    <div v-if="items && !flatShown.length" class="empty card">
      <AppIcon name="list" :size="32" />
      <p v-if="items.length">没有符合条件的话题。试试清除筛选或换个关键词。</p>
      <p v-else>还没有话题。点「新增话题」生成练习，或点「上传资料」导入。</p>
      <div class="empty__actions">
        <button type="button" class="btn btn--outline" @click="openUpload">上传资料</button>
        <button type="button" class="btn btn--primary" @click="openCreate">新增话题</button>
      </div>
    </div>

    <section v-if="groups.length" class="card card--flush">
      <div class="table-wrap">
        <table class="table topics-table topics-table--tree">
          <thead>
            <tr>
              <th class="topics-table__fold" />
              <th><AppIcon name="chat" :size="16" /> 话题</th>
              <th><AppIcon name="globe" :size="16" /> 语言</th>
              <th><AppIcon name="bars" :size="16" /> 级别</th>
              <th><AppIcon name="doc" :size="16" /> 形式</th>
              <th>状态</th>
              <th><AppIcon name="clock" :size="16" /> 最近</th>
              <th><AppIcon name="list" :size="16" /> 次数</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <template v-for="g in groups" :key="g.key">
              <tr class="topics-table__parent" :class="{ open: isOpen(g) }" @click="toggleGroup(g)">
                <td class="topics-table__fold">
                  <AppIcon :name="isOpen(g) ? 'chevron-down' : 'chevron-right'" :size="18" />
                </td>
                <td class="topics-table__topic">
                  <strong>{{ g.topic }}</strong>
                  <span class="muted">{{ g.items.length }} 种</span>
                </td>
                <td colspan="4" class="muted topics-table__summary">{{ g.summary }}</td>
                <td class="nowrap">{{ dateTime(g.latest) }}</td>
                <td>{{ g.attempts }}</td>
                <td />
              </tr>
              <tr
                v-for="t in g.items"
                v-show="isOpen(g)"
                :key="t.id"
                class="topics-table__child"
              >
                <td class="topics-table__fold" />
                <td class="topics-table__child-topic muted">{{ displayTitle(t, g.topic) }}</td>
                <td><span :class="['tag', `tag--${t.language}`]">{{ LANG_NAMES[t.language || 'en'] }}</span></td>
                <td>{{ LEVEL_NAMES[t.level || ''] || t.level || '—' }}</td>
                <td><span class="tag tag--mode">{{ MODE_NAMES[t.mode] || t.mode }}</span></td>
                <td>
                  <span v-if="!t.done && (t.answered || 0) > 0" class="tag tag--warn tag--sm">未完成 · 已答 {{ t.answered }}</span>
                  <span v-else-if="!t.done" class="tag tag--sm">未开始</span>
                  <span v-else-if="t.overall != null" :class="['score-text', scoreBand(t.overall)]">{{ t.overall }} 分</span>
                  <span v-else class="tag tag--sm">已完成</span>
                </td>
                <td class="nowrap">{{ dateTime(t.updatedAt || t.createdAt) }}</td>
                <td>{{ t.attempts }}</td>
                <td class="topics-table__actions" @click.stop>
                  <button
                    v-if="!t.done"
                    type="button"
                    class="icon-btn icon-btn--primary"
                    :disabled="!!busy"
                    :title="(t.answered || 0) > 0 ? '继续' : '开始'"
                    :aria-label="(t.answered || 0) > 0 ? '继续' : '开始'"
                    @click="open(t)"
                  ><AppIcon name="play" :size="16" /></button>
                  <button
                    v-else
                    type="button"
                    class="icon-btn"
                    :disabled="!!busy"
                    title="用上次的题"
                    aria-label="用上次的题"
                    @click="reuse(t)"
                  ><AppIcon name="repeat" :size="16" /></button>
                  <button
                    type="button"
                    class="icon-btn"
                    :disabled="!!busy"
                    title="重新生成"
                    aria-label="重新生成"
                    @click="regen(t)"
                  ><AppIcon name="refresh" :size="16" /></button>
                  <button
                    type="button"
                    class="icon-btn icon-btn--danger"
                    :disabled="!!busy"
                    title="删除"
                    aria-label="删除"
                    @click="remove(t)"
                  ><AppIcon name="trash" :size="16" /></button>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>

    <ModalDialog :open="creating" title="新增话题" icon="plus" @close="creating = false">
      <form class="topic-create" @submit.prevent="create">
        <label class="field">
          <span>话题</span>
          <input v-model="draft.topic" maxlength="200" required placeholder="例如：面试自我介绍、餐厅点餐…" />
        </label>
        <label class="field">
          <span>语言</span>
          <select v-model="draft.language">
            <option value="en">英语</option>
            <option value="ja">日语</option>
          </select>
        </label>
        <label class="field">
          <span>级别</span>
          <select v-model="draft.level">
            <option value="beginner">入门</option>
            <option value="intermediate">中级</option>
            <option value="advanced">高级</option>
          </select>
        </label>
        <label class="field">
          <span>形式</span>
          <select v-model="draft.mode">
            <option v-for="m in modes" :key="m.key" :value="m.key">{{ m.name }}</option>
          </select>
        </label>
        <p class="muted small">会调用模型生成一套新练习，并出现在本列表里。</p>
        <div class="topic-create__actions">
          <button type="button" class="btn btn--ghost" @click="creating = false">取消</button>
          <button type="submit" class="btn btn--primary" :disabled="!!busy || !draft.topic.trim()">生成并开始</button>
        </div>
      </form>
    </ModalDialog>

    <UploadMaterialsDialog
      :open="uploadOpen"
      @close="uploadOpen = false"
      @reopen="uploadOpen = true"
      @error="(m) => (error = m)"
      @imported="onImported"
      @busy="onUploadBusy"
    />
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppIcon from '../components/ui/AppIcon.vue'
import ModalDialog from '../components/ui/ModalDialog.vue'
import UploadMaterialsDialog from '../components/UploadMaterialsDialog.vue'
import { api, type TopicItem } from '../api'
import type { Lang, Level, Mode } from '../api/models'
import { setPrefs, store } from '../store'
import { LANG_NAMES, LEVEL_NAMES, MODE_NAMES, dateTime, scoreBand } from '../lib/format'

const MODES: { key: Mode; name: string }[] = [
  { key: 'questions', name: '话题问答' },
  { key: 'dialogue', name: '情景对话' },
  { key: 'article', name: '短文' },
  { key: 'chat', name: '自由对话' },
  { key: 'dictation', name: '精听填空' },
]

const LEVELS = [
  { key: 'beginner', label: '入门' },
  { key: 'intermediate', label: '中级' },
  { key: 'advanced', label: '高级' },
]

const MODE_LABELS = Object.values(MODE_NAMES)

type StatusFilter = '' | 'todo' | 'progress' | 'done'

function topicStatus(t: TopicItem): StatusFilter {
  if (t.done) return 'done'
  if ((t.answered || 0) > 0) return 'progress'
  return 'todo'
}

/** Strip trailing " | 话题问答" so variants of the same topic group together. */
function baseTopicName(raw: string): string {
  let name = (raw || '').trim()
  if (!name) return '未命名'
  for (const label of MODE_LABELS) {
    const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    name = name.replace(new RegExp(`[\\s|｜/／·•\\-]+${escaped}\\s*$`), '').trim()
  }
  for (const m of MODES) {
    name = name.replace(new RegExp(`[\\s|｜/／·•\\-]+${m.key}\\s*$`, 'i'), '').trim()
  }
  return name || '未命名'
}

function groupKeyOf(t: TopicItem): string {
  return baseTopicName(t.topic || t.title || '')
}

export default defineComponent({
  name: 'TopicsView',
  components: { AppIcon, ModalDialog, UploadMaterialsDialog },
  setup() {
    const router = useRouter()
    const items = ref<TopicItem[] | null>(null)
    const error = ref('')
    const q = ref('')
    const lang = ref('')
    const level = ref('')
    const mode = ref('')
    const status = ref<StatusFilter>('')
    const filtersOpen = ref(false)
    const busy = ref('')
    const busyLabel = ref('')
    const waited = ref(0)
    const creating = ref(false)
    const uploadOpen = ref(false)
    const expanded = reactive<Record<string, boolean>>({})
    const draft = reactive({
      topic: '',
      language: store.prefs.language as Lang,
      level: store.prefs.level as Level,
      mode: store.prefs.mode as Mode,
    })

    const load = () => api.topics().then((r) => (items.value = r)).catch((e) => (error.value = e.message))
    onMounted(load)

    const hasActiveFilters = computed(() => !!(lang.value || level.value || mode.value || status.value || q.value.trim()))

    const filterSummary = computed(() => {
      const parts: string[] = []
      if (lang.value) parts.push(LANG_NAMES[lang.value] || lang.value)
      if (level.value) parts.push(LEVEL_NAMES[level.value] || level.value)
      if (mode.value) parts.push(MODE_NAMES[mode.value as Mode] || mode.value)
      if (status.value === 'todo') parts.push('未开始')
      if (status.value === 'progress') parts.push('未完成')
      if (status.value === 'done') parts.push('已完成')
      return parts.join(' · ')
    })

    const flatShown = computed(() => {
      const needle = q.value.trim().toLowerCase()
      return (items.value || []).filter((t) => {
        if (lang.value && t.language !== lang.value) return false
        if (level.value && t.level !== level.value) return false
        if (mode.value && t.mode !== mode.value) return false
        if (status.value && topicStatus(t) !== status.value) return false
        if (!needle) return true
        const base = groupKeyOf(t).toLowerCase()
        return base.includes(needle) || [t.topic, t.title].some((x) => (x || '').toLowerCase().includes(needle))
      })
    })

    const groups = computed(() => {
      const map = new Map<string, TopicItem[]>()
      for (const t of flatShown.value) {
        const key = groupKeyOf(t)
        const list = map.get(key) || []
        list.push(t)
        map.set(key, list)
      }
      return [...map.entries()].map(([topic, list]) => {
        const items = list.slice().sort((a, b) =>
          String(b.updatedAt || b.createdAt).localeCompare(String(a.updatedAt || a.createdAt)))
        const modes = [...new Set(items.map((i) => MODE_NAMES[i.mode as Mode] || i.mode).filter(Boolean))]
        const langs = [...new Set(items.map((i) => LANG_NAMES[i.language || 'en'] || i.language))]
        const levels = [...new Set(items.map((i) => LEVEL_NAMES[i.level || ''] || i.level).filter(Boolean))]
        return {
          key: topic,
          topic,
          items,
          summary: [langs.join('/'), levels.join('/'), modes.join(' · ')].filter(Boolean).join(' · '),
          latest: items[0]?.updatedAt || items[0]?.createdAt || '',
          attempts: items.reduce((n, i) => n + (i.attempts || 0), 0),
        }
      }).sort((a, b) => String(b.latest).localeCompare(String(a.latest)))
    })

    function clearFilters() {
      q.value = ''
      lang.value = ''
      level.value = ''
      mode.value = ''
      status.value = ''
    }

    function isOpen(g: { key: string; items: TopicItem[] }) {
      if (expanded[g.key] !== undefined) return expanded[g.key]
      return g.items.length === 1
    }

    function toggleGroup(g: { key: string; items: TopicItem[] }) {
      expanded[g.key] = !isOpen(g)
    }

    function displayTitle(t: TopicItem, groupTopic: string) {
      const title = (t.title || '').trim()
      if (!title || baseTopicName(title) === groupTopic) return ''
      return title
    }

    function openCreate() {
      draft.topic = ''
      draft.language = store.prefs.language
      draft.level = store.prefs.level
      draft.mode = store.prefs.mode
      creating.value = true
      error.value = ''
    }

    function openUpload() {
      uploadOpen.value = true
      error.value = ''
    }

    function onUploadBusy(p: { on: boolean; topicImport?: boolean; waited?: number }) {
      if (p.on) {
        busy.value = 'upload'
        busyLabel.value = p.topicImport ? '正在导入话题…' : '正在整理课程包…'
        waited.value = typeof p.waited === 'number' ? p.waited : 0
      } else {
        busy.value = ''
        busyLabel.value = ''
      }
    }

    async function onImported() {
      await load()
    }

    function open(t: TopicItem) {
      router.push(`/practice/${t.id}`)
    }
    async function reuse(t: TopicItem) {
      error.value = ''
      busy.value = t.id
      busyLabel.value = `正在打开「${t.topic}」…`
      try {
        const r = await api.repeat(t.id)
        router.push(`/practice/${r.id}`)
      } catch (e: any) {
        error.value = e.message
      } finally {
        busy.value = ''
      }
    }
    async function regen(t: TopicItem) {
      if (!t.topic || !t.language || !t.level || !t.mode) return
      if (!window.confirm(`重新生成「${t.topic}」？会再调用一次模型，得到一套新题。`)) return
      error.value = ''
      busy.value = t.id
      busyLabel.value = `正在重新生成「${t.topic}」…`
      waited.value = 0
      try {
        const r = await api.generate({
          language: t.language as Lang,
          level: t.level as Level,
          mode: t.mode as Mode,
          topic: t.topic,
          count: store.prefs.count,
          focus: '',
        }, (s) => (waited.value = s))
        router.push(`/practice/${r.id}`)
      } catch (e: any) {
        error.value = e.message
      } finally {
        busy.value = ''
      }
    }
    async function remove(t: TopicItem) {
      if (!t.topic || !t.language || !t.level || !t.mode) return
      const n = t.attempts || 1
      if (!window.confirm(`删除「${t.topic}」？会去掉该语言、级别、形式下的全部 ${n} 次练习记录，不能恢复。`)) return
      error.value = ''
      busy.value = t.id
      busyLabel.value = `正在删除「${t.topic}」…`
      try {
        await api.deleteTopic({
          language: t.language, level: t.level, mode: t.mode, topic: t.topic,
        })
        await load()
      } catch (e: any) {
        error.value = e.message
      } finally {
        busy.value = ''
      }
    }
    async function create() {
      const topic = draft.topic.trim()
      if (!topic || busy.value) return
      error.value = ''
      busy.value = 'create'
      busyLabel.value = `正在生成「${topic}」…`
      waited.value = 0
      setPrefs({ language: draft.language, level: draft.level, mode: draft.mode, topic })
      try {
        const r = await api.generate({
          language: draft.language,
          level: draft.level,
          mode: draft.mode,
          topic,
          count: store.prefs.count,
          focus: '',
        }, (s) => (waited.value = s))
        creating.value = false
        router.push(`/practice/${r.id}`)
      } catch (e: any) {
        error.value = e.message
      } finally {
        busy.value = ''
      }
    }

    return {
      items, error, q, lang, level, mode, status, levels: LEVELS, modes: MODES,
      filtersOpen, filterSummary, flatShown, groups, expanded, hasActiveFilters,
      clearFilters, isOpen, toggleGroup, displayTitle,
      busy, busyLabel, waited, creating, uploadOpen, draft,
      open, openCreate, openUpload, onUploadBusy, onImported, reuse, regen, remove, create,
      LANG_NAMES, LEVEL_NAMES, MODE_NAMES, dateTime, scoreBand,
    }
  },
})
</script>
