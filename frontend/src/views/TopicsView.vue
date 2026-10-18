<template>
  <div class="page topics">
    <header class="page-head">
      <h1>话题管理</h1>
      <RouterLink to="/" class="btn btn--ghost btn--sm"><AppIcon name="plus" :size="16" /> 去首页出新题</RouterLink>
    </header>
    <div class="searchrow">
      <label class="input input--search"><AppIcon name="search" :size="18" />
        <input v-model="q" placeholder="搜索话题、标题…" aria-label="搜索话题" /></label>
    </div>
    <div class="chips">
      <button v-for="f in filters" :key="f.key" type="button" :class="['chip', { on: filter === f.key }]" @click="filter = f.key">{{ f.label }}</button>
    </div>
    <p v-if="error" class="banner banner--error"><AppIcon name="alert" /> {{ error }}</p>
    <p v-if="busy" class="banner banner--info"><span class="spinner" /> 正在重新生成「{{ busyTopic }}」… {{ waited }} 秒</p>

    <div v-if="items && !shown.length" class="empty card">
      <AppIcon name="list" :size="32" />
      <p v-if="items.length">没有符合条件的话题。</p>
      <p v-else>还没有话题。回首页输入话题生成练习，或管理员上传导入的 Markdown。</p>
      <RouterLink to="/" class="btn btn--primary">回到首页</RouterLink>
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
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppIcon from '../components/ui/AppIcon.vue'
import { api, type TopicItem } from '../api'
import { store } from '../store'
import { LANG_NAMES, LEVEL_NAMES, MODE_NAMES, dateTime, scoreBand } from '../lib/format'

export default defineComponent({
  name: 'TopicsView',
  components: { AppIcon },
  setup() {
    const router = useRouter()
    const items = ref<TopicItem[] | null>(null)
    const error = ref('')
    const q = ref('')
    const filter = ref('all')
    const busy = ref('')
    const busyTopic = ref('')
    const waited = ref(0)

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

    function open(t: TopicItem) {
      router.push(`/practice/${t.id}`)
    }
    async function reuse(t: TopicItem) {
      error.value = ''
      busy.value = t.id
      busyTopic.value = t.topic || ''
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
      busyTopic.value = t.topic
      waited.value = 0
      try {
        const r = await api.generate({
          language: t.language as any,
          level: t.level as any,
          mode: t.mode as any,
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

    return {
      items, error, q, filter, filters, shown, busy, busyTopic, waited,
      open, reuse, regen, LANG_NAMES, LEVEL_NAMES, MODE_NAMES, dateTime, scoreBand,
    }
  },
})
</script>
