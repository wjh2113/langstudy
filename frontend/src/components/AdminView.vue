<template>
  <div class="admin">
    <h1>用户与邀请</h1>

    <section class="block">
      <h2>生成邀请码</h2>
      <form class="invite-form" @submit.prevent="create">
        <label class="input input--sm">
          <span>可注册人数</span>
          <select v-model.number="form.maxUses">
            <option v-for="n in [1, 3, 5, 10, 30]" :key="n" :value="n">{{ n }} 人</option>
          </select>
        </label>
        <label class="input input--sm">
          <span>有效期</span>
          <select v-model.number="form.expiresDays">
            <option :value="1">1 天</option>
            <option :value="7">7 天</option>
            <option :value="30">30 天</option>
            <option :value="0">不过期</option>
          </select>
        </label>
        <label class="input input--grow">
          <span>备注（给谁的）</span>
          <input v-model="form.note" maxlength="100" placeholder="例如：同事小王" />
        </label>
        <button class="btn btn--primary" :disabled="busy">生成</button>
      </form>

      <div v-if="fresh" class="fresh">
        <p>邀请码已生成，发给对方即可注册：</p>
        <div class="fresh__row">
          <code class="fresh__code">{{ fresh.code }}</code>
          <button class="btn btn--ghost" @click="copy(fresh.code, 'code')">{{ copied === 'code' ? '已复制' : '复制邀请码' }}</button>
          <button class="btn btn--accent" @click="copy(link(fresh.code), 'link')">{{ copied === 'link' ? '已复制' : '复制注册链接' }}</button>
        </div>
        <p class="muted">{{ link(fresh.code) }}</p>
      </div>
      <p v-if="error" class="error">{{ error }}</p>

      <table v-if="invites.length" class="table">
        <thead><tr><th>邀请码</th><th>备注</th><th>使用</th><th>有效期至</th><th>状态</th><th /></tr></thead>
        <tbody>
          <tr v-for="i in invites" :key="i.code">
            <td><code>{{ i.code }}</code></td>
            <td>{{ i.note || '—' }}</td>
            <td>{{ i.uses }} / {{ i.maxUses }}<span v-if="i.usedBy" class="muted table__title">{{ i.usedBy }}</span></td>
            <td class="nowrap">{{ i.expiresAt ? i.expiresAt.replace('T', ' ').slice(0, 16) : '不过期' }}</td>
            <td><span :class="['pill', statusClass[i.status]]">{{ statusName[i.status] }}</span></td>
            <td class="nowrap">
              <template v-if="i.status === 'active'">
                <button class="link" @click="copy(link(i.code), i.code)">{{ copied === i.code ? '已复制' : '复制链接' }}</button>
                <button class="link link--muted" @click="revoke(i.code)">作废</button>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="block">
      <h2>用户</h2>
      <table class="table">
        <thead><tr><th>用户名</th><th>角色</th><th>邀请人</th><th>练习次数</th><th>最近练习</th><th>状态</th><th /></tr></thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td><strong>{{ u.username }}</strong><span v-if="u.id === me.id" class="muted">（你）</span></td>
            <td>{{ u.role === 'admin' ? '管理员' : '用户' }}</td>
            <td>{{ u.invitedBy || '—' }}</td>
            <td>{{ u.practiceCount }}</td>
            <td class="nowrap">{{ u.lastPracticeAt ? u.lastPracticeAt.replace('T', ' ').slice(5, 16) : '—' }}</td>
            <td><span :class="['pill', u.disabled ? 'low' : 'good']">{{ u.disabled ? '已停用' : '正常' }}</span></td>
            <td class="nowrap">
              <template v-if="u.id !== me.id">
                <button class="link" @click="toggle(u)">{{ u.disabled ? '启用' : '停用' }}</button>
                <button class="link link--muted" @click="reset(u)">重置密码</button>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="resetInfo" class="fresh">
        {{ resetInfo.username }} 的新密码：<code class="fresh__code">{{ resetInfo.password }}</code>
        <span class="muted">只显示这一次，请转告对方登录后在“账号”里修改。</span>
      </p>
    </section>
  </div>
</template>

<script>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api'

export default {
  name: 'AdminView',
  props: { me: { type: Object, required: true } },
  setup() {
    const invites = ref([])
    const users = ref([])
    const form = reactive({ maxUses: 1, expiresDays: 7, note: '' })
    const fresh = ref(null)
    const resetInfo = ref(null)
    const copied = ref('')
    const error = ref('')
    const busy = ref(false)

    const load = async () => {
      try {
        ;[invites.value, users.value] = await Promise.all([api.invites(), api.users()])
      } catch (e) {
        error.value = e.message
      }
    }
    onMounted(load)

    const link = (code) => `${location.origin}/?invite=${code}`

    async function create() {
      busy.value = true
      error.value = ''
      try {
        fresh.value = await api.createInvite({ maxUses: form.maxUses, expiresDays: form.expiresDays || null, note: form.note })
        form.note = ''
        await load()
      } catch (e) {
        error.value = e.message
      } finally {
        busy.value = false
      }
    }

    async function copy(text, key) {
      try {
        await navigator.clipboard.writeText(text)
      } catch {
        window.prompt('复制下面的内容：', text)
      }
      copied.value = key
      setTimeout(() => { if (copied.value === key) copied.value = '' }, 1500)
    }

    async function revoke(code) {
      await api.revokeInvite(code).catch((e) => (error.value = e.message))
      if (fresh.value?.code === code) fresh.value = null
      load()
    }

    async function toggle(u) {
      await api.updateUser(u.id, { disabled: !u.disabled }).catch((e) => (error.value = e.message))
      load()
    }

    async function reset(u) {
      try {
        const r = await api.resetPassword(u.id)
        resetInfo.value = { username: u.username, password: r.password }
      } catch (e) {
        error.value = e.message
      }
    }

    return {
      invites, users, form, fresh, resetInfo, copied, error, busy, link, create, copy, revoke, toggle, reset,
      statusName: { active: '可用', used: '已用完', expired: '已过期', revoked: '已作废' },
      statusClass: { active: 'good', used: 'mid', expired: 'low', revoked: 'low' },
    }
  },
}
</script>
