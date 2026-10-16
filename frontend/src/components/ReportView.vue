<template>
  <div class="report" :data-lang="env.language">
    <header class="report__head">
      <div>
        <p class="crumbs">练习报告 / {{ content.topic }}</p>
        <h1 :class="env.textClass">{{ content.title }}</h1>
      </div>
      <div class="report__actions">
        <button class="btn btn--ghost" @click="$emit('home')">换个话题</button>
        <button class="btn btn--primary" @click="$emit('retry')">同话题再练一次</button>
      </div>
    </header>

    <p v-if="report.demo" class="notice">演示模式报告：发音和流利度来自你的实际录音，其余维度为估算。配置大模型后可获得逐句批改。</p>

    <section class="scoreboard">
      <div class="overall">
        <span class="overall__num">{{ report.overall ?? '—' }}</span>
        <span class="overall__label">综合得分</span>
        <p class="overall__summary">{{ report.summary }}</p>
        <dl class="stats">
          <div><dt>作答</dt><dd>{{ report.stats.turns }} 条（语音 {{ report.stats.voiceTurns }}）</dd></div>
          <div v-if="report.stats.avgRate != null">
            <dt>平均语速</dt>
            <dd>{{ report.stats.avgRate }} {{ report.stats.rateUnit }}<small>建议 {{ report.stats.rateRange[0] }}–{{ report.stats.rateRange[1] }}</small></dd>
          </div>
          <div><dt>口头禅</dt><dd>{{ report.stats.fillers }} 次</dd></div>
        </dl>
      </div>
      <RadarChart :dims="report.dimensions" />
    </section>

    <section class="dims">
      <div v-for="d in report.dimensions" :key="d.key" class="dim">
        <div class="dim__top">
          <strong>{{ d.name }}</strong>
          <span :class="['dim__score', grade(d.score)]">{{ d.score ?? '未评估' }}</span>
        </div>
        <div class="bar"><span :class="grade(d.score)" :style="{ width: `${d.score ?? 0}%` }" /></div>
        <p class="dim__comment">{{ d.comment || d.desc }}</p>
        <p v-if="d.key === 'pronunciation' && report.stats.pronSource === 'assessment'" class="dim__source">按跟读/照读录音的发音评测打分</p>
      </div>
    </section>

    <section v-if="report.strengths.length || report.improvements.length" class="two-col">
      <div>
        <h2>做得好的</h2>
        <ul class="list list--good"><li v-for="(s, i) in report.strengths" :key="i">{{ s }}</li></ul>
      </div>
      <div>
        <h2>下次重点改进</h2>
        <ul class="list list--fix"><li v-for="(s, i) in report.improvements" :key="i">{{ s }}</li></ul>
      </div>
    </section>

    <section>
      <h2>逐条回顾</h2>
      <div class="items">
        <article v-for="(it, i) in report.items" :key="i" class="item">
          <div class="item__meta">
            <span class="tag">{{ it.followUp ? '追问' : kinds[it.kind] || '作答' }}</span>
            <span>{{ it.input === 'voice' ? '语音' : '文字' }}</span>
            <span v-if="it.metrics.rate != null">{{ it.metrics.rate }} {{ report.stats.rateUnit }}</span>
            <span v-if="it.metrics.pron != null">发音评测 {{ Math.round(it.metrics.pron) }}</span>
            <span v-else-if="it.metrics.similarity != null">吻合 {{ Math.round(it.metrics.similarity * 100) }}%</span>
          </div>
          <p v-if="it.prompt" :class="['item__prompt', env.textClass]">{{ it.prompt }}</p>
          <DiffText v-if="it.diff" :tokens="it.diff" :env="env" />
          <div class="item__rows">
            <div class="row"><span class="row__k">你说的</span><p :class="env.textClass">{{ it.answer }}</p></div>
            <div v-if="it.corrected && it.corrected !== it.answer" class="row">
              <span class="row__k">修改后</span><p :class="env.textClass">{{ it.corrected }}</p>
            </div>
            <div v-if="it.better" class="row row--better">
              <span class="row__k">更地道</span>
              <p :class="env.textClass">{{ it.better }}</p>
              <PlayButton :id="`better-${i}`" :text="it.better" :env="env" size="sm" />
            </div>
            <div v-if="it.pronNote || (it.pronIssues && it.pronIssues.length)" class="item__notes">
              <p v-if="it.pronNote">发音：{{ it.pronNote }}</p>
              <ul v-if="it.pronIssues && it.pronIssues.length" class="pron-issues">
                <li v-for="(p, k) in it.pronIssues" :key="k"><span :class="env.textClass">{{ p.quote }}</span> — {{ p.note }}</li>
              </ul>
            </div>
            <p v-if="it.notes" class="item__notes">{{ it.notes }}</p>
          </div>
        </article>
      </div>
    </section>

    <section v-if="report.vocabulary.length">
      <h2>值得记下的表达</h2>
      <div class="vocab">
        <div v-for="(v, i) in report.vocabulary" :key="i" class="vocab__item">
          <div class="vocab__word">
            <PlayButton :id="`vocab-${i}`" :text="v.example || v.word" :env="env" size="sm" />
            <strong :class="env.textClass">{{ v.word }}</strong>
            <span v-if="v.reading" class="muted">{{ v.reading }}</span>
          </div>
          <p>{{ v.meaning }}</p>
          <p v-if="v.example" :class="['vocab__ex', env.textClass]">{{ v.example }}</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script>
import { computed } from 'vue'
import DiffText from './DiffText.vue'
import PlayButton from './PlayButton.vue'
import RadarChart from './RadarChart.vue'

export default {
  name: 'ReportView',
  components: { DiffText, PlayButton, RadarChart },
  props: {
    report: { type: Object, required: true },
    session: { type: Object, required: true },
    env: { type: Object, required: true },
  },
  emits: ['retry', 'home'],
  setup(props) {
    const grade = (s) => (s == null ? '' : s >= 85 ? 'good' : s >= 70 ? 'mid' : 'low')
    return {
      content: computed(() => props.session.content),
      kinds: { answer: '回答', line: '台词', shadow: '跟读' },
      grade,
    }
  },
}
</script>
