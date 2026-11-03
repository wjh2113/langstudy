<template>
  <ModalDialog :open="open" title="上传资料" icon="doc" wide @close="close">
    <p class="muted">支持 PDF、PPTX、Word，也可以直接粘贴文字。可以一次选多个文件。文字在本地提取，只调用一次模型做归类，原文不会被改写。</p>
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
      <input ref="fileInput" type="file" multiple :accept="uploadAccept" :disabled="busy" @change="onFile" />
      <span :title="fileTitle">{{ fileLabel }}</span>
    </label>
    <ul v-if="files.length > 1" class="upload-files">
      <li v-for="(f, i) in files" :key="i">{{ f.name }}</li>
    </ul>
    <textarea v-if="!isTopicImport" v-model="paste" class="upload-text" rows="8" maxlength="40000" placeholder="或者把课件文字粘贴在这里" />
    <p v-if="isTopicImport" class="muted">已选 Markdown / 压缩包，点下面会按导入话题处理。</p>
    <p v-if="status" class="banner banner--info"><span class="spinner" /> {{ status }}</p>
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
      <button type="button" class="btn btn--primary" :disabled="busy" @click="submit">
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
    const files = ref<File[]>([])
    const fileInput = ref<HTMLInputElement | null>(null)
    const paste = ref('')
    const busy = ref(false)
    const status = ref('')
    const prompt = ref('')
    const copiedPrompt = ref(false)
    const imported = ref<ImportedTopic[]>([])
    const importErrors = ref<string[]>([])
    const importReplaced = ref(0)
    const MAX_FILES = 40

    const isTopicFile = (f: File) => /\.(md|markdown|txt|zip)$/i.test(f.name)
    const isTopicImport = computed(() => files.value.length > 0 && files.value.every(isTopicFile))
    const fileTitle = computed(() => files.value.map((f) => f.name).join('\n'))
    const fileLabel = computed(() => {
      if (!files.value.length) {
        return isAdmin.value
          ? '选择 PDF、PPTX、DOCX、.md 或 .zip，可一次选多个'
          : '选择 PDF、PPTX 或 DOCX，可一次选多个'
      }
      if (files.value.length === 1) return files.value[0].name
      return `已选 ${files.value.length} 个文件`
    })
    const uploadAccept = computed(() => isAdmin.value
      ? '.pdf,.pptx,.docx,.md,.markdown,.txt,.zip,application/pdf,text/markdown,application/zip'
      : '.pdf,.pptx,.docx,application/pdf')

    function reset() {
      files.value = []
      paste.value = ''
      imported.value = []
      importErrors.value = []
      importReplaced.value = 0
      status.value = ''
      if (fileInput.value) fileInput.value.value = ''
    }

    // 对话框里的提示。页面上的错误条在弹层后面，用户会觉得点了没反应。
    function showError(message: string) {
      importErrors.value = [message]
    }

    function chosenFiles(): File[] {
      if (files.value.length) return files.value
      return Array.from(fileInput.value?.files || [])
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
          showError(e.message)
        }
      }
    })

    function onFile(e: Event) {
      const input = e.target as HTMLInputElement
      const picked = Array.from(input.files || [])
      // 空的 change 不要把已选文件冲掉。也不要在这里清空 input.value：
      // 有的浏览器会把刚读到的文件一起清掉，点导入时列表是空的。
      if (!picked.length) return
      files.value = picked
      imported.value = []
      importErrors.value = []
      importReplaced.value = 0
      status.value = ''
      if (picked.length > MAX_FILES) {
        showError(`一次最多选 ${MAX_FILES} 个文件，当前选了 ${picked.length} 个`)
      }
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
      if (busy.value) return
      const picked = chosenFiles()
      if (!files.value.length && picked.length) files.value = picked
      if (!picked.length && !paste.value.trim()) {
        showError('请先选择文件，或粘贴课件文字')
        return
      }
      importErrors.value = []
      const topicFiles = picked.filter(isTopicFile)
      if (topicFiles.length && topicFiles.length !== picked.length) {
        showError('Markdown 话题和课件请分开上传')
        return
      }
      if (picked.length > MAX_FILES) {
        showError(`一次最多选 ${MAX_FILES} 个文件，当前选了 ${picked.length} 个`)
        return
      }
      if (isTopicImport.value) {
        if (!isAdmin.value) {
          showError('只有管理员可以导入 Markdown 话题')
          return
        }
        busy.value = true
        emit('busy', { on: true, topicImport: true })
        const importedAll: ImportedTopic[] = []
        const errors: string[] = []
        let replaced = 0
        try {
          for (let i = 0; i < picked.length; i++) {
            const item = picked[i]
            status.value = `正在导入 ${i + 1}/${picked.length}：${item.name}`
            try {
              const result = await api.importTopics(item)
              importedAll.push(...result.imported)
              replaced += result.replaced || 0
              for (const msg of result.errors || []) errors.push(`${item.name}：${msg}`)
            } catch (e: any) {
              errors.push(`${item.name}：${e.message}`)
            }
          }
          status.value = ''
          imported.value = importedAll
          importErrors.value = errors
          importReplaced.value = replaced
          emit('imported', { imported: importedAll, replaced, errors })
          // 只选了一个文件且只导入一份时，仍直接进入练习。多文件留在列表里。
          if (picked.length === 1 && importedAll.length === 1 && !errors.length) {
            close()
            router.push(`/practice/${importedAll[0].id}`)
          }
        } finally {
          busy.value = false
          status.value = ''
          emit('busy', { on: false, topicImport: true })
        }
        return
      }
      const form = new FormData()
      form.set('language', store.prefs.language)
      form.set('level', store.prefs.level)
      for (const item of picked) form.append('file', item)
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
      isAdmin, files, fileInput, fileLabel, fileTitle, paste, busy, status, prompt, copiedPrompt, imported, importErrors, importReplaced,
      isTopicImport, uploadAccept, MODE_NAMES,
      close, onFile, copyPrompt, submit,
    }
  },
})
</script>
