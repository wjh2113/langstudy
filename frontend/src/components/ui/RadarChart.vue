<template>
  <svg class="radar" :viewBox="`0 0 ${size} ${size}`" role="img" :aria-label="ariaLabel">
    <polygon v-for="f in [0.25, 0.5, 0.75, 1]" :key="f" :points="ring(f)" class="radar__grid" />
    <line v-for="(d, i) in dims" :key="'a' + d.key" :x1="c" :y1="c" :x2="pt(i, R)[0]" :y2="pt(i, R)[1]" class="radar__axis" />
    <polygon :points="shape" class="radar__shape" />
    <template v-for="(d, i) in dims" :key="'d' + d.key">
      <circle v-if="d.score != null" :cx="pt(i, (R * d.score) / 100)[0]" :cy="pt(i, (R * d.score) / 100)[1]" r="3.5" class="radar__dot" />
    </template>
    <text v-for="(d, i) in dims" :key="'l' + d.key" :x="pt(i, R + 20)[0]" :y="pt(i, R + 20)[1]" :text-anchor="anchor(i)"
      dominant-baseline="middle" class="radar__label">{{ d.name }}</text>
  </svg>
</template>

<script lang="ts">
import { computed, defineComponent, type PropType } from 'vue'
import type { Dimension } from '../../api/models'

export default defineComponent({
  name: 'RadarChart',
  props: { dims: { type: Array as PropType<Dimension[]>, required: true } },
  setup(props) {
    const size = 300
    const c = size / 2
    const R = 92
    const pt = (i: number, r: number) => {
      const a = (Math.PI * 2 * i) / props.dims.length - Math.PI / 2
      return [c + Math.cos(a) * r, c + Math.sin(a) * r]
    }
    const ring = (f: number) => props.dims.map((_, i) => pt(i, R * f).join(',')).join(' ')
    const shape = computed(() => props.dims.map((d, i) => pt(i, R * ((d.score ?? 0) / 100)).join(',')).join(' '))
    const anchor = (i: number) => {
      const x = pt(i, R + 20)[0]
      return Math.abs(x - c) < 4 ? 'middle' : x > c ? 'start' : 'end'
    }
    const ariaLabel = computed(() => props.dims.map((d) => `${d.name} ${d.score ?? '未评估'}`).join('，'))
    return { size, c, R, pt, ring, shape, anchor, ariaLabel }
  },
})
</script>
