<template>
  <Teleport to="body">
    <div v-if="open" :class="['overlay', { 'overlay--drawer': drawer }]" @click.self="$emit('close')">
      <div
        :class="drawer ? 'drawer' : ['modal', { 'modal--wide': wide }]"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
      >
        <header class="modal__head">
          <h2><AppIcon v-if="icon" :name="icon" :size="22" /> {{ title }}</h2>
          <button type="button" class="icon-btn" aria-label="关闭" @click="$emit('close')"><AppIcon name="x" /></button>
        </header>
        <slot />
      </div>
    </div>
  </Teleport>
</template>

<script lang="ts">
import { defineComponent, onBeforeUnmount, watch } from 'vue'
import AppIcon from './AppIcon.vue'

/** Centered dialog, or a right-side drawer (`drawer`). Esc and clicking outside close it. */
export default defineComponent({
  name: 'ModalDialog',
  components: { AppIcon },
  props: {
    open: { type: Boolean, default: false },
    title: { type: String, default: '' },
    icon: { type: String, default: '' },
    drawer: { type: Boolean, default: false },
    wide: { type: Boolean, default: false },
  },
  emits: ['close'],
  setup(props, { emit }) {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') emit('close') }
    watch(() => props.open, (o) => (o ? window.addEventListener('keydown', onKey) : window.removeEventListener('keydown', onKey)))
    onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
  },
})
</script>
