<template>
  <div :class="['seg', size && `seg--${size}`, { 'seg--block': block }]" role="radiogroup" :aria-label="label">
    <button v-for="o in options" :key="String(o.value)" type="button" role="radio" :aria-checked="o.value === modelValue"
      :class="{ on: o.value === modelValue }" :title="o.title" :disabled="o.disabled" @click="$emit('update:modelValue', o.value)">
      {{ o.label }}<small v-if="o.badge" class="seg__badge">{{ o.badge }}</small>
    </button>
  </div>
</template>

<script lang="ts">
import { defineComponent, type PropType } from 'vue'

export interface SegOption { value: string | number; label: string; title?: string; badge?: string | number; disabled?: boolean }

/** Segmented control: the active segment is filled blue. */
export default defineComponent({
  name: 'SegControl',
  props: {
    options: { type: Array as PropType<SegOption[]>, required: true },
    modelValue: { type: [String, Number], default: '' },
    size: { type: String, default: '' }, // '' | sm
    block: { type: Boolean, default: false },
    label: { type: String, default: '' },
  },
  emits: ['update:modelValue'],
})
</script>
