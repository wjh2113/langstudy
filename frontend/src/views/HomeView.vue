<template>
  <div class="home" :data-lang="prefs.language">
    <h1 class="home__title">今天练什么话题？</h1>

    <div class="home__ask">
      <form class="searchbar" @submit.prevent="submit()">
        <AppIcon name="search" :size="22" class="searchbar__icon" />
        <input v-model="topic" class="searchbar__input" maxlength="200" aria-label="话题"
          :placeholder="prefs.language === 'ja' ? '例如：日企面试、在便利店购物、预约餐厅…' : '例如：面试自我介绍、餐厅点餐、机场问路…'" />
        <button class="btn btn--primary searchbar__btn" :disabled="!topic.trim() || busy">
          {{ busy && !pasting ? '正在生成…' : '生成练习' }}<AppIcon v-if="!(busy && !pasting)" name="arrow-right" :size="18" />
        </button>
      </form>
      <button type="button" class="btn btn--ghost home__upload" :disabled="busy" @click="openUpload">
        <AppIcon name="doc" :size="18" /> 上传资料
      </button>
    </div>
    <div class="chips chips--center">
      <button v-for="s in suggestions[prefs.language] || []" :key="s" type="button" class="chip" @click="topic = s">{{ s }}</button>
    </div>

    <div v-if="busy" class="progress-card" role="status">
      <div class="progress-card__row">
        <span class="spinner" aria-hidden="true" />
        <strong>{{ pasting ? '正在整理课程包…' : '正在生成练习内容…' }}</strong>
        <span class="muted">{{ waited }} 秒</span>
      </div>
      <div class="bar"><span :style="{ width: `${Math.min(95, waited * 4)}%` }" /></div>
      <p class="muted">{{ pasting && isTopicImport ? '正在导入话题…' : uploadOpen || pasting ? '正在本地提取文字，并整理成课程包…' : '一般需要 10–30 秒，生成好会自动进入练习。' }}</p>
    </div>
    <p v-if="error" class="banner banner--error"><AppIcon name="alert" /> {{ error }}</p>

    <section v-if="unfinished.length" class="resume">
      <h2 class="section-title"><AppIcon name="history" /> 继续上次的练习</h2>
      <div class="resume__list">
        <RouterLink v-for="s in unfinished" :key="s.id" :to="`/practice/${s.id}`" class="resume__item">
          <span :class="['tag', `tag--${s.language}`]">{{ LANG_NAMES[s.language || 'en'] }}</span>
          <span class="tag tag--mode">{{ MODE_NAMES[s.mode] }}</span>
          <strong>{{ s.topic }}</strong>
          <span class="muted">已答 {{ s.answered }} 条 · {{ dateTime(s.updatedAt || s.createdAt) }}</span>
          <AppIcon name="chevron-right" :size="16" />
        </RouterLink>
      </div>
    </section>

    <section v-if="coach && (coach.level || coach.weakest)" class="coach">
      <div v-if="coach.level" class="coach__row">
        <AppIcon name="bars" class="coach__icon" />
        <p><strong>难度建议</strong>{{ coach.reason }}</p>
        <button v-if="coach.change && prefs.level !== coach.level" type="button" class="btn btn--sm btn--ghost"
          @click="setPrefs({ level: coach.level })">改为{{ LEVEL_NAMES[coach.level] }}</button>
        <span v-else-if="coach.change && autoApplied" class="tag tag--ok">已自动调整</span>
      </div>
      <div v-if="coach.weakest" class="coach__row">
        <AppIcon name="trend" class="coach__icon" />
        <p><strong>薄弱项</strong>最近「{{ coach.weakest.name }}」平均 {{ coach.weakest.score }} 分，是你最弱的一项。</p>
        <button type="button" class="btn btn--sm btn--primary" :disabled="busy" @click="drill">专项练一组</button>
      </div>
      <label class="coach__auto">
        <ToggleSwitch :model-value="prefs.autoLevel" label="按最近成绩自动调节难度" @update:model-value="(v) => setPrefs({ autoLevel: v })" />
        <span>按最近成绩自动调节难度</span>
      </label>
    </section>

    <section class="options card">
      <div class="options__row options__row--top">
        <div class="opt opt--lang">
          <OptHead icon="globe" title="学习语言" sub="选择你想练习的语言" />
          <div class="lang-cards">
            <button v-for="l in languages" :key="l.code" type="button" :class="['lang-card', `lang-card--${l.code}`, { on: prefs.language === l.code }]"
              :aria-pressed="prefs.language === l.code" @click="setPrefs({ language: l.code })">
              <FlagIcon :lang="l.code" :size="34" />
              <span class="lang-card__text"><strong>{{ LANG_NAMES[l.code] }}</strong><small>{{ l.name }}</small></span>
              <span v-if="prefs.language === l.code" class="lang-card__check"><AppIcon name="check" :size="14" :stroke="3" /></span>
            </button>
          </div>
        </div>
        <div class="opt opt--level">
          <OptHead icon="bars" title="难度等级" sub="从简单到具有挑战性的内容" />
          <SegControl block :options="levelOptions" :model-value="prefs.level" label="难度"
            @update:model-value="(v) => setPrefs({ level: v })" />
        </div>
        <div class="opt opt--count">
          <OptHead icon="list" title="题目数量" :sub="countHint" />
          <SegControl v-if="hasCount" block :options="[3, 5, 8].map((n) => ({ value: n, label: String(n) }))"
            :model-value="prefs.count" label="题目数量" @update:model-value="(v) => setPrefs({ count: v })" />
          <p v-else class="muted opt__note">{{ prefs.mode === 'chat' ? '自由对话不限轮数，聊到自然结束为止。' : '长度按难度自动决定。' }}</p>
        </div>
      </div>

      <div class="options__row options__row--bottom">
        <div v-if="regions.length > 1" class="opt opt--accent">
          <OptHead icon="headphones" title="听力口音" :sub="`选择你想要的${prefs.language === 'ja' ? '日语' : '英语'}口音`" />
          <div class="tile-grid tile-grid--accent">
            <button v-for="r in regions" :key="r.name" type="button" :class="['tile', { on: r.name === currentRegion }]"
              :aria-pressed="r.name === currentRegion" @click="pickRegion(r)">
              <RegionIcon :region="r.name" />
              <strong>{{ r.name || '标准' }}</strong>
              <small>（{{ r.name === currentRegion ? currentAccent?.label : r.items[0].label }}）</small>
            </button>
          </div>
          <AccentSelect v-if="regionAccents.length > 1" class="opt__sub" :accents="regionAccents" :model-value="accentKey"
            @update:model-value="(k) => setAccent(prefs.language, k)" />
        </div>
        <div class="opt opt--mode">
          <OptHead icon="chat-dots" title="练习形式" sub="选择你想要的练习方式" />
          <div class="tile-grid tile-grid--mode">
            <button v-for="m in modes" :key="m.key" type="button" :class="['tile', { on: prefs.mode === m.key }]"
              :aria-pressed="prefs.mode === m.key" @click="setPrefs({ mode: m.key })">
              <span class="tile__icon"><AppIcon :name="m.icon" :size="20" /></span>
              <strong>{{ m.name }}</strong>
              <small>{{ m.desc }}</small>
            </button>
          </div>
        </div>
      </div>
    </section>

    <p v-if="store.config && store.config.demoMode" class="banner banner--info">
      <AppIcon name="info" /> 现在是演示模式：还没有配置网关或大模型，会使用内置示例内容。
    </p>

    <ModalDialog :open="uploadOpen" title="上传资料" icon="doc" @close="closeUpload">
      <p class="muted">支持 PDF、PPTX、Word，也可以直接粘贴文字。文字在本地提取，只调用一次模型做归类，原文不会被改写。</p>
      <template v-if="isAdmin">
        <p class="muted">管理员还可以上传别的模型写好的 <code>.md</code> 或 <code>.zip</code>，导入后直接进练习历史和学习笔记。</p>
        <details class="upload-prompt" :open="!!prompt">
          <summary>发给其他模型的说明</summary>
          <textarea class="import-prompt" readonly :value="prompt" rows="10" />
          <button type="button" class="btn btn--outline btn--sm" :disabled="!prompt" @click="copyPrompt">
            <AppIcon name="copy" :size="14" /> {{ copiedPrompt ? '已复制' : '复制说明' }}
          </button>
        </details>
      </template>
      <label class="upload-pick">
        <input type="file" :accept="uploadAccept" :disabled="busy" @change="onFile" />
        <span>{{ file ? file.name : (isAdmin ? '选择 PDF、PPTX、DOCX、.md 或 .zip' : '选择 PDF、PPTX 或 DOCX') }}</span>
      </label>
      <textarea v-if="!isTopicImport" v-model="paste" class="upload-text" rows="8" maxlength="40000" placeholder="或者把课件文字粘贴在这里" />
      <p v-if="isTopicImport" class="muted">已选 Markdown / 压缩包，点下面会按导入话题处理。</p>
      <ul v-if="imported.length" class="import-list">
        <li v-for="item in imported" :key="item.id">
          <RouterLink :to="`/practice/${item.id}`" @click="closeUpload">{{ item.topic }}</RouterLink>
          <span class="tag tag--mode">{{ MODE_NAMES[item.mode] || item.mode }}</span>
          <span v-if="item.hasNotes" class="muted">含学习笔记</span>
        </li>
      </ul>
      <p v-for="(msg, i) in importErrors" :key="'ie'+i" class="banner banner--error"><AppIcon name="alert" /> {{ msg }}</p>
      <div class="modal__actions">
        <button type="button" class="btn btn--ghost" @click="closeUpload">{{ imported.length ? '关闭' : '取消' }}</button>
        <button type="button" class="btn btn--primary" :disabled="busy || (!file && !paste.trim())" @click="upload">
          {{ isTopicImport ? (busy ? '正在导入…' : '导入话题') : '整理成课程包' }}
        </button>
      </div>
    </ModalDialog>

    <ModalDialog :open="!!reuse" title="这个话题练过了" icon="history" @close="reuse = null">
      <p v-if="reuse">上次练习「{{ reuse.title }}」是在 {{ dateTime(reuse.createdAt) }}<template v-if="reuse.done">，得了 {{ reuse.overall ?? '—' }} 分</template>。</p>
      <p class="muted">用上次的题不会再调用 AI 生成，马上就能开始，学习笔记也会一起带过来。</p>
      <div class="modal__actions">
        <button type="button" class="btn btn--ghost" @click="startNew">换一套新题</button>
        <button type="button" class="btn btn--primary" @click="useLast">用上次的题</button>
      </div>
    </ModalDialog>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, h, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import AppIcon from '../components/ui/AppIcon.vue'
import AccentSelect, { groupAccents } from '../components/ui/AccentSelect.vue'
import FlagIcon from '../components/ui/FlagIcon.vue'
import ModalDialog from '../components/ui/ModalDialog.vue'
import RegionIcon from '../components/ui/RegionIcon.vue'
import SegControl from '../components/ui/SegControl.vue'
import ToggleSwitch from '../components/ui/ToggleSwitch.vue'
import { api, type SessionSummary } from '../api'
import type { Accent, Coach, Level, Mode } from '../api/models'
import type { PreviousSession } from '../api/types.gen'
import { isAdmin, setAccent, setPrefs, store } from '../store'
import { LANG_NAMES, LEVEL_NAMES, MODE_NAMES, dateTime } from '../lib/format'

const OptHead = (props: { icon: string; title: string; sub: string }) => h('div', { class: 'opt__head' }, [
  h(AppIcon, { name: props.icon, size: 22 }),
  h('div', [h('h3', props.title), h('p', props.sub)]),
])
OptHead.props = ['icon', 'title', 'sub']

const MODES: { key: Mode; name: string; desc: string; icon: string }[] = [
  { key: 'questions', name: '话题问答', desc: '围绕话题进行问答', icon: 'chats' },
  { key: 'dialogue', name: '情景对话', desc: '模拟真实场景对话', icon: 'chat' },
  { key: 'article', name: '短文', desc: '跟读并回答问题', icon: 'doc' },
  { key: 'chat', name: '自由对话', desc: 'AI 陪你一直聊', icon: 'chat-dots' },
  { key: 'dictation', name: '精听填空', desc: '听录音把词填上', icon: 'pen' },
]

const SUGGESTIONS: Record<string, string[]> = {
  en: ['面试自我介绍', '餐厅点餐', '问路', '日常寒暄', '商务会议'],
  ja: ['日企面试', '在便利店购物', '自我介绍', '预约餐厅', '聊聊周末计划'],
}

export default defineComponent({
  name: 'HomeView',
  components: { AccentSelect, AppIcon, FlagIcon, ModalDialog, OptHead, RegionIcon, SegControl, ToggleSwitch },
  setup() {
    const router = useRouter()
    const prefs = store.prefs
    const topic = ref(prefs.topic || '')
    const busy = ref(false)
    const waited = ref(0)
    const error = ref('')
    const reuse = ref<PreviousSession | null>(null)
    const uploadOpen = ref(false)
    const file = ref<File | null>(null)
    const paste = ref('')
    const pasting = ref(false)
    const prompt = ref('')
    const copiedPrompt = ref(false)
    const imported = ref<{ id: string; topic: string; mode: string; title: string; hasNotes: boolean }[]>([])
    const importErrors = ref<string[]>([])
    let pending: Record<string, any> | null = null

    const isTopicImport = computed(() => !!file.value && /\.(md|markdown|txt|zip)$/i.test(file.value.name))
    const uploadAccept = computed(() => isAdmin.value
      ? '.pdf,.pptx,.docx,.md,.markdown,.txt,.zip,application/pdf,text/markdown,application/zip'
      : '.pdf,.pptx,.docx,application/pdf')

    const languages = computed(() => store.config?.languages || [])
    const meta = computed(() => languages.value.find((l) => l.code === prefs.language))
    const levelOptions = computed(() => (meta.value?.levels || []).map((l) => ({ value: l.key, label: LEVEL_NAMES[l.key], title: l.label })))
    const accents = computed<Accent[]>(() => meta.value?.accents || [])
    const regions = computed(() => groupAccents(accents.value))
    const accentKey = computed(() => store.display.accents[prefs.language] || 'default')
    const currentAccent = computed(() => accents.value.find((a) => a.key === accentKey.value) || accents.value[0])
    const currentRegion = computed(() => currentAccent.value?.group ?? '')
    const regionAccents = computed(() => regions.value.find((r) => r.name === currentRegion.value)?.items || [])
    const pickRegion = (r: { name: string; items: Accent[] }) => {
      if (r.name !== currentRegion.value) setAccent(prefs.language, r.items[0].key)
    }
    const hasCount = computed(() => prefs.mode === 'questions' || prefs.mode === 'article')
    const countHint = computed(() => (prefs.mode === 'article' ? '短文后的理解题数量' : hasCount.value ? '每次练习包含的题目数量' : '这个形式不需要设置'))

    // coaching: suggested difficulty + weakest skill for the selected language
    const coach = ref<Coach | null>(null)
    const autoApplied = ref(false)
    watch(() => prefs.language, async (lang) => {
      coach.value = null
      try {
        const c = await api.coach(lang)
        if (lang !== prefs.language) return
        coach.value = c
        if (prefs.autoLevel && c.level && c.change && prefs.level !== c.level) {
          setPrefs({ level: c.level as Level })
          autoApplied.value = true
        }
      } catch { /* coaching is optional */ }
    }, { immediate: true })

    // unfinished practices (progress is saved as you go): offer to continue them
    const unfinished = ref<SessionSummary[]>([])
    onMounted(async () => {
      try {
        const all = await api.sessions()
        const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString()
        unfinished.value = all.filter((s) => !s.done && s.answered > 0 && (s.updatedAt || s.createdAt) > weekAgo).slice(0, 3)
      } catch { /* optional */ }
    })

    async function generate(body: Record<string, any>) {
      busy.value = true
      waited.value = 0
      error.value = ''
      try {
        const res = await api.generate(body as any, (s) => (waited.value = s))
        router.push(`/practice/${res.id}`)
      } catch (e: any) {
        error.value = e.message
      } finally {
        busy.value = false
      }
    }

    async function submit() {
      const t = topic.value.trim()
      if (!t || busy.value) return
      setPrefs({ topic: t })
      const body = { language: prefs.language, level: prefs.level, mode: prefs.mode, topic: t, count: prefs.count, focus: '' }
      try {
        const { previous } = await api.previous({ language: body.language, level: body.level, mode: body.mode, topic: t })
        if (previous) {
          pending = body
          reuse.value = previous
          return
        }
      } catch { /* just generate */ }
      generate(body)
    }

    function startNew() {
      reuse.value = null
      if (pending) generate(pending)
    }
    async function useLast() {
      const prev = reuse.value
      reuse.value = null
      if (!prev) return
      try {
        const r = await api.repeat(prev.id)
        router.push(`/practice/${r.id}`)
      } catch (e: any) {
        error.value = e.message
      }
    }

    const drill = () => coach.value?.weakest &&
      generate({ language: prefs.language, level: prefs.level, mode: '', topic: '', count: prefs.count, focus: coach.value.weakest.key })

    function onFile(e: Event) {
      const input = e.target as HTMLInputElement
      file.value = input.files?.[0] || null
      imported.value = []
      importErrors.value = []
    }

    function closeUpload() {
      uploadOpen.value = false
      file.value = null
      paste.value = ''
      imported.value = []
      importErrors.value = []
    }

    async function openUpload() {
      uploadOpen.value = true
      imported.value = []
      importErrors.value = []
      if (isAdmin.value && !prompt.value) {
        try { prompt.value = (await api.importPrompt()).prompt } catch (e: any) { error.value = e.message }
      }
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

    async function upload() {
      if (busy.value || (!file.value && !paste.value.trim())) return
      error.value = ''
      importErrors.value = []
      if (isTopicImport.value) {
        if (!isAdmin.value) {
          error.value = '只有管理员可以导入 Markdown 话题'
          return
        }
        pasting.value = true
        busy.value = true
        waited.value = 0
        try {
          const result = await api.importTopics(file.value!)
          imported.value = result.imported
          importErrors.value = result.errors || []
          if (result.imported.length === 1 && !result.errors?.length) {
            closeUpload()
            router.push(`/practice/${result.imported[0].id}`)
          }
        } catch (e: any) {
          error.value = e.message
        } finally {
          busy.value = false
          pasting.value = false
        }
        return
      }
      const form = new FormData()
      form.set('language', prefs.language)
      form.set('level', prefs.level)
      if (file.value) form.set('file', file.value)
      if (paste.value.trim()) form.set('text', paste.value.trim())
      pasting.value = true
      uploadOpen.value = false
      busy.value = true
      waited.value = 0
      try {
        const res = await api.courseUpload(form, (s) => (waited.value = s))
        router.push(`/course/${res.id}`)
      } catch (e: any) {
        error.value = e.message
        uploadOpen.value = true
      } finally {
        busy.value = false
        pasting.value = false
      }
    }

    return {
      store, prefs, topic, busy, waited, error, reuse, uploadOpen, file, paste, pasting, onFile, upload,
      closeUpload, openUpload, isAdmin, isTopicImport, uploadAccept, prompt, copiedPrompt, copyPrompt,
      imported, importErrors,
      languages, levelOptions, regions, accentKey, currentAccent, currentRegion,
      regionAccents, pickRegion, hasCount, countHint, coach, autoApplied, unfinished, submit, startNew, useLast, drill,
      setPrefs, setAccent, modes: MODES, suggestions: SUGGESTIONS, LANG_NAMES, LEVEL_NAMES, MODE_NAMES, dateTime,
    }
  },
})
</script>
