<template>
  <ModalDialog :open="open" title="上传资料" icon="doc" wide @close="close">
    <p class="muted">支持 PDF、PPTX、Word，也可以直接粘贴文字。文字在本地提取，只调用一次模型做归类，原文不会被改写。</p>
    <template v-if="isAdmin">
      <p class="muted">管理员还可以上传别的模型写好的 <code>.md</code> 或 <code>.zip</code>，导入后直接进练习历史和学习笔记。相同「语言 + 话题 + 级别 + 形式」会覆盖旧练习。</p>
      <details class="upload-prompt">
        <summary>发给其他模型的说明</summary>
        <textarea class="import-prompt" readonly :value="prompt" rows="10" />
        <button type="button" class="btn btn--outline btn--sm" :disabled="!prompt" @click="copyPrompt">
          <AppIcon name="copy" :size="14" /> {{ copiedPrompt ? '已复制' : '复制说明' }}
        </button>
      </details>
    </template>
    <label class="upload-pick">
      <input type="file" :accept="uploadAccept" :disabled="busy" @change="onFile" />
      <span>{{ file ? file.name : (isAdmin ? '选择 PDF、PPTX、DOCX、.md 或 .zip' : '选择 PDF、PPTX 或 DOCX') }}</span>
    </label>
    <textarea v-if="!isTopicImport" v-model="paste" class="upload-text" rows="8" maxlength="40000" placeholder="或者把课件文字粘贴在这里" />
    <p v-if="isTopicImport" class="muted">已选 Markdown / 压缩包，点下面会按导入话题处理。</p>
    <p v-if="imported.length && importReplaced" class="banner banner--info">
      已按「语言 + 话题 + 级别 + 形式」覆盖原先 {{ importReplaced }} 份练习。
    </p>
    <ul v-if="imported.length" class="import-list">
      <li v-for="item in imported" :key="item.id">
        <RouterLink :to="`/practice/${item.id}`" @click="close">{{ item.topic }}</RouterLink>
        <span class="tag tag--mode">{{ MODE_NAMES[item.mode] || item.mode }}</span>
        <span v-if="item.hasNotes" class="muted">含学习笔记</span>
        <span v-if="item.replaced" class="muted">已覆盖 {{ item.replaced }} 份</span>
      </li>
    </ul>
    <p v-for="(msg, i) in importErrors" :key="'ie'+i" class="banner banner--error"><AppIcon name="alert" /> {{ msg }}</p>
    <div class="modal__actions">
      <button type="button" class="btn btn--ghost" @click="close">{{ imported.length ? '关闭' : '取消' }}</button>
      <button type="button" class="btn btn--primary" :disabled="busy || (!file && !paste.trim())" @click="submit">
        {{ isTopicImport ? (busy ? '正在导入…' : '导入话题') : '整理成课程包' }}
      </button>
    </div>
  </ModalDialog>
</template>

<script lang="ts">
import { computed, defineComponent, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import AppIcon from './ui/AppIcon.vue'
import ModalDialog from './ui/ModalDialog.vue'
import { api } from '../api'
import { isAdmin, store } from '../store'
import { MODE_NAMES } from '../lib/format'

export type ImportedTopic = {
  id: string
  topic: string
  mode: string
  title: string
  hasNotes: boolean
  replaced?: number
}

/** Same upload / Markdown-import dialog used on Home and Topics. */
export default defineComponent({
  name: 'UploadMaterialsDialog',
  components: { AppIcon, ModalDialog },
  props: {
    open: { type: Boolean, default: false },
  },
  emits: ['close', 'reopen', 'imported', 'error', 'busy'],
  setup(props, { emit }) {
    const router = useRouter()
    const file = ref<File | null>(null)
    const paste = ref('')
    const busy = ref(false)
    const prompt = ref('')
    const copiedPrompt = ref(false)
    const imported = ref<ImportedTopic[]>([])
    const importErrors = ref<string[]>([])
    const importReplaced = ref(0)

    const isTopicImport = computed(() => !!file.value && /\.(md|markdown|txt|zip)$/i.test(file.value.name))
    const uploadAccept = computed(() => isAdmin.value
      ? '.pdf,.pptx,.docx,.md,.markdown,.txt,.zip,application/pdf,text/markdown,application/zip'
      : '.pdf,.pptx,.docx,application/pdf')

    function reset() {
      file.value = null
      paste.value = ''
      imported.value = []
      importErrors.value = []
      importReplaced.value = 0
    }

    function close() {
      reset()
      emit('close')
    }

    watch(() => props.open, async (o) => {
      if (!o) return
      reset()
      if (isAdmin.value && !prompt.value) {
        try {
          prompt.value = (await api.importPrompt()).prompt
        } catch (e: any) {
          emit('error', e.message)
        }
      }
    })

    function onFile(e: Event) {
      const input = e.target as HTMLInputElement
      file.value = input.files?.[0] || null
      imported.value = []
      importErrors.value = []
      importReplaced.value = 0
    }

    async function copyPrompt() {
      if (!prompt.value) return
      try {
        await navigator.clipboard.writeText(prompt.value)
      } catch {
        window.prompt('复制下面的内容：', prompt.value)
      }
      copiedPrompt.value = true
      setTimeout(() => { copiedPrompt.value = false }, 1500)
    }

    async function submit() {
      if (busy.value || (!file.value && !paste.value.trim())) return
      importErrors.value = []
      if (isTopicImport.value) {
        if (!isAdmin.value) {
          emit('error', '只有管理员可以导入 Markdown 话题')
          return
        }
        busy.value = true
        emit('busy', { on: true, topicImport: true })
        try {
          const result = await api.importTopics(file.value!)
          imported.value = result.imported
          importErrors.value = result.errors || []
          importReplaced.value = result.replaced || 0
          emit('imported', result)
          if (result.imported.length === 1 && !result.errors?.length) {
            close()
            router.push(`/practice/${result.imported[0].id}`)
          }
        } catch (e: any) {
          emit('error', e.message)
        } finally {
          busy.value = false
          emit('busy', { on: false, topicImport: true })
        }
        return
      }
      const form = new FormData()
      form.set('language', store.prefs.language)
      form.set('level', store.prefs.level)
      if (file.value) form.set('file', file.value)
      if (paste.value.trim()) form.set('text', paste.value.trim())
      emit('close')
      busy.value = true
      emit('busy', { on: true, topicImport: false, waited: 0 })
      try {
        const res = await api.courseUpload(form, (s) => emit('busy', { on: true, topicImport: false, waited: s }))
        reset()
        router.push(`/course/${res.id}`)
      } catch (e: any) {
        emit('error', e.message)
        emit('reopen')
      } finally {
        busy.value = false
        emit('busy', { on: false, topicImport: false })
      }
    }

    return {
      isAdmin, file, paste, busy, prompt, copiedPrompt, imported, importErrors, importReplaced,
      isTopicImport, uploadAccept, MODE_NAMES,
      close, onFile, copyPrompt, submit,
    }
  },
})
</script>
