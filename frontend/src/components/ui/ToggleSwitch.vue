<template>
  <button type="button" role="switch" :aria-checked="modelValue" :aria-label="label" :disabled="disabled"
    :class="['toggle', { 'is-on': modelValue }]" @click="$emit('update:modelValue', !modelValue)">
    <span class="toggle__knob" />
  </button>
</template>

<script lang="ts">
import { defineComponent } from 'vue'

/** iOS-style on/off switch. */
export default defineComponent({
  name: 'ToggleSwitch',
  props: {
    modelValue: { type: Boolean, default: false },
    label: { type: String, default: '' },
    disabled: { type: Boolean, default: false },
  },
  emits: ['update:modelValue'],
})
</script>
