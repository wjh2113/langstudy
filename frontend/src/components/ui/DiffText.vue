<template>
  <SaveableText :class="['diff', env.textClass]" :language="env.language" :sentence="sentence">
    <span v-for="(t, i) in tokens" :key="i" :class="{ miss: !t.ok }">{{ t.t }}{{ env.language === 'ja' ? '' : ' ' }}</span>
  </SaveableText>
</template>

<script lang="ts">
import { computed, defineComponent, type PropType } from 'vue'
import SaveableText from './SaveableText.vue'
import type { DiffToken, Env } from '../../api/models'

/** 跟读对照：没听对的部分用红线标出。选中文字可以加入生词本。 */
export default defineComponent({
  name: 'DiffText',
  components: { SaveableText },
  props: {
    tokens: { type: Array as PropType<DiffToken[]>, required: true },
    env: { type: Object as PropType<Env>, required: true },
  },
  setup(props) {
    const sentence = computed(() => props.tokens.map((t) => t.t).join(props.env.language === 'ja' ? '' : ' '))
    return { sentence }
  },
})
</script>
