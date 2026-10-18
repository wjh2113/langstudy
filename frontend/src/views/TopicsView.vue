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
      <p class="topics-toolbar__meta muted">
        显示 {{ flatShown.length }} / {{ items?.length || 0 }}
        <button v-if="hasActiveFilters" type="button" class="btn btn--ghost btn--sm" @click="clearFilters">清除筛选</button>
      </p>
    </div>

    <div class="topics-filters">
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

    <div v-if="groups.length" class="topics-groups">
      <section v-for="g in groups" :key="g.key" class="card card--flush topics-group">
        <button type="button" class="topics-group__head" @click="toggleGroup(g.key)">
          <AppIcon :name="collapsed[g.key] ? 'chevron-right' : 'chevron-down'" :size="18" />
          <strong>{{ g.topic }}</strong>
          <span class="muted">{{ g.items.length }} 种</span>
        </button>
        <div v-show="!collapsed[g.key]" class="table-wrap">
          <table class="table topics-table">
            <thead>
              <tr>
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
              <tr v-for="t in g.items" :key="t.id">
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
                <td class="topics-table__actions">
                  <button v-if="!t.done" type="button" class="btn btn--sm btn--primary" :disabled="!!busy" @click="open(t)">
                    {{ (t.answered || 0) > 0 ? '继续' : '开始' }}
                  </button>
                  <button v-else type="button" class="btn btn--sm btn--outline" :disabled="!!busy" @click="reuse(t)">用上次的题</button>
                  <button type="button" class="btn btn--sm btn--ghost" :disabled="!!busy" @click="regen(t)">
                    <AppIcon name="refresh" :size="14" /> 重新生成
                  </button>
                  <button type="button" class="btn btn--sm btn--ghost" :disabled="!!busy" @click="remove(t)">
                    <AppIcon name="trash" :size="14" /> 删除
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

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

type StatusFilter = '' | 'todo' | 'progress' | 'done'

function topicStatus(t: TopicItem): StatusFilter {
  if (t.done) return 'done'
  if ((t.answered || 0) > 0) return 'progress'
  return 'todo'
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
    const busy = ref('')
    const busyLabel = ref('')
    const waited = ref(0)
    const creating = ref(false)
    const uploadOpen = ref(false)
    const collapsed = reactive<Record<string, boolean>>({})
    const draft = reactive({
      topic: '',
      language: store.prefs.language as Lang,
      level: store.prefs.level as Level,
      mode: store.prefs.mode as Mode,
    })

    const load = () => api.topics().then((r) => (items.value = r)).catch((e) => (error.value = e.message))
    onMounted(load)

    const hasActiveFilters = computed(() => !!(q.value.trim() || lang.value || level.value || mode.value || status.value))

    const flatShown = computed(() => {
      const needle = q.value.trim().toLowerCase()
      return (items.value || []).filter((t) => {
        if (lang.value && t.language !== lang.value) return false
        if (level.value && t.level !== level.value) return false
        if (mode.value && t.mode !== mode.value) return false
        if (status.value && topicStatus(t) !== status.value) return false
        if (!needle) return true
        return [t.topic, t.title].some((x) => (x || '').toLowerCase().includes(needle))
      })
    })

    const groups = computed(() => {
      const map = new Map<string, TopicItem[]>()
      for (const t of flatShown.value) {
        const key = (t.topic || t.title || '未命名').trim() || '未命名'
        const list = map.get(key) || []
        list.push(t)
        map.set(key, list)
      }
      return [...map.entries()].map(([topic, list]) => ({
        key: topic,
        topic,
        items: list.slice().sort((a, b) => String(b.updatedAt || b.createdAt).localeCompare(String(a.updatedAt || a.createdAt))),
      })).sort((a, b) => {
        const at = a.items[0]?.updatedAt || a.items[0]?.createdAt || ''
        const bt = b.items[0]?.updatedAt || b.items[0]?.createdAt || ''
        return String(bt).localeCompare(String(at))
      })
    })

    function clearFilters() {
      q.value = ''
      lang.value = ''
      level.value = ''
      mode.value = ''
      status.value = ''
    }

    function toggleGroup(key: string) {
      collapsed[key] = !collapsed[key]
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
      flatShown, groups, collapsed, hasActiveFilters, clearFilters, toggleGroup,
      busy, busyLabel, waited, creating, uploadOpen, draft,
      open, openCreate, openUpload, onUploadBusy, onImported, reuse, regen, remove, create,
      LANG_NAMES, LEVEL_NAMES, MODE_NAMES, dateTime, scoreBand,
    }
  },
})
</script>
