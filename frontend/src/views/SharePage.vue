<template>
  <div class="share-page">
    <header class="topbar">
      <RouterLink to="/" class="brand"><AppIcon name="logo" :size="30" /><span class="brand__name">LangStudy</span></RouterLink>
      <span class="topbar__sep" aria-hidden="true" />
      <span class="topbar__tagline">分享的练习报告（只读）</span>
    </header>
    <main class="page share-page__main">
      <p v-if="error" class="banner banner--error"><AppIcon name="alert" /> {{ error }}</p>
      <p v-else-if="!data" class="hint">正在读取报告…</p>
      <ReportView v-else readonly :owner="data.owner" :report="data.report" :content="data.content" session-id="shared"
        :env="env" :audio-base="`/api/share/${token}/audio/`" />
    </main>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, onMounted, ref, shallowRef } from 'vue'
import { useRoute } from 'vue-router'
import ReportView from '../components/report/ReportView.vue'
import AppIcon from '../components/ui/AppIcon.vue'
import { api, type SharedReport } from '../api'
import { envFor } from '../store'
import { setServerTTS } from '../lib/audio'

/** Public, read-only report opened from a share link (no login). */
export default defineComponent({
  name: 'SharePage',
  components: { AppIcon, ReportView },
  setup() {
    const token = useRoute().params.token as string
    const data = shallowRef<SharedReport | null>(null)
    const error = ref('')
    const env = computed(() => envFor(data.value?.content.language || 'en'))
    onMounted(async () => {
      setServerTTS(false) // not signed in: read aloud with the browser's voices
      try {
        data.value = await api.shared(token)
      } catch (e: any) {
        error.value = e.status === 404 ? '这个分享链接不存在，或者已经被关闭了。' : e.message
      }
    })
    return { token, data, error, env }
  },
})
</script>
