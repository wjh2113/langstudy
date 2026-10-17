<template>
  <div class="page empty card">
    <AppIcon name="info" :size="32" />
    <p>这个页面不存在。</p>
    <RouterLink to="/" class="btn btn--primary">回到首页</RouterLink>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue'
import AppIcon from '../components/ui/AppIcon.vue'

export default defineComponent({ name: 'NotFound', components: { AppIcon } })
</script>
