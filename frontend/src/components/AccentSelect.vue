<template>
  <select v-if="accents.length > 1" class="accent-select" :value="modelValue" aria-label="听力口音"
    @change="$emit('update:modelValue', $event.target.value)">
    <template v-for="g in groups" :key="g.name">
      <template v-if="!g.name">
        <option v-for="a in g.items" :key="a.key" :value="a.key">{{ a.label }}</option>
      </template>
      <optgroup v-else :label="g.name">
        <option v-for="a in g.items" :key="a.key" :value="a.key">{{ a.label }}{{ a.simulated ? '（模拟）' : '' }}</option>
      </optgroup>
    </template>
  </select>
</template>

<script>
import { computed } from 'vue'

/** Accent picker grouped by region (美洲 / 欧洲 / 亚洲 / 大洋洲). */
export default {
  name: 'AccentSelect',
  props: {
    accents: { type: Array, default: () => [] },
    modelValue: { type: String, default: 'default' },
  },
  emits: ['update:modelValue'],
  setup(props) {
    const groups = computed(() => {
      const out = []
      for (const a of props.accents) {
        let g = out.find((x) => x.name === a.group)
        if (!g) out.push((g = { name: a.group, items: [] }))
        g.items.push(a)
      }
      return out
    })
    return { groups }
  },
}
</script>
