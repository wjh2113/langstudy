<template>
  <div class="auth">
    <div class="auth__card">
      <div class="brand">
        <span class="brand__mark" aria-hidden="true">听说</span>
        <span class="brand__name">LangStudy</span>
      </div>

      <template v-if="mode === 'setup'">
        <h1>创建管理员账号</h1>
        <p class="muted">这是第一次启动。你创建的账号是管理员，可以生成邀请码让别人注册。</p>
      </template>
      <template v-else>
        <div class="auth__tabs" role="tablist">
          <button role="tab" :aria-selected="mode === 'login'" :class="{ on: mode === 'login' }" @click="switchTo('login')">登录</button>
          <button role="tab" :aria-selected="mode === 'register'" :class="{ on: mode === 'register' }" @click="switchTo('register')">用邀请码注册</button>
        </div>
      </template>

      <form class="auth__form" @submit.prevent="submit">
        <label v-if="mode === 'register'" class="input">
          <span>邀请码</span>
          <input v-model="code" autocomplete="off" placeholder="例如 ABCD-2345" maxlength="12" @blur="checkCode" />
          <small v-if="codeMessage" :class="codeOk ? 'ok' : 'error'">{{ codeMessage }}</small>
        </label>
        <label class="input">
          <span>用户名</span>
          <input v-model="username" autocomplete="username" maxlength="32" />
        </label>
        <label class="input">
          <span>密码</span>
          <input v-model="password" type="password" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" />
          <small v-if="mode !== 'login'" class="muted">至少 8 位</small>
        </label>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="btn btn--primary btn--block" :disabled="busy">{{ busy ? '请稍候…' : submitLabel }}</button>
      </form>
      <p v-if="mode === 'login'" class="hint">没有账号？向管理员要一个邀请码。忘记密码也请联系管理员重置。</p>
    </div>
  </div>
</template>

<script>
import { computed, ref } from 'vue'
import { api } from '../api'

export default {
  name: 'AuthView',
  props: {
    initialMode: { type: String, default: 'login' }, // setup | login | register
    initialCode: { type: String, default: '' },
  },
  emits: ['done'],
  setup(props, { emit }) {
    const mode = ref(props.initialMode)
    const username = ref('')
    const password = ref('')
    const code = ref(props.initialCode)
    const codeMessage = ref('')
    const codeOk = ref(false)
    const error = ref('')
    const busy = ref(false)
    const submitLabel = computed(() => ({ setup: '创建并进入', login: '登录', register: '注册并登录' })[mode.value])

    function switchTo(m) {
      mode.value = m
      error.value = ''
    }

    async function checkCode() {
      if (!code.value.trim()) return (codeMessage.value = '')
      try {
        const r = await api.checkInvite(code.value.trim())
        codeOk.value = r.valid
        codeMessage.value = r.valid ? '邀请码有效' : r.message
      } catch {
        codeMessage.value = ''
      }
    }
    if (props.initialCode) checkCode()

    async function submit() {
      error.value = ''
      if (!username.value.trim() || !password.value) return (error.value = '请填写用户名和密码')
      busy.value = true
      try {
        const body = { username: username.value.trim(), password: password.value }
        const r = mode.value === 'setup' ? await api.setup(body)
          : mode.value === 'register' ? await api.register({ ...body, inviteCode: code.value.trim() })
            : await api.login(body)
        emit('done', r.user)
      } catch (e) {
        error.value = e.message
      } finally {
        busy.value = false
      }
    }

    return { mode, username, password, code, codeMessage, codeOk, error, busy, submitLabel, switchTo, checkCode, submit }
  },
}
</script>
