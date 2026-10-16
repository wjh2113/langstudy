<template>
  <div class="notes-page">
    <template v-if="!openId">
      <h1>学习笔记</h1>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="items && !items.length" class="empty">
        还没有保存的笔记。做练习时点上方的“学习笔记”，或在报告底部生成，生成后会出现在这里。
      </p>
      <div v-if="items && items.length" class="notes-list">
        <button v-for="s in items" :key="s.id" class="notes-list__item" @click="openId = s.id">
          <span class="notes-list__meta">{{ langNames[s.language] }} · {{ modeNames[s.mode] }} · {{ s.generatedAt.slice(0, 10) }}</span>
          <strong>{{ s.topic }}</strong>
          <span class="muted">{{ s.summary || s.title }}</span>
          <span class="notes-list__counts">单词 {{ s.counts.vocabulary }} · 语法 {{ s.counts.grammar }} · 句型 {{ s.counts.patterns }}</span>
        </button>
      </div>
    </template>

    <template v-else>
      <div class="notes-page__bar">
        <button class="link" @click="openId = null">← 全部笔记</button>
        <button class="btn btn--ghost" @click="$emit('open-session', openId)">{{ current && current.done ? '查看练习报告' : '继续这个练习' }}</button>
      </div>
      <p class="crumbs">{{ current && current.topic }}</p>
      <StudyNotes :key="openId" :session-id="openId" :env="noteEnv" @generated="load" />
    </template>
  </div>
</template>

<script>
import { computed, onMounted, ref } from 'vue'
import StudyNotes from './StudyNotes.vue'
import { api } from '../api'

export default {
  name: 'NotesView',
  components: { StudyNotes },
  props: {
    env: { type: Object, required: true },
    envFor: { type: Function, required: true }, // language -> env for that language
  },
  emits: ['open-session'],
  setup(props) {
    const items = ref(null)
    const error = ref('')
    const openId = ref(null)
    const current = computed(() => items.value?.find((s) => s.id === openId.value))
    const noteEnv = computed(() => (current.value ? props.envFor(current.value.language) : props.env))

    const load = () => api.notesList().then((r) => (items.value = r)).catch((e) => (error.value = e.message))
    onMounted(load)

    return {
      items, error, openId, current, noteEnv, load,
      langNames: { en: 'English', ja: '日本語' },
      modeNames: { article: '短文', dialogue: '情景对话', questions: '话题问答', chat: '自由对话', dictation: '精听填空' },
    }
  },
}
</script>
