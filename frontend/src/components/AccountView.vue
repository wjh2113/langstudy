<template>
  <div class="account">
    <h1>账号</h1>
    <section class="block">
      <p><strong>{{ me.username }}</strong> <span class="muted">· {{ me.role === 'admin' ? '管理员' : '用户' }}</span></p>
      <h2>修改密码</h2>
      <form class="auth__form" @submit.prevent="save">
        <label class="input">
          <span>原密码</span>
          <input v-model="oldPassword" type="password" autocomplete="current-password" />
        </label>
        <label class="input">
          <span>新密码</span>
          <input v-model="newPassword" type="password" autocomplete="new-password" />
          <small class="muted">至少 8 位。修改后需要重新登录。</small>
        </label>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="btn btn--primary" :disabled="busy">修改密码</button>
      </form>
    </section>
    <button class="btn btn--ghost" @click="$emit('logout')">退出登录</button>
  </div>
</template>

<script>
import { ref } from 'vue'
import { api } from '../api'

export default {
  name: 'AccountView',
  props: { me: { type: Object, required: true } },
  emits: ['logout'],
  setup(_, { emit }) {
    const oldPassword = ref('')
    const newPassword = ref('')
    const error = ref('')
    const busy = ref(false)

    async function save() {
      error.value = ''
      if (newPassword.value.length < 8) return (error.value = '新密码至少 8 位')
      busy.value = true
      try {
        await api.changePassword({ oldPassword: oldPassword.value, newPassword: newPassword.value })
        emit('logout')
      } catch (e) {
        error.value = e.message
      } finally {
        busy.value = false
      }
    }

    return { oldPassword, newPassword, error, busy, save }
  },
}
</script>
