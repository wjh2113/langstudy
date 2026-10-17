<template>
  <div :class="['target', wrapCls]">
    <button v-if="env.hideText && !revealed" type="button" :class="['veil', cls]" title="显示原文" @click="$emit('reveal')">
      <span :class="['veil__text', env.textClass]" aria-hidden="true">{{ text }}</span>
      <span class="veil__label"><AppIcon name="eye" :size="16" /> 点击显示</span>
    </button>
    <template v-else>
      <p :class="[env.textClass, cls]">{{ text }}<button v-if="translatable && !showTr" type="button" class="tr-btn"
        title="翻译这一句" aria-label="翻译这一句" @click="asked = true"><AppIcon name="translate" :size="14" /></button></p>
      <TranslationLine v-if="showTr" :text="text" :language="env.language" />
    </template>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, ref, type PropType } from 'vue'
import AppIcon from './AppIcon.vue'
import TranslationLine from './TranslationLine.vue'
import type { Env } from '../../api/models'

/**
 * Target-language text that can be blurred for blind listening.
 * Its Chinese translation is fetched only on demand: with 显示翻译 on, when the
 * blurred text is revealed, or when the learner taps 译 for this one sentence.
 */
export default defineComponent({
  name: 'TargetText',
  components: { AppIcon, TranslationLine },
  props: {
    text: { type: String, required: true },
    env: { type: Object as PropType<Env>, required: true },
    cls: { type: String, default: '' },
    wrapCls: { type: String, default: '' },
    revealed: { type: Boolean, default: false },
    translatable: { type: Boolean, default: true },
  },
  emits: ['reveal'],
  setup(props) {
    const asked = ref(false)
    const showTr = computed(() => props.translatable &&
      (props.env.showTranslation || asked.value || (props.env.hideText && props.revealed)))
    return { asked, showTr }
  },
})
</script>
