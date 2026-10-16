<template>
  <svg class="radar" :viewBox="`0 0 ${size} ${size}`" role="img" :aria-label="ariaLabel">
    <polygon v-for="f in [0.25, 0.5, 0.75, 1]" :key="f" :points="ring(f)" class="radar__grid" />
    <line v-for="(d, i) in dims" :key="'a' + d.key" :x1="c" :y1="c" :x2="pt(i, R)[0]" :y2="pt(i, R)[1]" class="radar__axis" />
    <polygon :points="shape" class="radar__shape" />
    <template v-for="(d, i) in dims" :key="'d' + d.key">
      <circle v-if="d.score != null" :cx="pt(i, (R * d.score) / 100)[0]" :cy="pt(i, (R * d.score) / 100)[1]" r="3.5" class="radar__dot" />
    </template>
    <text v-for="(d, i) in dims" :key="'l' + d.key" :x="pt(i, R + 26)[0]" :y="pt(i, R + 26)[1]" :text-anchor="anchor(i)"
      dominant-baseline="middle" class="radar__label">
      <tspan>{{ d.name }}</tspan>
      <tspan class="radar__score" :x="pt(i, R + 26)[0]" dy="1.25em">{{ d.score ?? '—' }}</tspan>
    </text>
  </svg>
</template>

<script>
import { computed } from 'vue'

export default {
  name: 'RadarChart',
  props: { dims: { type: Array, required: true } },
  setup(props) {
    const size = 300
    const c = size / 2
    const R = 104
    const pt = (i, r) => {
      const a = (Math.PI * 2 * i) / props.dims.length - Math.PI / 2
      return [c + Math.cos(a) * r, c + Math.sin(a) * r]
    }
    const ring = (f) => props.dims.map((_, i) => pt(i, R * f).join(',')).join(' ')
    const shape = computed(() => props.dims.map((d, i) => pt(i, R * ((d.score ?? 0) / 100)).join(',')).join(' '))
    const anchor = (i) => {
      const x = pt(i, R + 26)[0]
      return Math.abs(x - c) < 4 ? 'middle' : x > c ? 'start' : 'end'
    }
    const ariaLabel = computed(() => props.dims.map((d) => `${d.name} ${d.score ?? '未评估'}`).join('，'))
    return { size, c, R, pt, ring, shape, anchor, ariaLabel }
  },
}
</script>
