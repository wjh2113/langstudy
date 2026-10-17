<template>
  <div class="page admin">
    <header class="page-head">
      <h1>用户与邀请</h1>
    </header>
    <div class="chips">
      <button v-for="t in tabs" :key="t.key" type="button" :class="['chip', { on: tab === t.key }]" @click="tab = t.key">{{ t.label }}</button>
    </div>
    <p v-if="error" class="banner banner--error"><AppIcon name="alert" /> {{ error }}</p>

    <template v-if="tab === 'invites'">
      <section class="card">
        <h2 class="card__title">生成新邀请码</h2>
        <form class="invite-form" @submit.prevent="create">
          <label class="field">
            <span class="field__label">可注册人数</span>
            <span class="input"><input v-model.number="form.maxUses" type="number" min="1" max="100" /></span>
            <small class="muted">1 - 100</small>
          </label>
          <label class="field">
            <span class="field__label">有效期</span>
            <span class="select"><AppIcon name="calendar" :size="16" />
              <select v-model.number="form.expiresDays">
                <option :value="1">1 天</option><option :value="7">7 天</option><option :value="30">30 天</option>
                <option :value="90">90 天</option><option :value="0">不过期</option>
              </select><AppIcon name="chevron-down" :size="16" class="select__chev" /></span>
          </label>
          <label class="field field--grow">
            <span class="field__label">备注</span>
            <span class="input"><input v-model="form.note" maxlength="100" placeholder="例如：同事小王" /></span>
            <small class="muted field__count">{{ form.note.length }}/100</small>
          </label>
          <button class="btn btn--primary invite-form__go" :disabled="busy">生成</button>
        </form>
      </section>

      <section v-if="fresh" class="success-card">
        <span class="success-card__check"><AppIcon name="check" :size="28" :stroke="3" /></span>
        <div class="success-card__text">
          <strong>邀请码生成成功！</strong>
          <p>已生成新的邀请码，分享给对方即可注册使用。</p>
        </div>
        <div class="success-card__code">
          <small class="muted">邀请码</small>
          <code>{{ fresh.code }}</code>
        </div>
        <button type="button" class="btn btn--ghost" @click="copy(fresh.code, 'code')"><AppIcon name="copy" :size="16" /> {{ copied === 'code' ? '已复制' : '复制邀请码' }}</button>
        <button type="button" class="btn btn--outline" @click="copy(link(fresh.code), 'link')"><AppIcon name="link" :size="16" /> {{ copied === 'link' ? '已复制' : '复制注册链接' }}</button>
      </section>

      <section class="card">
        <h2 class="card__title">邀请码列表</h2>
        <div class="table-wrap">
          <table v-if="invites.length" class="table">
            <thead><tr><th>邀请码</th><th>可注册人数</th><th>已注册人数</th><th>有效期</th><th>备注</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="i in invites" :key="i.code">
                <td><code>{{ i.code }}</code></td>
                <td>{{ i.maxUses }}</td>
                <td>{{ i.uses }}<span v-if="i.usedBy" class="muted cell-sub">{{ i.usedBy }}</span></td>
                <td class="nowrap">{{ i.expiresAt ? dateOnly(i.expiresAt) : '不过期' }}</td>
                <td>{{ i.note || '—' }}</td>
                <td><span :class="['status', `status--${STATUS[i.status].cls}`]"><i />{{ STATUS[i.status].name }}</span></td>
                <td class="nowrap">
                  <template v-if="i.status === 'active'">
                    <button type="button" class="btn btn--xs btn--outline" @click="copy(link(i.code), i.code)">{{ copied === i.code ? '已复制' : '复制链接' }}</button>
                    <button type="button" class="btn btn--xs btn--danger-outline" @click="revoke(i.code)">作废</button>
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-else class="muted">还没有邀请码。</p>
        </div>
      </section>
    </template>

    <section v-else-if="tab === 'users'" class="card">
      <h2 class="card__title">用户列表</h2>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>用户</th><th>邀请人</th><th>练习次数</th><th>最近练习</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="u in users" :key="u.id">
              <td><span class="user-cell"><span class="avatar avatar--sm">{{ u.username.slice(0, 1).toUpperCase() }}</span>
                <strong>{{ u.username }}</strong><span class="muted">{{ u.role === 'admin' ? '管理员' : '普通用户' }}{{ u.id === me?.id ? '（你）' : '' }}</span></span></td>
              <td>{{ u.invitedBy || '—' }}</td>
              <td>{{ u.practiceCount }}</td>
              <td class="nowrap">{{ u.lastPracticeAt ? dateTime(u.lastPracticeAt) : '—' }}</td>
              <td><span :class="['status', u.disabled ? 'status--warn' : 'status--ok']"><i />{{ u.disabled ? '已停用' : '正常' }}</span></td>
              <td class="nowrap">
                <template v-if="u.id !== me?.id">
                  <button type="button" class="btn btn--xs btn--outline" @click="toggle(u)">{{ u.disabled ? '启用' : '停用' }}</button>
                  <button type="button" class="btn btn--xs btn--ghost" @click="reset(u)">重置密码</button>
                </template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="resetInfo" class="banner banner--ok">
        {{ resetInfo.username }} 的新密码：<code class="code-big">{{ resetInfo.password }}</code>
        <span class="muted">只显示这一次，请转告对方登录后在“账号设置”里修改。</span>
      </p>
    </section>

    <template v-else-if="tab === 'usage'">
      <section v-if="usage" class="card">
        <div class="card__titlebar">
          <h2 class="card__title"><AppIcon name="bars" /> AI 用量（近 {{ usage.days }} 天）</h2>
          <span class="muted">每人每日上限：{{ usage.dailyLimit ? `${usage.dailyLimit} 次` : '不限' }}（在 backend/.env 设置 AI_DAILY_LIMIT）</span>
        </div>
        <div class="table-wrap">
          <table class="table">
            <thead><tr><th>用户</th><th>今天调用</th><th>今天积分</th><th>{{ usage.days }} 天调用</th><th>Tokens</th><th>积分</th></tr></thead>
            <tbody>
              <tr v-for="u in usage.users" :key="u.id">
                <td><strong>{{ u.username }}</strong></td><td>{{ u.callsToday }}</td><td>{{ fmtCredits(u.creditsToday) }}</td>
                <td>{{ u.calls }}</td><td>{{ u.tokens.toLocaleString() }}</td><td>{{ fmtCredits(u.credits) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <h3 class="sub-title">按用途</h3>
        <div class="usage-tasks">
          <div v-for="t in usage.tasks" :key="t.task" class="usage-task">
            <span>{{ TASKS[t.task.split(':')[0]] || t.task }}{{ t.task.endsWith(':retry') ? '（重试）' : '' }}</span>
            <strong>{{ t.calls }}</strong><small class="muted">次 · {{ t.tokens.toLocaleString() }} tokens{{ t.credits != null ? ` · ${fmtCredits(t.credits)} 积分` : '' }}</small>
          </div>
          <p v-if="!usage.tasks.length" class="muted">还没有 AI 调用记录。</p>
        </div>
        <p class="muted small">积分以网关在响应里返回的计费为准；网关没返回时只统计次数和 tokens。</p>
      </section>
      <section v-if="mistakes" class="card">
        <h2 class="card__title"><AppIcon name="alert" /> 大家最常犯的问题</h2>
        <p class="muted">已批改 {{ mistakes.graded }} 条作答，其中 {{ mistakes.flagged }} 条有问题（{{ mistakes.graded ? Math.round(mistakes.flagged / mistakes.graded * 100) : 0 }}%）。</p>
        <ol class="plain-list">
          <li v-for="(m, k) in mistakes.topNotes" :key="k">{{ m.notes }} <span class="muted">· {{ m.count }} 次 · {{ m.users }} 人</span></li>
        </ol>
      </section>
    </template>

    <template v-else-if="tab === 'import'">
      <section class="card">
        <h2 class="card__title">发给其他模型的说明</h2>
        <p class="muted">把下面整段复制给别的大模型。有课件时，在同一条消息里附上 PPT、PDF、Word，或把讲义文字贴在后面，它会以课件为准。没有课件时，在后面写上话题和目标语言（英语、日语，或两种都要）。交回来的可以是一个 Markdown，也可以是装着多个 Markdown 的压缩包。</p>
        <textarea class="import-prompt" readonly :value="prompt" rows="14" />
        <button type="button" class="btn btn--outline" :disabled="!prompt" @click="copy(prompt, 'prompt')">
          <AppIcon name="copy" :size="16" /> {{ copied === 'prompt' ? '已复制' : '复制说明' }}
        </button>
      </section>
      <section class="card">
        <h2 class="card__title">导入话题</h2>
        <p class="muted">导入后归在你自己的账号下，可以在历史记录里打开练习，学习笔记里已经有单词、语法和句型。</p>
        <label class="btn btn--primary">
          {{ importing ? '正在导入…' : '选择 .md 或 .zip' }}
          <input class="sr-only" type="file" accept=".md,.markdown,.txt,.zip,text/markdown,application/zip" :disabled="importing" @change="onImport" />
        </label>
        <ul v-if="imported.length" class="import-list">
          <li v-for="item in imported" :key="item.id">
            <RouterLink :to="`/practice/${item.id}`">{{ item.topic }}</RouterLink>
            <span class="tag tag--mode">{{ MODE_NAMES[item.mode] || item.mode }}</span>
            <span v-if="item.hasNotes" class="muted">含学习笔记</span>
          </li>
        </ul>
        <p v-for="(msg, i) in importErrors" :key="i" class="banner banner--error"><AppIcon name="alert" /> {{ msg }}</p>
      </section>
    </template>
  </div>
</template>

<script lang="ts">
import { defineComponent, onMounted, reactive, ref, watch } from 'vue'
import AppIcon from '../components/ui/AppIcon.vue'
import { api } from '../api'
import { store } from '../store'
import { dateOnly, dateTime, MODE_NAMES } from '../lib/format'

export default defineComponent({
  name: 'AdminView',
  components: { AppIcon },
  setup() {
    const tab = ref('invites')
    const invites = ref<any[]>([])
    const users = ref<any[]>([])
    const usage = ref<any>(null)
    const mistakes = ref<any>(null)
    const form = reactive({ maxUses: 1, expiresDays: 7, note: '' })
    const fresh = ref<any>(null)
    const resetInfo = ref<{ username: string; password: string } | null>(null)
    const copied = ref('')
    const error = ref('')
    const busy = ref(false)
    const prompt = ref('')
    const importing = ref(false)
    const imported = ref<{ id: string; topic: string; mode: string; title: string; hasNotes: boolean }[]>([])
    const importErrors = ref<string[]>([])

    const load = async () => {
      try {
        ;[invites.value, users.value] = await Promise.all([api.invites(), api.users()])
      } catch (e: any) {
        error.value = e.message
      }
    }
    onMounted(load)
    watch(tab, async (t) => {
      if (t === 'import' && !prompt.value) {
        try { prompt.value = (await api.importPrompt()).prompt } catch (e: any) { error.value = e.message }
      }
      if (t !== 'usage') return
      try {
        ;[usage.value, mistakes.value] = await Promise.all([api.usage(30), api.mistakeStats()])
      } catch (e: any) {
        error.value = e.message
      }
    })

    async function onImport(ev: Event) {
      const input = ev.target as HTMLInputElement
      const file = input.files?.[0]
      input.value = ''
      if (!file) return
      importing.value = true
      error.value = ''
      importErrors.value = []
      try {
        const result = await api.importTopics(file)
        imported.value = result.imported
        importErrors.value = result.errors || []
      } catch (e: any) {
        error.value = e.message
      } finally {
        importing.value = false
      }
    }

    const link = (code: string) => `${location.origin}/?invite=${code}`

    async function create() {
      busy.value = true
      error.value = ''
      try {
        fresh.value = await api.createInvite({ maxUses: Math.max(1, Math.min(100, form.maxUses || 1)), expiresDays: form.expiresDays || null, note: form.note })
        form.note = ''
        await load()
      } catch (e: any) {
        error.value = e.message
      } finally {
        busy.value = false
      }
    }

    async function copy(text: string, key: string) {
      try {
        await navigator.clipboard.writeText(text)
      } catch {
        window.prompt('复制下面的内容：', text)
      }
      copied.value = key
      setTimeout(() => { if (copied.value === key) copied.value = '' }, 1500)
    }

    async function revoke(code: string) {
      await api.revokeInvite(code).catch((e) => (error.value = e.message))
      if (fresh.value?.code === code) fresh.value = null
      load()
    }

    async function toggle(u: any) {
      await api.updateUser(u.id, { disabled: !u.disabled }).catch((e) => (error.value = e.message))
      load()
    }

    async function reset(u: any) {
      try {
        const r = await api.resetPassword(u.id)
        resetInfo.value = { username: u.username, password: r.password }
      } catch (e: any) {
        error.value = e.message
      }
    }

    const fmtCredits = (v: number | null) => (v == null ? '—' : Math.round(v * 100) / 100)

    return {
      me: store.user, tab, invites, users, usage, mistakes, form, fresh, resetInfo, copied, error, busy,
      prompt, importing, imported, importErrors, onImport, MODE_NAMES,
      link, create, copy, revoke, toggle, reset,
      dateOnly, dateTime, fmtCredits,
      tabs: [{ key: 'invites', label: '邀请码' }, { key: 'users', label: '用户' }, { key: 'usage', label: '用量与统计' }, { key: 'import', label: '导入话题' }],
      STATUS: {
        active: { name: '可用', cls: 'ok' }, used: { name: '已用完', cls: 'muted' },
        expired: { name: '已过期', cls: 'warn' }, revoked: { name: '已作废', cls: 'bad' },
      } as Record<string, { name: string; cls: string }>,
      TASKS: { generate: '出题', evaluate: '评分', followup: '追问', chat: '自由对话', notes: '学习笔记', translate: '翻译', tts: '朗读', stt: '语音识别', pronounce: '发音评测' } as Record<string, string>,
    }
  },
})
</script>
