<template>
  <div class="history">
    <div class="history__head">
      <h1>历史记录</h1>
      <label v-if="isAdmin" class="switch">
        <input v-model="showAll" type="checkbox" @change="load" />
        <span>显示所有用户的记录</span>
      </label>
    </div>
    <template v-for="l in ['en', 'ja']" :key="l">
      <section v-if="trendOf(l).length > 1" class="trend-box">
        <h2>{{ langNames[l] }} 综合得分变化</h2>
        <TrendChart :points="trendOf(l)" />
      </section>
    </template>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="items && !items.length" class="empty">还没有练习记录。回到“新的练习”，输入一个话题开始吧。</p>
    <table v-if="items && items.length" class="table">
      <thead>
        <tr><th>时间</th><th v-if="showAll">用户</th><th>语言</th><th>形式</th><th>话题</th><th>得分</th><th /></tr>
      </thead>
      <tbody>
        <tr v-for="s in items" :key="s.id">
          <td class="nowrap">{{ s.createdAt.replace('T', ' ').slice(5, 16) }}</td>
          <td v-if="showAll">{{ s.username || '—' }}</td>
          <td>{{ langNames[s.language] || s.language }}</td>
          <td>{{ modeNames[s.mode] }}</td>
          <td>
            <button class="link" @click="$emit('open', s.id)">{{ s.topic }}</button>
            <span class="muted table__title">{{ s.title }}<span v-if="s.hasNotes" class="tag tag--sm">笔记</span></span>
          </td>
          <td>
            <strong v-if="s.done">{{ s.overall ?? '—' }}</strong>
            <span v-else class="muted">未完成</span>
          </td>
          <td><button class="link link--muted" @click="remove(s.id)">删除</button></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>
import { onMounted, reactive, ref } from 'vue'
import TrendChart from './TrendChart.vue'
import { api } from '../api'

export default {
  name: 'HistoryView',
  components: { TrendChart },
  props: { isAdmin: { type: Boolean, default: false } },
  emits: ['open'],
  setup() {
    const showAll = ref(false)
    const items = ref(null)
    const error = ref('')
    const trend = reactive({ en: [], ja: [] })

    const load = () => api.sessions(showAll.value).then((r) => (items.value = r)).catch((e) => (error.value = e.message))
    onMounted(() => {
      load()
      for (const l of ['en', 'ja']) api.progress(l).then((r) => (trend[l] = r)).catch(() => {})
    })

    async function remove(id) {
      await api.deleteSession(id).catch(() => {})
      load()
    }

    return {
      items, error, remove, load, showAll,
      trendOf: (l) => trend[l].filter((p) => p.overall != null),
      langNames: { en: 'English', ja: '日本語' },
      modeNames: { article: '短文', dialogue: '情景对话', questions: '话题问答', chat: '自由对话', dictation: '精听填空' },
    }
  },
}
</script>
