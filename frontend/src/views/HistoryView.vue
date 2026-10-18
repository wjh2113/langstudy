<template>
  <div class="page history">
    <header class="page-head">
      <h1>练习历史</h1>
      <label v-if="isAdmin" class="inline-toggle">
        <ToggleSwitch v-model="showAll" label="显示所有用户的记录" @update:model-value="load" />
        <span>显示所有用户的记录</span>
      </label>
    </header>
    <div class="chips">
      <button v-for="f in filters" :key="f.key" type="button" :class="['chip', { on: filter === f.key }]" @click="filter = f.key">{{ f.label }}</button>
    </div>

    <section v-if="hasTrend" class="card">
      <div class="card__titlebar">
        <h2 class="card__title"><AppIcon name="trend" /> 近 30 天成绩趋势</h2>
        <div class="legend">
          <span v-for="s in series" :key="s.key" :class="`legend__item legend__item--${s.key}`"><i />{{ s.name }}</span>
        </div>
      </div>
      <TrendChart :series="series" :days="30" />
    </section>

    <p v-if="error" class="banner banner--error"><AppIcon name="alert" /> {{ error }}</p>
    <div v-if="items && !shown.length" class="empty card">
      <AppIcon name="clock" :size="32" />
      <p>还没有练习记录。回到首页，输入一个话题开始吧。</p>
      <RouterLink to="/" class="btn btn--primary">开始练习</RouterLink>
    </div>

    <!-- PC: table -->
    <section v-if="shown.length" class="card card--flush desktop-only">
      <div class="table-wrap">
        <table class="table history-table">
          <thead>
            <tr>
              <th><AppIcon name="clock" :size="16" /> 时间</th>
              <th v-if="showAll"><AppIcon name="user" :size="16" /> 用户</th>
              <th><AppIcon name="globe" :size="16" /> 语言</th>
              <th><AppIcon name="doc" :size="16" /> 形式</th>
              <th><AppIcon name="chat" :size="16" /> 话题</th>
              <th><AppIcon name="star" :size="16" /> 得分</th>
              <th><AppIcon name="note" :size="16" /> 笔记</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in shown" :key="s.id" class="clickable" @click="open(s)">
              <td class="nowrap">{{ dateTime(s.createdAt) }}</td>
              <td v-if="showAll">{{ s.username || '—' }}</td>
              <td><span :class="['tag', `tag--${s.language}`]">{{ LANG_NAMES[s.language || 'en'] }}</span></td>
              <td><span :class="['tag', 'tag--mode', `tag--mode-${s.mode}`]">{{ MODE_NAMES[s.mode] }}</span></td>
              <td class="history-table__topic">{{ s.topic }}<span class="muted">{{ s.title }}</span></td>
              <td>
                <strong v-if="s.done" :class="['score-text', scoreBand(s.overall)]">{{ s.overall ?? '—' }}</strong>
                <span v-else class="tag tag--warn">未完成 · 已答 {{ s.answered }}</span>
              </td>
              <td><RouterLink v-if="s.hasNotes" :to="`/notes/${s.id}`" class="icon-link" title="查看笔记" @click.stop><AppIcon name="note" /></RouterLink><span v-else class="muted">—</span></td>
              <td><button type="button" class="icon-btn icon-btn--danger" title="删除" aria-label="删除" @click.stop="remove(s)"><AppIcon name="trash" :size="16" /></button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Phone: cards -->
    <div v-if="shown.length" class="history-list mobile-only">
      <article
        v-for="s in shown"
        :key="'m-' + s.id"
        class="history-card card card--flush clickable"
        role="button"
        tabindex="0"
        @click="open(s)"
        @keydown.enter.prevent="open(s)"
      >
        <div class="history-card__top">
          <div class="history-card__tags">
            <span :class="['tag', `tag--${s.language}`]">{{ s.language === 'ja' ? '日语' : '英语' }}</span>
            <span :class="['tag', 'tag--mode', `tag--mode-${s.mode}`]">{{ MODE_NAMES[s.mode] }}</span>
            <span v-if="showAll && s.username" class="tag tag--sm">{{ s.username }}</span>
          </div>
          <span class="muted history-card__when">{{ dateTime(s.createdAt) }}</span>
        </div>
        <h3 class="history-card__topic">{{ s.topic }}</h3>
        <p v-if="s.title && s.title !== s.topic" class="muted history-card__title">{{ s.title }}</p>
        <div class="history-card__foot">
          <strong v-if="s.done" :class="['score-text', scoreBand(s.overall)]">{{ s.overall ?? '—' }} 分</strong>
          <span v-else class="tag tag--warn">未完成 · 已答 {{ s.answered }}</span>
          <div class="history-card__actions" @click.stop>
            <RouterLink v-if="s.hasNotes" :to="`/notes/${s.id}`" class="icon-btn" title="查看笔记" aria-label="查看笔记">
              <AppIcon name="note" :size="16" />
            </RouterLink>
            <button type="button" class="icon-btn icon-btn--danger" title="删除" aria-label="删除" @click="remove(s)">
              <AppIcon name="trash" :size="16" />
            </button>
          </div>
        </div>
      </article>
    </div>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppIcon from '../components/ui/AppIcon.vue'
import ToggleSwitch from '../components/ui/ToggleSwitch.vue'
import TrendChart, { type TrendSeries } from '../components/ui/TrendChart.vue'
import { api, type SessionSummary } from '../api'
import { isAdmin } from '../store'
import { LANG_NAMES, MODE_NAMES, dateTime, scoreBand } from '../lib/format'

export default defineComponent({
  name: 'HistoryView',
  components: { AppIcon, ToggleSwitch, TrendChart },
  setup() {
    const router = useRouter()
    const showAll = ref(false)
    const items = ref<SessionSummary[] | null>(null)
    const error = ref('')
    const filter = ref('all')
    const trend = ref<Record<string, { createdAt: string; overall: number | null }[]>>({ en: [], ja: [] })

    const load = () => api.sessions(showAll.value).then((r) => (items.value = r)).catch((e) => (error.value = e.message))
    onMounted(() => {
      load()
      for (const l of ['en', 'ja']) api.progress(l).then((r) => (trend.value = { ...trend.value, [l]: r })).catch(() => {})
    })

    const shown = computed(() => (items.value || []).filter((s) => filter.value === 'all' || s.language === filter.value))
    const series = computed<TrendSeries[]>(() => ['en', 'ja']
      .filter((l) => filter.value === 'all' || filter.value === l)
      .map((l) => ({ key: l, name: l === 'en' ? '英语' : '日语', points: trend.value[l] || [] })))
    const hasTrend = computed(() => series.value.some((s) => s.points.filter((p) => p.overall != null).length > 0))

    const open = (s: SessionSummary) => router.push(s.done ? `/report/${s.id}` : `/practice/${s.id}`)
    async function remove(s: SessionSummary) {
      if (!window.confirm(`删除「${s.topic}」这次练习？报告、录音和笔记会一起删除。`)) return
      await api.deleteSession(s.id).catch(() => {})
      load()
    }

    return {
      isAdmin, showAll, items, error, filter, shown, series, hasTrend, load, open, remove, dateTime, scoreBand, LANG_NAMES, MODE_NAMES,
      filters: [{ key: 'all', label: '全部' }, { key: 'en', label: '英语' }, { key: 'ja', label: '日语' }],
    }
  },
})
</script>
