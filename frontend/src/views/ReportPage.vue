<template>
  <div class="page">
    <p v-if="error" class="banner banner--error"><AppIcon name="alert" /> {{ error }}</p>
    <p v-else-if="!session" class="hint">正在读取报告…</p>
    <ReportView v-else :report="report" :content="content" :session-id="session.id" :env="env">
      <template #actions>
        <button type="button" class="btn btn--ghost" @click="share"><AppIcon name="share" :size="16" /> {{ session.shareToken ? '分享链接' : '分享报告' }}</button>
        <button type="button" class="btn btn--ghost" @click="router.push('/')">换个话题</button>
        <button type="button" class="btn btn--primary" :disabled="busy" @click="again"><AppIcon name="repeat" :size="16" /> 同话题再练一次</button>
      </template>
      <template #notice>
        <div v-if="report.cardsAdded || (coach && coach.level)" class="banner banner--ok">
          <AppIcon name="check-circle" />
          <span v-if="report.cardsAdded">已把 {{ report.cardsAdded }} 句改正后的句子加入错句本。<RouterLink to="/review" class="link">去复习</RouterLink></span>
          <span v-if="coach && coach.level">下次建议：{{ coach.reason }}</span>
        </div>
      </template>
    </ReportView>

    <ModalDialog :open="shareOpen" title="分享报告" icon="share" @close="shareOpen = false">
      <p>拿到链接的人不用登录就能查看这份报告（只读，包括你的录音）。随时可以关闭分享，关闭后链接立即失效。</p>
      <div class="copy-row">
        <input :value="shareUrl" readonly aria-label="分享链接" @focus="selectAll" />
        <button type="button" class="btn btn--primary" @click="copy"><AppIcon name="copy" :size="16" /> {{ copied ? '已复制' : '复制链接' }}</button>
      </div>
      <div class="modal__actions">
        <button type="button" class="btn btn--ghost btn--danger" @click="unshare">关闭分享</button>
        <button type="button" class="btn btn--ghost" @click="shareOpen = false">完成</button>
      </div>
    </ModalDialog>

    <ModalDialog :open="againOpen" title="同话题再练一次" icon="repeat" @close="againOpen = false">
      <p>用同一套题再练一次不会重新调用 AI，马上就能开始；换一套会按这个话题重新出题。</p>
      <div class="modal__actions">
        <button type="button" class="btn btn--ghost" :disabled="busy" @click="newSet">换一套新题</button>
        <button type="button" class="btn btn--primary" :disabled="busy" @click="sameSet">用这套题再练</button>
      </div>
      <p v-if="busy" class="hint">正在生成… {{ waited }} 秒</p>
    </ModalDialog>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ReportView from '../components/report/ReportView.vue'
import AppIcon from '../components/ui/AppIcon.vue'
import ModalDialog from '../components/ui/ModalDialog.vue'
import { api, type SessionOut } from '../api'
import type { Coach, Content, Report } from '../api/models'
import { envFor, store } from '../store'
import { takeReport } from './reportCache'

export default defineComponent({
  name: 'ReportPage',
  components: { AppIcon, ModalDialog, ReportView },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const id = route.params.id as string
    const session = shallowRef<SessionOut | null>(null)
    const error = ref('')
    const coach = ref<Coach | null>(null)
    const content = computed(() => (session.value?.content || {}) as unknown as Content)
    const report = computed(() => (session.value?.report || {}) as unknown as Report)
    const env = computed(() => envFor(content.value.language || 'en'))
    const shareOpen = ref(false)
    const shareUrl = ref('')
    const copied = ref(false)
    const againOpen = ref(false)
    const busy = ref(false)
    const waited = ref(0)

    onMounted(async () => {
      try {
        const s = takeReport(id) || (await api.session(id))
        if (!s.report) return router.replace(`/practice/${id}`)
        session.value = s
        store.pageLanguage = (s.content as any).language
        api.coach((s.content as any).language).then((c) => (coach.value = c)).catch(() => {})
      } catch (e: any) {
        error.value = e.status === 404 ? '这份报告不存在，或者练习已经被删除了。' : e.message
      }
    })
    onBeforeUnmount(() => { store.pageLanguage = null })

    async function share() {
      try {
        const r = await api.share(id)
        shareUrl.value = location.origin + r.url
        session.value = { ...(session.value as SessionOut), shareToken: r.token }
        shareOpen.value = true
      } catch (e: any) {
        error.value = e.message
      }
    }
    async function unshare() {
      await api.unshare(id).catch(() => {})
      session.value = { ...(session.value as SessionOut), shareToken: null }
      shareOpen.value = false
    }
    async function copy() {
      try {
        await navigator.clipboard.writeText(shareUrl.value)
      } catch {
        window.prompt('复制下面的链接：', shareUrl.value)
      }
      copied.value = true
      setTimeout(() => (copied.value = false), 1500)
    }

    const selectAll = (e: FocusEvent) => (e.target as HTMLInputElement).select()
    const again = () => (againOpen.value = true)
    async function sameSet() {
      busy.value = true
      try {
        const r = await api.repeat(id)
        router.push(`/practice/${r.id}`)
      } catch (e: any) {
        error.value = e.message
      } finally {
        busy.value = false
      }
    }
    async function newSet() {
      const c = content.value
      busy.value = true
      waited.value = 0
      try {
        const r = await api.generate({ language: c.language, level: c.level, mode: c.mode, topic: c.topic, count: store.prefs.count, focus: '' },
          (s) => (waited.value = s))
        router.push(`/practice/${r.id}`)
      } catch (e: any) {
        error.value = e.message
        againOpen.value = false
      } finally {
        busy.value = false
      }
    }

    return { router, session, error, coach, content, report, env, shareOpen, shareUrl, copied, againOpen, busy, waited, share, unshare, copy, again, sameSet, newSet, selectAll }
  },
})
</script>
