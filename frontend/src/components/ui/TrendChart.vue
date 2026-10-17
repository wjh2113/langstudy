<template>
  <div class="trend">
    <svg :viewBox="`0 0 ${w} ${h}`" role="img" :aria-label="ariaLabel">
      <g v-for="v in [0, 20, 40, 60, 80, 100]" :key="v">
        <line :x1="padL" :x2="w - padR" :y1="ys(v)" :y2="ys(v)" class="trend__grid" />
        <text :x="padL - 8" :y="ys(v)" text-anchor="end" dominant-baseline="middle" class="trend__tick">{{ v }}</text>
      </g>
      <text v-for="t in ticks" :key="t.label" :x="t.x" :y="h - 6" text-anchor="middle" class="trend__tick">{{ t.label }}</text>
      <g v-for="s in drawn" :key="s.key" :class="['trend__series', `trend__series--${s.key}`]">
        <path :d="s.path" class="trend__line" />
        <circle v-for="(p, i) in s.pts" :key="i" :cx="p.x" :cy="p.y" r="3.2" class="trend__dot">
          <title>{{ s.name }} {{ p.date }}：{{ p.v }}</title>
        </circle>
      </g>
    </svg>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, type PropType } from 'vue'

export interface TrendSeries { key: string; name: string; points: { createdAt: string; overall: number | null }[] }

const DAY = 86400000

/** Overall score per practice over the last `days` days, one line per language. */
export default defineComponent({
  name: 'TrendChart',
  props: {
    series: { type: Array as PropType<TrendSeries[]>, required: true },
    days: { type: Number, default: 30 },
  },
  setup(props) {
    const w = 1000
    const h = 220
    const padL = 36
    const padR = 12
    const padT = 10
    const padB = 28
    const end = new Date()
    end.setHours(23, 59, 59, 999)
    const start = end.getTime() - props.days * DAY
    const xs = (t: number) => padL + ((t - start) / (end.getTime() - start)) * (w - padL - padR)
    const ys = (v: number) => padT + (1 - v / 100) * (h - padT - padB)
    const drawn = computed(() => props.series.map((s) => {
      const pts = s.points
        .filter((p) => p.overall != null && new Date(p.createdAt).getTime() >= start)
        .map((p) => ({ x: xs(new Date(p.createdAt).getTime()), y: ys(p.overall as number), v: p.overall, date: p.createdAt.slice(5, 10) }))
      return { ...s, pts, path: pts.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ') }
    }))
    const ticks = computed(() => {
      const out = []
      for (let d = props.days; d >= 0; d -= Math.ceil(props.days / 8)) {
        const t = end.getTime() - d * DAY
        const dt = new Date(t)
        out.push({ x: xs(t), label: `${dt.getMonth() + 1}-${dt.getDate()}` })
      }
      return out
    })
    const ariaLabel = computed(() => drawn.value.map((s) => `${s.name} ${s.pts.length} 次练习`).join('，'))
    return { w, h, padL, padR, xs, ys, drawn, ticks, ariaLabel }
  },
})
</script>
