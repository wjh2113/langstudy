<template>
  <div class="settings">
    <h2 v-if="!inDrawer" class="settings__title"><AppIcon name="settings" :size="22" /> 练习设置</h2>

    <div class="settings__group">
      <h3><AppIcon name="gauge" /> 语速</h3>
      <SegControl :options="rates" :model-value="env.rate" block label="语速" @update:model-value="(v) => setDisplay({ rate: v })" />
    </div>

    <div v-if="env.accents.length > 1" class="settings__group">
      <h3><AppIcon name="headphones" /> 听力口音</h3>
      <AccentSelect :accents="env.accents" :model-value="env.accent" @update:model-value="(k) => setAccent(env.language, k)" />
    </div>

    <div class="settings__group">
      <div class="setting-row">
        <AppIcon name="eye-off" />
        <div><h3>盲听</h3><p>先隐藏原文，只听录音作答，需要时再点开</p></div>
        <ToggleSwitch :model-value="env.hideText" label="盲听" @update:model-value="(v) => setDisplay({ hideText: v })" />
      </div>
      <div class="setting-row">
        <AppIcon name="translate" />
        <div><h3>显示中文翻译</h3><p>在原文下方显示中文（用到时才翻译）</p></div>
        <ToggleSwitch :model-value="env.showTranslation" label="显示中文翻译" @update:model-value="(v) => setDisplay({ showTranslation: v })" />
      </div>
      <div v-if="handsFreeModes.includes(mode)" class="setting-row">
        <AppIcon name="mic" />
        <div><h3>免手动</h3><p>AI 说完自动开麦，停顿约 1.5 秒自动提交</p></div>
        <ToggleSwitch :model-value="env.handsFree" label="免手动" @update:model-value="(v) => setDisplay({ handsFree: v })" />
      </div>
    </div>

    <div class="settings__group">
      <div class="settings__progress-head">
        <h3><AppIcon name="bars" /> 作答进度</h3>
        <span>{{ progressText }}</span>
      </div>
      <div class="bar"><span :style="{ width: `${progressPct}%` }" /></div>
      <p class="muted settings__saved">
        <template v-if="saveState === 'saving'">正在保存…</template>
        <template v-else-if="saveState === 'error'"><span class="error">自动保存失败，网络恢复后会重试</span></template>
        <template v-else-if="savedAt">已自动保存 {{ savedAt }} · 刷新或关掉页面也能接着做</template>
        <template v-else>每答一题都会自动保存</template>
      </p>
    </div>

    <div class="settings__group settings__current">
      <h3><AppIcon name="doc" /> 当前练习</h3>
      <div class="tags">
        <span :class="['tag', `tag--${env.language}`]">{{ LANG_NAMES[env.language] }}</span>
        <span class="tag tag--mode">{{ MODE_NAMES[mode] }}</span>
        <span v-if="level" class="tag">{{ LEVEL_NAMES[level] }}</span>
      </div>
    </div>

    <button type="button" class="btn btn--primary btn--lg btn--block" :disabled="!canFinish || busy" @click="$emit('finish')">
      <AppIcon name="flag" :size="20" /> {{ busyText || '结束并评分' }}
    </button>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="!env.serverSTT && !env.recognitionSupported" class="hint">这个浏览器不支持语音识别，可以用“写”作答，或换用 Edge。</p>
  </div>
</template>

<script lang="ts">
import { defineComponent, type PropType } from 'vue'
import AccentSelect from '../ui/AccentSelect.vue'
import AppIcon from '../ui/AppIcon.vue'
import SegControl from '../ui/SegControl.vue'
import ToggleSwitch from '../ui/ToggleSwitch.vue'
import type { Env } from '../../api/models'
import { setAccent, setDisplay } from '../../store'
import { LANG_NAMES, LEVEL_NAMES, MODE_NAMES } from '../../lib/format'

/** Right-hand panel (or drawer on small screens): listening settings, progress, finish. */
export default defineComponent({
  name: 'PracticeSettings',
  components: { AccentSelect, AppIcon, SegControl, ToggleSwitch },
  props: {
    env: { type: Object as PropType<Env>, required: true },
    mode: { type: String as PropType<keyof typeof MODE_NAMES>, required: true },
    level: { type: String, default: '' },
    progressText: { type: String, default: '' },
    progressPct: { type: Number, default: 0 },
    canFinish: { type: Boolean, default: false },
    busy: { type: Boolean, default: false },
    busyText: { type: String, default: '' },
    error: { type: String, default: '' },
    savedAt: { type: String, default: '' },
    saveState: { type: String, default: '' },
    inDrawer: { type: Boolean, default: false },
  },
  emits: ['finish'],
  setup() {
    return {
      setDisplay, setAccent, LANG_NAMES, LEVEL_NAMES, MODE_NAMES,
      rates: [0.8, 1, 1.2].map((r) => ({ value: r, label: `${r}×` })),
      handsFreeModes: ['questions', 'dialogue', 'chat'],
    }
  },
})
</script>
