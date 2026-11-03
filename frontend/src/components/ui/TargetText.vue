<template>
  <div :class="['target', wrapCls]">
    <button v-if="env.hideText && !revealed" type="button" :class="['veil', cls]" title="显示原文" @click="$emit('reveal')">
      <span :class="['veil__text', env.textClass]" aria-hidden="true">{{ text }}</span>
      <span class="veil__label"><AppIcon name="eye" :size="16" /> 点击显示</span>
    </button>
    <template v-else>
      <SaveableText :class="[env.textClass, cls]" :language="env.language" :sentence="text">{{ text }}<button v-if="translatable && !showTr" type="button" class="tr-btn"
        title="翻译这一句" aria-label="翻译这一句" @click="asked = true"><AppIcon name="translate" :size="14" /></button></SaveableText>
      <TranslationLine v-if="showTr" :text="text" :language="env.language" :given="translation" />
    </template>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, ref, type PropType } from 'vue'
import AppIcon from './AppIcon.vue'
import SaveableText from './SaveableText.vue'
import TranslationLine from './TranslationLine.vue'
import type { Env } from '../../api/models'

/**
 * Target-language text that can be blurred for blind listening.
 * 生成时带上的中文直接显示。没有译文的旧内容，才在打开翻译时再去请求。
 */
export default defineComponent({
  name: 'TargetText',
  components: { AppIcon, SaveableText, TranslationLine },
  props: {
    text: { type: String, required: true },
    translation: { type: String, default: '' },
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
