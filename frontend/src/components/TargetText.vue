<template>
  <button v-if="env.hideText && !revealed" :class="['veil', cls]" title="显示原文" @click="$emit('reveal')">
    <span :class="['veil__text', env.textClass]" aria-hidden="true">{{ text }}</span>
    <span class="veil__label"><AppIcon name="eye" /> 显示原文</span>
  </button>
  <p v-else :class="[env.textClass, cls]">{{ text }}</p>
</template>

<script>
import AppIcon from './AppIcon.vue'

/** Target-language text that can be blurred for blind listening. */
export default {
  name: 'TargetText',
  components: { AppIcon },
  props: {
    text: { type: String, required: true },
    env: { type: Object, required: true },
    cls: { type: String, default: '' },
    revealed: { type: Boolean, default: false },
  },
  emits: ['reveal'],
}
</script>
