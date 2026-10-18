<template>
  <div class="page topics">
    <header class="page-head">
      <h1>话题管理</h1>
      <div class="page-head__actions">
        <button v-if="isAdmin" type="button" class="btn btn--outline btn--sm" :disabled="!!busy" @click="openImport">
          <AppIcon name="doc" :size="16" /> 导入
        </button>
        <button type="button" class="btn btn--primary btn--sm" @click="openCreate">
          <AppIcon name="plus" :size="16" /> 新增话题
        </button>
      </div>
    </header>
    <div class="searchrow">
      <label class="input input--search"><AppIcon name="search" :size="18" />
        <input v-model="q" placeholder="搜索话题、标题…" aria-label="搜索话题" /></label>
    </div>
    <div class="chips">
      <button v-for="f in filters" :key="f.key" type="button" :class="['chip', { on: filter === f.key }]" @click="filter = f.key">{{ f.label }}</button>
    </div>
    <p v-if="error" class="banner banner--error"><AppIcon name="alert" /> {{ error }}</p>
    <p v-if="busy" class="banner banner--info"><span class="spinner" /> {{ busyLabel }} {{ waited ? waited + ' 秒' : '' }}</p>

    <div v-if="items && !shown.length" class="empty card">
      <AppIcon name="list" :size="32" />
      <p v-if="items.length">没有符合条件的话题。</p>
      <p v-else>还没有话题。点「新增话题」生成练习<template v-if="isAdmin">，或点「导入」上传 Markdown</template>。</p>
      <div class="empty__actions">
        <button v-if="isAdmin" type="button" class="btn btn--outline" @click="openImport">导入</button>
        <button type="button" class="btn btn--primary" @click="openCreate">新增话题</button>
      </div>
    </div>

    <section v-if="shown.length" class="card card--flush">
      <div class="table-wrap">
        <table class="table topics-table">
          <thead>
            <tr>
              <th><AppIcon name="chat" :size="16" /> 话题</th>
              <th><AppIcon name="globe" :size="16" /> 语言</th>
              <th><AppIcon name="bars" :size="16" /> 级别</th>
              <th><AppIcon name="doc" :size="16" /> 形式</th>
              <th><AppIcon name="clock" :size="16" /> 最近</th>
              <th><AppIcon name="list" :size="16" /> 次数</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in shown" :key="t.id">
              <td class="topics-table__topic">
                <strong>{{ t.topic }}</strong>
                <span class="muted">{{ t.title }}</span>
                <span v-if="!t.done && (t.answered || 0) > 0" class="tag tag--warn tag--sm">未完成 · 已答 {{ t.answered }}</span>
                <span v-else-if="!t.done" class="tag tag--sm">未开始</span>
                <span v-else-if="t.overall != null" :class="['score-text', scoreBand(t.overall)]">{{ t.overall }} 分</span>
              </td>
              <td><span :class="['tag', `tag--${t.language}`]">{{ LANG_NAMES[t.language || 'en'] }}</span></td>
              <td>{{ LEVEL_NAMES[t.level || ''] || t.level || '—' }}</td>
              <td><span class="tag tag--mode">{{ MODE_NAMES[t.mode] || t.mode }}</span></td>
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

    <ModalDialog :open="importing" title="导入话题" icon="doc" wide @close="closeImport">
      <p class="muted">上传别的模型写好的 <code>.md</code> 或 <code>.zip</code>。相同「语言 + 话题 + 级别 + 形式」会覆盖旧练习。</p>
      <details class="upload-prompt">
        <summary>发给其他模型的说明</summary>
        <textarea class="import-prompt" readonly :value="prompt" rows="10" />
        <button type="button" class="btn btn--outline btn--sm" :disabled="!prompt" @click="copyPrompt">
          <AppIcon name="copy" :size="14" /> {{ copiedPrompt ? '已复制' : '复制说明' }}
        </button>
      </details>
      <label class="upload-pick">
        <input type="file" accept=".md,.zip,text/markdown,application/zip" :disabled="!!busy" @change="onImportFile" />
        <span>{{ importFile ? importFile.name : '选择 .md 或 .zip' }}</span>
      </label>
      <p v-if="imported.length && importReplaced" class="banner banner--info">
        已按「语言 + 话题 + 级别 + 形式」覆盖原先 {{ importReplaced }} 份练习。
      </p>
      <ul v-if="imported.length" class="import-list">
        <li v-for="item in imported" :key="item.id">
          <RouterLink :to="`/practice/${item.id}`" @click="closeImport">{{ item.topic }}</RouterLink>
          <span class="tag tag--mode">{{ MODE_NAMES[item.mode] || item.mode }}</span>
          <span v-if="item.hasNotes" class="muted">含学习笔记</span>
          <span v-if="item.replaced" class="muted">已覆盖 {{ item.replaced }} 份</span>
        </li>
      </ul>
      <p v-for="(msg, i) in importErrors" :key="'ie'+i" class="banner banner--error"><AppIcon name="alert" /> {{ msg }}</p>
      <div class="modal__actions">
        <button type="button" class="btn btn--ghost" @click="closeImport">{{ imported.length ? '关闭' : '取消' }}</button>
        <button type="button" class="btn btn--primary" :disabled="!!busy || !importFile" @click="runImport">
          {{ busy === 'import' ? '正在导入…' : '导入话题' }}
        </button>
      </div>
    </ModalDialog>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppIcon from '../components/ui/AppIcon.vue'
import ModalDialog from '../components/ui/ModalDialog.vue'
import { api, type TopicItem } from '../api'
import type { Lang, Level, Mode } from '../api/models'
import { isAdmin, setPrefs, store } from '../store'
import { LANG_NAMES, LEVEL_NAMES, MODE_NAMES, dateTime, scoreBand } from '../lib/format'

const MODES: { key: Mode; name: string }[] = [
  { key: 'questions', name: '话题问答' },
  { key: 'dialogue', name: '情景对话' },
  { key: 'article', name: '短文' },
  { key: 'chat', name: '自由对话' },
  { key: 'dictation', name: '精听填空' },
]

export default defineComponent({
  name: 'TopicsView',
  components: { AppIcon, ModalDialog },
  setup() {
    const router = useRouter()
    const items = ref<TopicItem[] | null>(null)
    const error = ref('')
    const q = ref('')
    const filter = ref('all')
    const busy = ref('')
    const busyLabel = ref('')
    const waited = ref(0)
    const creating = ref(false)
    const importing = ref(false)
    const importFile = ref<File | null>(null)
    const imported = ref<{ id: string; topic: string; mode: string; title: string; hasNotes: boolean; replaced?: number }[]>([])
    const importErrors = ref<string[]>([])
    const importReplaced = ref(0)
    const prompt = ref('')
    const copiedPrompt = ref(false)
    const draft = reactive({
      topic: '',
      language: store.prefs.language as Lang,
      level: store.prefs.level as Level,
      mode: store.prefs.mode as Mode,
    })

    const load = () => api.topics().then((r) => (items.value = r)).catch((e) => (error.value = e.message))
    onMounted(load)

    const filters = computed(() => {
      const modes = [...new Set((items.value || []).map((t) => t.mode).filter(Boolean))] as string[]
      return [
        { key: 'all', label: '全部' },
        { key: 'en', label: '英语' },
        { key: 'ja', label: '日语' },
        ...modes.map((m) => ({ key: `m:${m}`, label: (MODE_NAMES as Record<string, string>)[m] || m })),
      ]
    })
    const shown = computed(() => (items.value || []).filter((t) => {
      const f = filter.value
      if (f === 'en' || f === 'ja') { if (t.language !== f) return false }
      else if (f.startsWith('m:') && t.mode !== f.slice(2)) return false
      const needle = q.value.trim().toLowerCase()
      return !needle || [t.topic, t.title].some((x) => (x || '').toLowerCase().includes(needle))
    }))

    function openCreate() {
      draft.topic = ''
      draft.language = store.prefs.language
      draft.level = store.prefs.level
      draft.mode = store.prefs.mode
      creating.value = true
      error.value = ''
    }
    async function openImport() {
      importing.value = true
      importFile.value = null
      imported.value = []
      importErrors.value = []
      importReplaced.value = 0
      error.value = ''
      if (!prompt.value) {
        try { prompt.value = (await api.importPrompt()).prompt } catch (e: any) { error.value = e.message }
      }
    }
    function closeImport() {
      importing.value = false
      importFile.value = null
    }
    function onImportFile(e: Event) {
      const input = e.target as HTMLInputElement
      importFile.value = input.files?.[0] || null
      imported.value = []
      importErrors.value = []
      importReplaced.value = 0
    }
    async function copyPrompt() {
      if (!prompt.value) return
      try {
        await navigator.clipboard.writeText(prompt.value)
      } catch {
        window.prompt('复制下面的内容：', prompt.value)
      }
      copiedPrompt.value = true
      setTimeout(() => { copiedPrompt.value = false }, 1500)
    }
    async function runImport() {
      if (!importFile.value || busy.value) return
      error.value = ''
      importErrors.value = []
      busy.value = 'import'
      busyLabel.value = '正在导入话题…'
      try {
        const result = await api.importTopics(importFile.value)
        imported.value = result.imported
        importErrors.value = result.errors || []
        importReplaced.value = result.replaced || 0
        if (result.imported.length) await load()
        if (result.imported.length === 1 && !result.errors?.length) {
          closeImport()
          router.push(`/practice/${result.imported[0].id}`)
        }
      } catch (e: any) {
        error.value = e.message
      } finally {
        busy.value = ''
      }
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
      items, error, q, filter, filters, shown, busy, busyLabel, waited, creating, draft, modes: MODES,
      isAdmin, importing, importFile, imported, importErrors, importReplaced, prompt, copiedPrompt,
      open, openCreate, openImport, closeImport, onImportFile, copyPrompt, runImport,
      reuse, regen, remove, create,
      LANG_NAMES, LEVEL_NAMES, MODE_NAMES, dateTime, scoreBand,
    }
  },
})
</script>
