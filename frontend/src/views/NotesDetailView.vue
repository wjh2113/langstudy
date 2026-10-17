<template>
  <div class="page notes-detail">
    <Teleport to="#header-center">
      <nav class="head-tabs" role="tablist">
        <RouterLink :to="practiceLink" role="tab" aria-selected="false">{{ done ? '练习报告' : '练习' }}</RouterLink>
        <span role="tab" aria-selected="true" class="on">学习笔记</span>
      </nav>
    </Teleport>
    <p v-if="error" class="banner banner--error">{{ error }}</p>
    <template v-else-if="session">
      <header class="page-head">
        <div>
          <p class="crumbs"><RouterLink to="/notes" class="link"><AppIcon name="arrow-left" :size="14" /> 全部笔记</RouterLink></p>
          <h1>{{ topic }}</h1>
        </div>
      </header>
      <StudyNotes :session-id="id" :env="env" />
    </template>
    <p v-else class="hint">正在读取…</p>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { useRoute } from 'vue-router'
import StudyNotes from '../components/practice/StudyNotes.vue'
import AppIcon from '../components/ui/AppIcon.vue'
import { api, type SessionOut } from '../api'
import type { Content } from '../api/models'
import { envFor, store } from '../store'

export default defineComponent({
  name: 'NotesDetailView',
  components: { AppIcon, StudyNotes },
  setup() {
    const id = useRoute().params.id as string
    const session = shallowRef<SessionOut | null>(null)
    const error = ref('')
    const content = computed(() => (session.value?.content || {}) as unknown as Content)
    const env = computed(() => envFor(content.value.language || 'en'))
    const done = computed(() => Boolean(session.value?.report))
    onMounted(async () => {
      try {
        session.value = await api.session(id)
        store.pageLanguage = content.value.language
      } catch (e: any) {
        error.value = e.message
      }
    })
    onBeforeUnmount(() => { store.pageLanguage = null })
    return {
      id, session, error, env, done, topic: computed(() => content.value.topic),
      practiceLink: computed(() => (done.value ? `/report/${id}` : `/practice/${id}`)),
    }
  },
})
</script>
