<template>
  <div v-if="store.auth === 'loading' && !isPublic" class="boot" />
  <RouterView v-else-if="isPublic" />
  <AuthView v-else-if="store.auth !== 'in'" :key="store.auth" :initial-mode="store.auth" :initial-code="inviteCode"
    @done="onSignedIn" />
  <div v-else :class="['shell', { 'shell--bare': bare, 'shell--home': route.name === 'home' }]">
    <AppHeader :bare="bare" />
    <div class="shell__body">
      <AppSidebar v-if="!bare && route.name !== 'home'" />
      <main class="shell__main">
        <p v-if="store.configError" class="banner banner--error">
          <AppIcon name="alert" /> {{ store.configError }} <button type="button" class="link" @click="loadConfig">重试</button>
        </p>
        <RouterView v-slot="{ Component }">
          <component :is="Component" v-if="Component" />
        </RouterView>
      </main>
    </div>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppHeader from './components/layout/AppHeader.vue'
import AppSidebar from './components/layout/AppSidebar.vue'
import AppIcon from './components/ui/AppIcon.vue'
import AuthView from './views/AuthView.vue'
import type { User } from './api/types.gen'
import { boot, loadConfig, signedIn, store } from './store'

export default defineComponent({
  name: 'App',
  components: { AppHeader, AppIcon, AppSidebar, AuthView },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const inviteCode = new URLSearchParams(location.search).get('invite') || ''
    const isPublic = computed(() => Boolean(route.meta.public))
    const bare = computed(() => Boolean(route.meta.bare))
    onMounted(() => boot(inviteCode))

    function onSignedIn(user: User) {
      signedIn(user)
      if (inviteCode) router.replace({ path: route.path, query: {} })
    }
    return { store, route, isPublic, bare, inviteCode, onSignedIn, loadConfig }
  },
})
</script>
