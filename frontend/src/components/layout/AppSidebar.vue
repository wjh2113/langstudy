<template>
  <aside class="sidebar" aria-label="主导航">
    <nav>
      <RouterLink v-for="item in items" :key="item.name" :to="item.to"
        :class="['sidebar__item', { on: isActive(item.name) }]">
        <AppIcon :name="item.icon" :size="20" />
        <span>{{ item.label }}</span>
        <span v-if="item.badge === 'due' && dueCount" class="count-badge">{{ dueCount }}</span>
      </RouterLink>
    </nav>
    <div class="sidebar__foot">
      <div class="motto">
        <p>每天进步一点点<br />遇见更好的自己</p>
        <svg viewBox="0 0 160 70" class="motto__art" aria-hidden="true">
          <rect x="18" y="52" width="124" height="5" rx="2" class="art-desk" />
          <rect x="30" y="42" width="40" height="5" rx="1.5" class="art-book" />
          <rect x="34" y="36" width="34" height="6" rx="1.5" class="art-book2" />
          <path d="M104 52l-6-16h20l-6 16z" class="art-pot" />
          <path d="M108 36c-2-10-12-14-16-12 2 6 8 10 16 12zM108 36c2-12 10-18 15-16-1 8-7 13-15 16zM108 36c-1-8 1-16 4-20 3 6 1 14-4 20z" class="art-leaf" />
        </svg>
      </div>
      <p v-if="store.config" class="sidebar__meta">
        {{ store.config.demoMode ? '演示模式' : `模型：${store.config.model}` }}<br />
        语音识别：{{ store.config.sttServer ? '服务端' : recognitionSupported ? '浏览器' : '不可用' }}
      </p>
    </div>
  </aside>
</template>

<script lang="ts">
import { computed, defineComponent } from 'vue'
import { useRoute } from 'vue-router'
import AppIcon from '../ui/AppIcon.vue'
import { NAV } from './nav'
import { isAdmin, store } from '../../store'
import { dueCount } from '../../lib/cards'
import { browserRecognitionSupported } from '../../lib/recorder'

export default defineComponent({
  name: 'AppSidebar',
  components: { AppIcon },
  setup() {
    const route = useRoute()
    const items = computed(() => NAV.filter((n) => !n.admin || isAdmin.value))
    const isActive = (name: string) => route.name === name || (name === 'history' && route.name === 'report') ||
      (name === 'notes' && route.name === 'note')
    return { items, isActive, dueCount, store, recognitionSupported: browserRecognitionSupported }
  },
})
</script>
