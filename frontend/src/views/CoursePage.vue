<template>
  <div v-if="error" class="page"><p class="banner banner--error"><AppIcon name="alert" /> {{ error }}</p>
    <RouterLink to="/" class="btn btn--ghost">回到首页</RouterLink></div>
  <div v-else-if="!course" class="page"><p class="hint">正在打开课程包…</p></div>
  <div v-else class="page course">
    <header class="page-head">
      <div>
        <p class="muted">{{ course.sourceName }}</p>
        <h1>{{ course.title }}</h1>
        <p class="muted">{{ course.topic }} · 可以按顺序做，也可以挑一项开始</p>
      </div>
      <button v-if="first" type="button" class="btn btn--primary" @click="open(first)">从第一项开始</button>
    </header>

    <ol class="course__list">
      <li v-for="(item, i) in course.items" :key="item.key + i" class="card course__item">
        <span class="course__no">{{ i + 1 }}</span>
        <div>
          <h2>{{ item.title }}</h2>
          <p class="muted">{{ item.blurb }}</p>
        </div>
        <button type="button" class="btn btn--ghost btn--sm" :disabled="!item.sessionId" @click="open(item)">
          {{ item.kind === 'notes' ? '查看笔记' : '开始' }}
        </button>
      </li>
    </ol>

    <section v-if="notesId && env" id="course-notes" class="course__notes">
      <StudyNotes :session-id="notesId" :env="env" locked />
    </section>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '../components/ui/AppIcon.vue'
import StudyNotes from '../components/practice/StudyNotes.vue'
import { api } from '../api'
import type { CourseItem, CoursePack, Lang } from '../api/models'
import { envFor } from '../store'

export default defineComponent({
  name: 'CoursePage',
  components: { AppIcon, StudyNotes },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const course = ref<CoursePack | null>(null)
    const error = ref('')
    const notesId = computed(() => course.value?.items.find((it) => it.kind === 'notes')?.sessionId || '')
    const first = computed(() => course.value?.items.find((it) => it.kind !== 'notes' && it.sessionId) || null)
    const env = computed(() => (course.value ? envFor(course.value.language as Lang) : null))

    onMounted(async () => {
      try {
        course.value = await api.course(route.params.id as string)
      } catch (e: any) {
        error.value = e.message
      }
    })

    function open(item: CourseItem) {
      if (item.kind === 'notes') {
        document.getElementById('course-notes')?.scrollIntoView({ behavior: 'smooth' })
        return
      }
      if (item.sessionId) router.push(`/practice/${item.sessionId}`)
    }

    return { course, error, notesId, first, env, open }
  },
})
</script>
