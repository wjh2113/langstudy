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
    <div v-if="report.cardsAdded || (coach && coach.level)" class="coach-strip">
      <p v-if="report.cardsAdded">
        已把 {{ report.cardsAdded }} 句改正后的句子加入错句本。<button class="link" @click="$emit('review')">去复习</button>
      </p>
      <p v-if="coach && coach.level">下次建议：{{ coach.reason }}</p>
    </div>

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
          <template v-if="it.kind === 'dictation'">
            <div class="item__meta">
              <span class="tag">填空</span>
              <span :class="['pill', it.correct ? 'good' : 'low']">{{ it.correct ? '正确' : '错误' }}</span>
              <PlayButton :id="`dict-${i}`" :text="it.prompt" :env="env" size="sm" />
            </div>
            <p :class="['item__prompt', env.textClass]">{{ it.prompt }}</p>
            <div class="item__rows">
              <div class="row"><span class="row__k">你填的</span><p :class="env.textClass">{{ it.answer || '（没填）' }}</p></div>
              <div v-if="!it.correct" class="row row--better"><span class="row__k">正确</span><p :class="env.textClass">{{ it.reference }}</p></div>
            </div>
          </template>
          <template v-else>
          <div class="item__meta">
            <span class="tag">{{ it.followUp ? '追问' : kinds[it.kind] || '作答' }}</span>
            <span>{{ it.input === 'voice' ? '语音' : '文字' }}</span>
            <span v-if="it.metrics.lagSec != null">影子跟读 · 晚 {{ it.metrics.lagSec }} 秒 · 用时 {{ it.metrics.durationRatio }} 倍</span>
            <span v-if="it.metrics.rate != null">{{ it.metrics.rate }} {{ report.stats.rateUnit }}</span>
            <span v-if="it.metrics.pron != null">发音评测 {{ Math.round(it.metrics.pron) }}</span>
            <span v-else-if="it.metrics.similarity != null">吻合 {{ Math.round(it.metrics.similarity * 100) }}%</span>
          </div>
          <p v-if="it.prompt" :class="['item__prompt', env.textClass]">{{ it.prompt }}</p>
          <DiffText v-if="it.diff" :tokens="it.diff" :env="env" />
          <div class="item__rows">
            <div class="row"><span class="row__k">你说的</span><p :class="env.textClass">{{ it.answer }}</p></div>
            <div v-if="it.audioUrl" class="ab">
              <span class="row__k">对比听</span>
              <span class="ab__side"><span class="muted">我的录音</span><audio :src="it.audioUrl" controls preload="none" /></span>
              <span v-if="standardOf(it)" class="ab__side">
                <span class="muted">标准音</span>
                <PlayButton :id="`std-${i}`" :text="standardOf(it)" :env="env" label="播放" />
              </span>
            </div>
            <div v-if="it.corrected && it.corrected !== it.answer" class="row">
              <span class="row__k">修改后</span><p :class="env.textClass">{{ it.corrected }}</p>
              <StarButton :card="{ language: env.language, kind: 'sentence', front: it.corrected, meaning: it.notes,
                example: it.better && it.better !== it.corrected ? it.better : '', extra: it.answer, sourceSession: session.id }" />
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
          </template>
        </article>
      </div>
    </section>

    <StudyNotes :session-id="session.id" :env="env" />

    <section v-if="report.vocabulary.length">
      <h2>值得记下的表达</h2>
      <div class="vocab">
        <div v-for="(v, i) in report.vocabulary" :key="i" class="vocab__item">
          <div class="vocab__word">
            <PlayButton :id="`vocab-${i}`" :text="v.example || v.word" :env="env" size="sm" />
            <strong :class="env.textClass">{{ v.word }}</strong>
            <span v-if="v.reading" class="muted">{{ v.reading }}</span>
            <StarButton class="star--end" :card="{ language: env.language, kind: 'word', front: v.word, reading: v.reading,
              meaning: v.meaning, example: v.example, sourceSession: session.id }" />
          </div>
          <p>{{ v.meaning }}</p>
          <p v-if="v.example" :class="['vocab__ex', env.textClass]">{{ v.example }}</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script>
import { computed, onMounted, ref } from 'vue'
import StarButton from './StarButton.vue'
import { api } from '../api'
import DiffText from './DiffText.vue'
import PlayButton from './PlayButton.vue'
import RadarChart from './RadarChart.vue'
import StudyNotes from './StudyNotes.vue'

export default {
  name: 'ReportView',
  components: { DiffText, PlayButton, RadarChart, StarButton, StudyNotes },
  props: {
    report: { type: Object, required: true },
    session: { type: Object, required: true },
    env: { type: Object, required: true },
  },
  emits: ['retry', 'home', 'review'],
  setup(props) {
    const grade = (s) => (s == null ? '' : s >= 85 ? 'good' : s >= 70 ? 'mid' : 'low')
    const coach = ref(null)
    onMounted(() => api.coach(props.env.language).then((c) => (coach.value = c)).catch(() => {}))
    // what "standard" sounds like for an item: the better phrasing, the fix, or the script
    const standardOf = (it) => it.better || (it.corrected !== it.answer && it.corrected) || it.reference || ''
    return {
      content: computed(() => props.session.content),
      kinds: { answer: '回答', line: '台词', shadow: '跟读' },
      grade, coach, standardOf,
    }
  },
}
</script>
