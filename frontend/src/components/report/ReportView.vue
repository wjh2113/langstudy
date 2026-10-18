<template>
  <div class="report" :data-lang="env.language">
    <header class="page-head">
      <div>
        <p class="crumbs"><span>{{ MODE_NAMES[content.mode] }}</span> / <span>{{ content.topic }}</span>
          <span :class="['tag', `tag--${env.language}`]">{{ LANG_NAMES[env.language] }}</span></p>
        <h1>{{ readonly ? `${owner || '学习者'} 的练习报告` : '本次练习报告' }}</h1>
      </div>
      <div class="page-head__actions"><slot name="actions" /></div>
    </header>

    <p v-if="report.demo" class="banner banner--info"><AppIcon name="info" /> 演示模式报告：发音和流利度来自你的实际录音，其余维度为估算。配置网关后可获得逐句批改。</p>
    <slot name="notice" />

    <section class="card hero">
      <div class="hero__score">
        <svg class="laurel laurel--l" viewBox="0 0 40 90" aria-hidden="true"><path d="M30 86C12 70 8 46 16 18" /><g><ellipse v-for="k in 6" :key="k" :cx="20 - k * 0.6" :cy="80 - k * 11" rx="4" ry="8" :transform="`rotate(-35 ${20 - k * 0.6} ${80 - k * 11})`" /></g></svg>
        <div class="hero__center">
          <span class="hero__num">{{ report.overall ?? '—' }}</span>
          <span class="hero__label">综合评分</span>
          <p class="hero__summary">{{ verdict }}</p>
        </div>
        <svg class="laurel laurel--r" viewBox="0 0 40 90" aria-hidden="true"><path d="M10 86C28 70 32 46 24 18" /><g><ellipse v-for="k in 6" :key="k" :cx="20 + k * 0.6" :cy="80 - k * 11" rx="4" ry="8" :transform="`rotate(35 ${20 + k * 0.6} ${80 - k * 11})`" /></g></svg>
      </div>
      <div class="hero__radar"><RadarChart :dims="report.dimensions" /></div>
      <ul class="hero__list">
        <li v-for="d in report.dimensions" :key="d.key">
          <span class="dot" :style="{ background: DIM[d.key]?.color }" />
          <span>{{ d.name }}</span>
          <strong :class="['score-text', scoreBand(d.score)]">{{ d.score ?? '—' }}</strong>
        </li>
      </ul>
    </section>

    <p v-if="report.summary" class="report__summary">{{ report.summary }}</p>
    <dl class="stat-row">
      <div><dt>作答</dt><dd>{{ report.stats.turns }} 条<small>语音 {{ report.stats.voiceTurns }}</small></dd></div>
      <div v-if="report.stats.avgRate != null"><dt>平均语速</dt><dd>{{ report.stats.avgRate }}<small>{{ report.stats.rateUnit }} · 建议 {{ report.stats.rateRange[0] }}–{{ report.stats.rateRange[1] }}</small></dd></div>
      <div><dt>口头禅</dt><dd>{{ report.stats.fillers }}<small>次</small></dd></div>
      <div v-if="report.stats.dictationAccuracy != null"><dt>填空正确率</dt><dd>{{ report.stats.dictationAccuracy }}<small>%</small></dd></div>
    </dl>

    <div class="report__grid">
      <section class="dim-grid">
        <article v-for="d in report.dimensions" :key="d.key" class="card dim-card">
          <div class="dim-card__head">
            <span class="dim-card__icon" :style="{ background: DIM[d.key]?.color }"><AppIcon :name="DIM[d.key]?.icon || 'bars'" :size="18" /></span>
            <strong>{{ d.name }}</strong>
            <span :class="['dim-card__score', scoreBand(d.score)]">{{ d.score ?? '未评估' }}</span>
          </div>
          <div class="bar"><span :style="{ width: `${d.score ?? 0}%`, background: DIM[d.key]?.color }" /></div>
          <p class="dim-card__comment">{{ d.comment || d.desc }}</p>
          <p v-if="d.key === 'pronunciation' && report.stats.pronSource === 'assessment'" class="muted dim-card__src">按发音评测打分</p>
        </article>
      </section>
      <aside class="report__side">
        <section v-if="report.strengths.length" class="card side-card side-card--good">
          <h2><AppIcon name="check-circle" :size="22" /> 做得好的</h2>
          <ul><li v-for="(s, i) in report.strengths" :key="i"><AppIcon name="check-circle" :size="18" /><span>{{ s }}</span></li></ul>
        </section>
        <section v-if="report.improvements.length" class="card side-card side-card--warn">
          <h2><AppIcon name="alert" :size="22" /> 下次改进</h2>
          <ul><li v-for="(s, i) in report.improvements" :key="i"><AppIcon name="alert" :size="18" /><span>{{ s }}</span></li></ul>
        </section>
      </aside>
    </div>

    <div class="report__grid report__grid--wide">
      <section class="card review">
        <h2 class="card__title"><AppIcon name="list" /> 逐条回顾</h2>
        <div class="table-wrap">
          <table class="table review-table">
            <thead><tr><th>#</th><th>你说的</th><th>修改后</th><th>更地道的说法</th><th>试听</th><th /></tr></thead>
            <tbody>
              <template v-for="(it, i) in report.items" :key="i">
                <tr :class="{ open: openItem === i }">
                  <td class="muted" data-label="#">{{ i + 1 }}</td>
                  <td data-label="你说的">
                    <span class="tag tag--sm">{{ it.kind === 'dictation' ? '填空' : it.followUp ? '追问' : KINDS[it.kind] || '作答' }}</span>
                    <span :class="env.textClass">{{ it.answer || '（没填）' }}</span>
                  </td>
                  <td data-label="修改后" :class="env.textClass">
                    <template v-if="it.kind === 'dictation'"><span :class="it.correct ? 'ok-text' : 'bad-text'">{{ it.correct ? '✓ 正确' : it.reference }}</span></template>
                    <template v-else-if="it.corrected && it.corrected !== it.answer">{{ it.corrected }}</template>
                    <span v-else-if="it.ok || it.kind === 'shadow'" class="ok-text">✓ 没问题</span>
                  </td>
                  <td data-label="更地道的说法" :class="env.textClass">{{ it.better }}</td>
                  <td data-label="试听"><PlayButton v-if="standardOf(it)" :id="`std-${i}`" :text="standardOf(it)" :env="env" size="sm" /></td>
                  <td data-label=""><button type="button" class="icon-btn" :aria-expanded="openItem === i" aria-label="详情" @click="openItem = openItem === i ? -1 : i">
                    <AppIcon :name="openItem === i ? 'chevron-up' : 'chevron-down'" :size="16" /></button></td>
                </tr>
                <tr v-if="openItem === i" class="review-table__detail">
                  <td data-label="" />
                  <td colspan="5" data-label="">
                    <p v-if="it.prompt" :class="['muted', env.textClass]">{{ it.kind === 'dictation' ? '原句' : '题目' }}：{{ it.prompt }}</p>
                    <DiffText v-if="it.diff" :tokens="it.diff" :env="env" />
                    <div class="metric-tags">
                      <span class="tag tag--sm">{{ it.input === 'voice' ? '语音' : '文字' }}</span>
                      <span v-if="it.metrics.rate != null" class="tag tag--sm">{{ it.metrics.rate }} {{ report.stats.rateUnit }}</span>
                      <span v-if="it.metrics.pron != null" class="tag tag--sm">发音评测 {{ Math.round(it.metrics.pron) }}</span>
                      <span v-else-if="it.metrics.similarity != null" class="tag tag--sm">吻合 {{ Math.round(it.metrics.similarity * 100) }}%</span>
                      <span v-if="it.metrics.lagSec != null" class="tag tag--sm">影子跟读 · 晚 {{ it.metrics.lagSec }} 秒 · {{ it.metrics.durationRatio }} 倍</span>
                    </div>
                    <div v-if="it.audioUrl" class="ab">
                      <span class="muted">我的录音</span><audio :src="audioSrc(it.audioUrl)" controls preload="none" />
                    </div>
                    <p v-if="it.notes" class="item-notes">{{ it.notes }}</p>
                    <p v-if="it.pronNote" class="item-notes">发音：{{ it.pronNote }}</p>
                    <ul v-if="it.pronIssues && it.pronIssues.length" class="pron-issues">
                      <li v-for="(p, k) in it.pronIssues" :key="k"><span :class="env.textClass">{{ p.quote }}</span> — {{ p.note }}</li>
                    </ul>
                    <StarButton v-if="!readonly && it.corrected && it.corrected !== it.answer && it.kind !== 'dictation'" label="加入错句本"
                      :card="{ language: env.language, kind: 'sentence', front: it.corrected, meaning: it.notes,
                        example: it.better && it.better !== it.corrected ? it.better : '', extra: it.answer, sourceSession: sessionId }" />
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="report.vocabulary.length" class="card expr">
        <h2 class="card__title"><AppIcon name="star-fill" /> 值得记下的表达</h2>
        <article v-for="(v, i) in report.vocabulary" :key="i" class="expr-card">
          <PlayButton :id="`vocab-${i}`" :text="v.example || v.word" :env="env" size="md" />
          <div class="expr-card__body">
            <div class="expr-card__top">
              <strong :class="env.textClass">{{ v.word }}</strong>
              <span v-if="v.reading" class="muted">{{ v.reading }}</span>
              <StarButton v-if="!readonly" class="expr-card__star" label="收藏" :card="{ language: env.language, kind: 'word', front: v.word, reading: v.reading,
                meaning: v.meaning, example: v.example, sourceSession: sessionId }" />
            </div>
            <p><span class="muted">中文意思</span>{{ v.meaning }}</p>
            <p v-if="v.example"><span class="muted">例句</span><span :class="env.textClass">{{ v.example }}</span></p>
          </div>
        </article>
      </section>
    </div>

    <StudyNotes v-if="!readonly" :session-id="sessionId" :env="env" />
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, ref, type PropType } from 'vue'
import StudyNotes from '../practice/StudyNotes.vue'
import AppIcon from '../ui/AppIcon.vue'
import DiffText from '../ui/DiffText.vue'
import PlayButton from '../ui/PlayButton.vue'
import RadarChart from '../ui/RadarChart.vue'
import StarButton from '../ui/StarButton.vue'
import type { Content, Env, Report, ReportItem } from '../../api/models'
import { LANG_NAMES, MODE_NAMES, scoreBand } from '../../lib/format'

const DIM: Record<string, { color: string; icon: string }> = {
  listening: { color: '#4F6AF6', icon: 'headphones' },
  pronunciation: { color: '#2A9D8F', icon: 'speaker' },
  fluency: { color: '#8B5CF6', icon: 'chat-dots' },
  grammar: { color: '#F59E0B', icon: 'doc' },
  vocabulary: { color: '#0EA5E9', icon: 'book' },
  content: { color: '#14B8A6', icon: 'pen' },
}

/** The graded report. `readonly` is the shared view (no saving cards, no notes, audio via the share link). */
export default defineComponent({
  name: 'ReportView',
  components: { AppIcon, DiffText, PlayButton, RadarChart, StarButton, StudyNotes },
  props: {
    report: { type: Object as PropType<Report>, required: true },
    content: { type: Object as PropType<Content>, required: true },
    sessionId: { type: String, required: true },
    env: { type: Object as PropType<Env>, required: true },
    readonly: { type: Boolean, default: false },
    owner: { type: String, default: '' },
    audioBase: { type: String, default: '' }, // shared view: replace /api/sessions/{id}/audio with this
  },
  setup(props) {
    const openItem = ref(-1)
    const verdict = computed(() => {
      const s = props.report.overall
      if (s == null) return ''
      return s >= 90 ? '非常出色，继续保持！' : s >= 80 ? '表现良好，继续保持！' : s >= 70 ? '不错，还有提升空间' : s >= 60 ? '及格了，针对弱项多练练' : '别灰心，多练几次会快速进步'
    })
    // what "standard" sounds like for an item: the better phrasing, the fix, or the script
    const standardOf = (it: ReportItem) => it.better || (it.corrected !== it.answer && it.corrected) || it.reference || ''
    const audioSrc = (url: string) => (props.audioBase ? props.audioBase + url.split('/').pop() : url)
    return { openItem, verdict, standardOf, audioSrc, scoreBand, DIM, LANG_NAMES, MODE_NAMES, KINDS: { answer: '回答', line: '台词', shadow: '跟读' } as Record<string, string> }
  },
})
</script>
