<template>
  <header class="topbar">
    <RouterLink to="/" class="brand" aria-label="LangStudy 首页">
      <AppIcon name="logo" :size="30" />
      <span class="brand__name">LangStudy</span>
    </RouterLink>
    <span class="topbar__sep" aria-hidden="true" />
    <div id="header-center" class="topbar__center">
      <nav v-if="route.name === 'home'" class="lang-crumb" aria-label="学习语言">
        <template v-for="(l, i) in langs" :key="l">
          <span v-if="i" class="lang-crumb__sep" aria-hidden="true">/</span>
          <button type="button" :class="{ on: store.prefs.language === l }" :aria-pressed="store.prefs.language === l"
            @click="setPrefs({ language: l })">{{ LANG_NAMES[l] }}</button>
        </template>
      </nav>
      <span v-else-if="!bare" class="topbar__tagline">语言学习 · 从这里开始</span>
    </div>
    <div class="topbar__right">
      <RouterLink v-if="dueCount" to="/review" class="icon-btn icon-btn--badge" :title="`今天有 ${dueCount} 张卡片该复习了`">
        <AppIcon name="bell" /><span class="dot-badge">{{ dueCount > 99 ? '99+' : dueCount }}</span>
      </RouterLink>
      <button type="button" class="icon-btn" :title="themeTitle" :aria-label="themeTitle" @click="cycleTheme">
        <AppIcon :name="store.theme === 'system' ? 'monitor' : store.theme === 'dark' ? 'moon' : 'sun'" />
      </button>
      <div class="usermenu" @keydown.esc="open = false">
        <button type="button" class="usermenu__btn" :aria-expanded="open" aria-haspopup="menu" @click="open = !open">
          <span class="avatar"><AppIcon name="user" :size="18" /></span>
          <span class="usermenu__name">{{ store.user?.username }}</span>
          <AppIcon name="chevron-down" :size="14" />
        </button>
        <div v-if="open" class="usermenu__pop" role="menu" @click="open = false">
          <p class="usermenu__who"><strong>{{ store.user?.username }}</strong><span class="muted">{{ isAdmin ? '管理员' : '学习者' }}</span></p>
          <template v-for="item in items" :key="item.name">
            <RouterLink :to="item.to" role="menuitem" class="usermenu__item">
              <AppIcon :name="item.icon" :size="16" />{{ item.label }}
              <span v-if="item.badge === 'due' && dueCount" class="count-badge">{{ dueCount }}</span>
            </RouterLink>
          </template>
          <button type="button" role="menuitem" class="usermenu__item" @click="signOut"><AppIcon name="logout" :size="16" />退出登录</button>
        </div>
        <div v-if="open" class="usermenu__scrim" @click="open = false" />
      </div>
    </div>
  </header>
</template>

<script lang="ts">
import { computed, defineComponent, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '../ui/AppIcon.vue'
import { NAV } from './nav'
import { isAdmin, logout, setPrefs, setTheme, store } from '../../store'
import { dueCount } from '../../lib/cards'
import { LANG_NAMES } from '../../lib/format'
import type { Lang } from '../../api/models'

export default defineComponent({
  name: 'AppHeader',
  components: { AppIcon },
  props: { bare: { type: Boolean, default: false } },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const open = ref(false)
    watch(() => route.fullPath, () => (open.value = false))
    const items = computed(() => NAV.filter((n) => !n.admin || isAdmin.value))
    const order = ['system', 'light', 'dark'] as const
    const cycleTheme = () => setTheme(order[(order.indexOf(store.theme) + 1) % order.length])
    const themeTitle = computed(() => ({ system: '主题：跟随系统', light: '主题：浅色', dark: '主题：深色' })[store.theme])
    async function signOut() {
      await logout()
      router.push('/')
    }
    const langs: Lang[] = ['en', 'ja']
    return { route, store, isAdmin, open, items, dueCount, cycleTheme, themeTitle, setPrefs, signOut, LANG_NAMES, langs }
  },
})
</script>
