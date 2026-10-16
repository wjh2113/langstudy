<template>
  <form class="home" :data-lang="prefs.language" @submit.prevent="submit">
    <h1 class="home__title">今天练什么话题？</h1>
    <p class="home__sub">输入一个话题，生成听说练习。用语音作答，结束后从六个维度给你打分。</p>

    <div class="topic">
      <input v-model="topic" class="topic__input" maxlength="200" aria-label="话题" autofocus
        :placeholder="prefs.language === 'ja' ? '例如：日企面试' : '例如：软件工程师面试'" />
      <button class="btn btn--primary btn--lg" :disabled="!topic.trim() || busy">{{ busy ? '正在生成…' : '生成练习' }}</button>
    </div>
    <div class="chips">
      <button v-for="s in suggestions[prefs.language] || []" :key="s" type="button" class="chip" @click="topic = s">{{ s }}</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>

    <div class="options">
      <fieldset class="field">
        <legend>语言</legend>
        <div class="seg">
          <button v-for="l in languages" :key="l.code" type="button" :class="{ on: prefs.language === l.code }"
            @click="update({ language: l.code })">{{ l.code === 'ja' ? '日本語' : 'English' }}</button>
        </div>
      </fieldset>

      <fieldset class="field">
        <legend>难度</legend>
        <div class="seg">
          <button v-for="lv in levels" :key="lv.key" type="button" :class="{ on: prefs.level === lv.key }" :title="lv.label"
            @click="update({ level: lv.key })">
            {{ lv.label.split(' ')[0] }}<small>{{ lv.label.split(' ').slice(1).join(' ').replace(/[()]/g, '') }}</small>
          </button>
        </div>
      </fieldset>

      <fieldset class="field field--wide">
        <legend>练习形式</legend>
        <div class="modes">
          <label v-for="m in modes" :key="m.key" :class="['mode', { on: prefs.mode === m.key }]">
            <input type="radio" name="mode" :value="m.key" :checked="prefs.mode === m.key" @change="update({ mode: m.key })" />
            <strong>{{ m.name }}</strong>
            <span>{{ m.desc }}</span>
          </label>
        </div>
      </fieldset>

      <fieldset v-if="prefs.mode !== 'dialogue'" class="field">
        <legend>{{ prefs.mode === 'article' ? '理解题数量' : '问题数量' }}</legend>
        <div class="seg">
          <button v-for="n in [3, 5, 8]" :key="n" type="button" :class="{ on: prefs.count === n }" @click="update({ count: n })">{{ n }}</button>
        </div>
      </fieldset>
    </div>

    <p v-if="config && config.demoMode" class="notice">
      现在是演示模式：还没有配置大模型，会使用内置示例内容。在 <code>backend/.env</code> 中填写 <code>LLM_API_KEY</code> 后重启后端，即可按你的话题生成。
    </p>
  </form>
</template>

<script>
import { computed, ref } from 'vue'

const MODES = [
  { key: 'questions', name: '话题问答', desc: '一问一答，适合面试、自我介绍、聊观点' },
  { key: 'dialogue', name: '情景对话', desc: '和 AI 分角色对话，练习真实场景应答' },
  { key: 'article', name: '短文', desc: '听一段短文，逐句跟读，再回答理解题' },
]

const SUGGESTIONS = {
  en: ['软件工程师面试', '在餐厅点餐', '向同事介绍项目进展', '机场办理登机', '聊聊你最喜欢的电影', '租房看房'],
  ja: ['日企面试', '在便利店购物', '自我介绍', '向酒店前台咨询', '聊聊周末计划', '打电话预约餐厅'],
}

export default {
  name: 'HomeView',
  props: {
    config: { type: Object, default: null },
    prefs: { type: Object, required: true },
    busy: { type: Boolean, default: false },
    error: { type: String, default: '' },
  },
  emits: ['update:prefs', 'start'],
  setup(props, { emit }) {
    const topic = ref(props.prefs.topic || '')
    const languages = computed(() => props.config?.languages || [])
    const levels = computed(() => (languages.value.find((l) => l.code === props.prefs.language) || languages.value[0])?.levels || [])

    const update = (patch) => emit('update:prefs', { ...props.prefs, ...patch })

    function submit() {
      const t = topic.value.trim()
      if (!t || props.busy) return
      const next = { ...props.prefs, topic: t }
      emit('update:prefs', next)
      emit('start', next)
    }

    return { topic, languages, levels, modes: MODES, suggestions: SUGGESTIONS, update, submit }
  },
}
</script>
