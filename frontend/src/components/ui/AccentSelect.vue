<template>
  <label v-if="accents.length > 1" class="select">
    <AppIcon v-if="icon" :name="icon" :size="16" />
    <select :value="modelValue" aria-label="听力口音" @change="onChange">
      <template v-for="g in groups" :key="g.name">
        <template v-if="!g.name">
          <option v-for="a in g.items" :key="a.key" :value="a.key">{{ a.label }}</option>
        </template>
        <optgroup v-else :label="g.name">
          <option v-for="a in g.items" :key="a.key" :value="a.key">{{ g.name }} · {{ a.label }}{{ a.simulated ? '（模拟）' : '' }}</option>
        </optgroup>
      </template>
    </select>
    <AppIcon name="chevron-down" :size="16" class="select__chev" />
  </label>
</template>

<script lang="ts">
import { computed, defineComponent, type PropType } from 'vue'
import AppIcon from './AppIcon.vue'
import type { Accent } from '../../api/models'

export function groupAccents(accents: Accent[]) {
  const out: { name: string; items: Accent[] }[] = []
  for (const a of accents) {
    let g = out.find((x) => x.name === a.group)
    if (!g) out.push((g = { name: a.group, items: [] }))
    g.items.push(a)
  }
  return out
}

/** Accent dropdown grouped by region (美洲 / 欧洲 / 亚洲 / 大洋洲). */
export default defineComponent({
  name: 'AccentSelect',
  components: { AppIcon },
  props: {
    accents: { type: Array as PropType<Accent[]>, default: () => [] },
    modelValue: { type: String, default: 'default' },
    icon: { type: String, default: '' },
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    const onChange = (e: Event) => emit('update:modelValue', (e.target as HTMLSelectElement).value)
    return { groups: computed(() => groupAccents(props.accents)), onChange }
  },
})
</script>
