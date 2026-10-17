<template>
  <div class="auth">
    <section class="auth__brand">
      <div class="auth__logo"><AppIcon name="logo" :size="64" /><span>LangStudy</span></div>
      <p class="auth__tagline">安静练习，从容开口</p>
      <svg class="auth__waves" viewBox="0 0 600 200" preserveAspectRatio="none" aria-hidden="true">
        <path d="M0 60C120 0 200 40 300 110s220 80 300 10" />
        <path d="M0 100C140 40 220 60 320 130s200 50 280-10" />
        <path d="M0 140C150 80 240 90 340 150s180 30 260-20" />
      </svg>
    </section>

    <section class="auth__card">
      <nav v-if="mode !== 'setup'" class="tabs" role="tablist">
        <button type="button" role="tab" :aria-selected="mode === 'login'" :class="{ on: mode === 'login' }" @click="switchTo('login')">登录</button>
        <button type="button" role="tab" :aria-selected="mode === 'register'" :class="{ on: mode === 'register' }" @click="switchTo('register')">用邀请码注册</button>
      </nav>
      <nav v-else class="tabs" role="tablist"><button type="button" role="tab" aria-selected="true" class="on">首次启动 · 创建管理员账号</button></nav>

      <form class="auth__form" @submit.prevent="submit">
        <h1>{{ heading }}</h1>
        <p v-if="mode === 'setup'" class="muted">数据库里还没有用户。你创建的账号就是管理员，可以生成邀请码让别人注册。</p>

        <label v-if="mode === 'register'" class="field">
          <span class="field__label">邀请码</span>
          <span class="input"><AppIcon name="ticket" :size="18" />
            <input v-model="code" autocomplete="off" placeholder="请输入邀请码，例如 ABCD-2345" maxlength="12" @blur="checkCode" />
          </span>
          <small v-if="codeMessage" :class="codeOk ? 'ok' : 'error'">{{ codeMessage }}</small>
        </label>
        <label class="field">
          <span class="field__label">{{ mode === 'setup' ? '管理员用户名' : '用户名' }}</span>
          <span class="input"><AppIcon name="user" :size="18" />
            <input v-model="username" autocomplete="username" maxlength="32" placeholder="请输入用户名" />
          </span>
        </label>
        <label class="field">
          <span class="field__label">密码</span>
          <span class="input"><AppIcon name="lock" :size="18" />
            <input v-model="password" :type="showPw ? 'text' : 'password'" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
              :placeholder="mode === 'login' ? '请输入密码' : '至少 8 位'" />
            <button type="button" class="input__btn" :aria-label="showPw ? '隐藏密码' : '显示密码'" @click="showPw = !showPw">
              <AppIcon :name="showPw ? 'eye-off' : 'eye'" :size="18" />
            </button>
          </span>
        </label>
        <label v-if="mode !== 'login'" class="field">
          <span class="field__label">确认密码</span>
          <span class="input"><AppIcon name="lock" :size="18" />
            <input v-model="password2" :type="showPw ? 'text' : 'password'" autocomplete="new-password" placeholder="请再次输入密码" />
          </span>
        </label>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button :class="['btn', 'btn--block', 'btn--lg', mode === 'login' ? 'btn--dark' : 'btn--primary']" :disabled="busy">
          {{ busy ? '请稍候…' : submitLabel }}
        </button>
        <p v-if="mode === 'login'" class="hint">没有账号？向管理员要一个邀请码。忘记密码也请联系管理员重置。</p>
      </form>
    </section>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, ref } from 'vue'
import AppIcon from '../components/ui/AppIcon.vue'
import { api } from '../api'

export default defineComponent({
  name: 'AuthView',
  components: { AppIcon },
  props: {
    initialMode: { type: String, default: 'login' }, // setup | login | register
    initialCode: { type: String, default: '' },
  },
  emits: ['done'],
  setup(props, { emit }) {
    const mode = ref(props.initialMode)
    const username = ref('')
    const password = ref('')
    const password2 = ref('')
    const showPw = ref(false)
    const code = ref(props.initialCode)
    const codeMessage = ref('')
    const codeOk = ref(false)
    const error = ref('')
    const busy = ref(false)
    const submitLabel = computed(() => ({ setup: '创建管理员账号', login: '登录', register: '注册' } as Record<string, string>)[mode.value])
    const heading = computed(() => ({ setup: '创建管理员账号', login: '登录', register: '用邀请码注册' } as Record<string, string>)[mode.value])

    function switchTo(m: string) {
      mode.value = m
      error.value = ''
    }

    async function checkCode() {
      if (!code.value.trim()) return (codeMessage.value = '')
      try {
        const r = await api.checkInvite(code.value.trim())
        codeOk.value = r.valid
        codeMessage.value = r.valid ? '邀请码有效' : r.message
      } catch (e: any) {
        codeOk.value = false
        codeMessage.value = e.status === 429 ? e.message : ''
      }
    }
    if (props.initialCode) checkCode()

    async function submit() {
      error.value = ''
      if (!username.value.trim() || !password.value) return (error.value = '请填写用户名和密码')
      if (mode.value !== 'login' && password.value !== password2.value) return (error.value = '两次输入的密码不一样')
      busy.value = true
      try {
        const body = { username: username.value.trim(), password: password.value }
        const r = mode.value === 'setup' ? await api.setup(body)
          : mode.value === 'register' ? await api.register({ ...body, inviteCode: code.value.trim() })
            : await api.login(body)
        emit('done', r.user)
      } catch (e: any) {
        error.value = e.message
      } finally {
        busy.value = false
      }
    }

    return { mode, username, password, password2, showPw, code, codeMessage, codeOk, error, busy, submitLabel, heading, switchTo, checkCode, submit }
  },
})
</script>
