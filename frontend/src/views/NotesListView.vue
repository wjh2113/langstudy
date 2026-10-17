<template>
  <div class="page notes-list">
    <header class="page-head"><h1>我的学习笔记</h1></header>
    <div class="searchrow">
      <label class="input input--search"><AppIcon name="search" :size="18" />
        <input v-model="q" placeholder="搜索笔记话题、关键词…" aria-label="搜索笔记" /></label>
    </div>
    <div class="chips">
      <button v-for="f in filters" :key="f.key" type="button" :class="['chip', { on: filter === f.key }]" @click="filter = f.key">{{ f.label }}</button>
    </div>
    <p v-if="error" class="banner banner--error">{{ error }}</p>
    <div v-if="items && !shown.length" class="empty card">
      <AppIcon name="book" :size="32" />
      <p v-if="items.length">没有符合条件的笔记。</p>
      <p v-else>还没有保存的笔记。做练习时点上方的“学习笔记”，或在报告底部生成，生成后会出现在这里。</p>
    </div>
    <div class="nl-grid">
      <RouterLink v-for="s in shown" :key="s.id" :to="`/notes/${s.id}`" class="card nl-card">
        <div class="nl-card__top">
          <span :class="['tag', 'tag--solid', `tag--${s.language}`]">{{ LANG_NAMES[s.language] }}</span>
          <span class="muted">{{ dateOnly(s.generatedAt) }}</span>
        </div>
        <h3>{{ s.topic }}</h3>
        <p class="muted nl-card__sum">{{ s.summary || s.title }}</p>
        <div class="nl-card__counts">
          <span><AppIcon name="book" /><small>单词</small><strong>{{ s.counts.vocabulary }}</strong></span>
          <span><AppIcon name="doc" /><small>语法</small><strong>{{ s.counts.grammar }}</strong></span>
          <span><AppIcon name="chat-dots" /><small>句型</small><strong>{{ s.counts.patterns }}</strong></span>
        </div>
      </RouterLink>
    </div>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, onMounted, ref } from 'vue'
import AppIcon from '../components/ui/AppIcon.vue'
import { api } from '../api'
import { LANG_NAMES, MODE_NAMES, dateOnly } from '../lib/format'

export default defineComponent({
  name: 'NotesListView',
  components: { AppIcon },
  setup() {
    const items = ref<any[] | null>(null)
    const error = ref('')
    const q = ref('')
    const filter = ref('all')
    onMounted(() => api.notesList().then((r) => (items.value = r)).catch((e) => (error.value = e.message)))
    const filters = computed(() => {
      const modes = [...new Set((items.value || []).map((s) => s.mode))]
      return [{ key: 'all', label: '全部' }, { key: 'en', label: '英语' }, { key: 'ja', label: '日语' },
        ...modes.map((m) => ({ key: `m:${m}`, label: MODE_NAMES[m as keyof typeof MODE_NAMES] || m }))]
    })
    const shown = computed(() => (items.value || []).filter((s) => {
      const f = filter.value
      if (f === 'en' || f === 'ja') { if (s.language !== f) return false } else if (f.startsWith('m:') && s.mode !== f.slice(2)) return false
      const t = q.value.trim().toLowerCase()
      return !t || [s.topic, s.title, s.summary].some((x) => (x || '').toLowerCase().includes(t))
    }))
    return { items, error, q, filter, filters, shown, LANG_NAMES, dateOnly }
  },
})
</script>
