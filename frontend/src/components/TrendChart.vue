<template>
  <svg v-if="points.length > 1" class="trend" :viewBox="`0 0 ${w} ${h}`" role="img" :aria-label="`最近 ${points.length} 次综合得分`">
    <g v-for="v in [60, 80]" :key="v">
      <line :x1="pad" :x2="w - pad" :y1="ys(v)" :y2="ys(v)" class="trend__grid" />
      <text :x="w - pad + 4" :y="ys(v)" dominant-baseline="middle" class="trend__tick">{{ v }}</text>
    </g>
    <path :d="path" class="trend__line" />
    <circle v-for="(p, i) in points" :key="i" :cx="xs(i)" :cy="ys(p.overall)" r="3.5" class="trend__dot">
      <title>{{ p.createdAt.slice(0, 10) }}：{{ p.overall }}</title>
    </circle>
  </svg>
</template>

<script>
import { computed } from 'vue'

export default {
  name: 'TrendChart',
  props: { points: { type: Array, required: true } },
  setup(props) {
    const w = 900
    const h = 150
    const pad = 20
    const xs = (i) => pad + (i * (w - pad * 2)) / (props.points.length - 1)
    const ys = (v) => h - pad - ((Math.max(v, 40) - 40) / 60) * (h - pad * 2)
    const path = computed(() => props.points.map((p, i) => `${i ? 'L' : 'M'}${xs(i)},${ys(p.overall)}`).join(' '))
    return { w, h, pad, xs, ys, path }
  },
}
</script>
