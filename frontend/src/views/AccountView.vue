<template>
  <div class="page account">
    <header class="page-head"><h1>账号设置</h1></header>
    <section class="card account__who">
      <span class="avatar avatar--lg"><AppIcon name="user" :size="28" /></span>
      <div><strong>{{ me?.username }}</strong><p class="muted">{{ me?.role === 'admin' ? '管理员' : '学习者' }}</p></div>
      <button type="button" class="btn btn--ghost" @click="signOut"><AppIcon name="logout" :size="16" /> 退出登录</button>
    </section>

    <section class="card">
      <h2 class="card__title">外观</h2>
      <SegControl :options="themes" :model-value="store.theme" label="主题" @update:model-value="(v) => setTheme(v)" />
    </section>

    <section class="card">
      <h2 class="card__title">修改密码</h2>
      <form class="stack-form" @submit.prevent="save">
        <label class="field"><span class="field__label">原密码</span>
          <span class="input"><AppIcon name="lock" :size="18" /><input v-model="oldPassword" type="password" autocomplete="current-password" /></span></label>
        <label class="field"><span class="field__label">新密码</span>
          <span class="input"><AppIcon name="lock" :size="18" /><input v-model="newPassword" type="password" autocomplete="new-password" /></span>
          <small class="muted">至少 8 位。修改后需要重新登录。</small></label>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="btn btn--primary" :disabled="busy">修改密码</button>
      </form>
    </section>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppIcon from '../components/ui/AppIcon.vue'
import SegControl from '../components/ui/SegControl.vue'
import { api } from '../api'
import { logout, setTheme, store } from '../store'

export default defineComponent({
  name: 'AccountView',
  components: { AppIcon, SegControl },
  setup() {
    const router = useRouter()
    const oldPassword = ref('')
    const newPassword = ref('')
    const error = ref('')
    const busy = ref(false)

    async function signOut() {
      await logout()
      router.push('/')
    }

    async function save() {
      error.value = ''
      if (newPassword.value.length < 8) return (error.value = '新密码至少 8 位')
      busy.value = true
      try {
        await api.changePassword({ oldPassword: oldPassword.value, newPassword: newPassword.value })
        await signOut()
      } catch (e: any) {
        error.value = e.message
      } finally {
        busy.value = false
      }
    }

    return {
      me: store.user, store, oldPassword, newPassword, error, busy, save, signOut, setTheme,
      themes: [{ value: 'system', label: '跟随系统' }, { value: 'light', label: '浅色' }, { value: 'dark', label: '深色' }],
    }
  },
})
</script>
