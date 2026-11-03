<template>
  <p
    ref="host"
    v-bind="fallthrough"
    :class="{ 'savable--open': !!menu }"
    @contextmenu="onContextMenu"
    @pointerdown="onPointerDown"
  >
    <slot />
  </p>
  <Teleport to="body">
    <div
      v-if="menu"
      ref="menuEl"
      class="pick-menu"
      role="menu"
      :style="{ left: pos.x + 'px', top: pos.y + 'px' }"
      @contextmenu.prevent
    >
      <button type="button" role="menuitem" :disabled="busy || already" @click="save">
        <AppIcon :name="already ? 'star-fill' : 'star'" :size="16" />
        {{ already ? '已收藏' : '添加收藏' }}
      </button>
    </div>
    <p v-if="note" :class="['pick-note', { 'pick-note--err': noteErr }]" role="status">{{ note }}</p>
  </Teleport>
</template>

<script lang="ts">
import { computed, defineComponent, inject, onBeforeUnmount, onMounted, reactive, ref, watch, type PropType } from 'vue'
import AppIcon from './AppIcon.vue'
import type { Lang } from '../../api/models'
import { isSaved, loadSaved, saveCard } from '../../lib/cards'
import { SESSION_ID } from '../../lib/practice'
import {
  cleanFront, collapsed, exampleFor, selectionKind, wordRangeIn,
  type CardKind,
} from '../../lib/selectionSave'
import { cachedTranslation } from '../../lib/translate'

const HOLD_MS = 500
const MOVE_PX = 10
const MENU_W = 160
const MENU_H = 52

/**
 * 练习里的目标语正文：选中单词或句子后，桌面右键、手机长按，加入已有的收藏卡片。
 * 菜单挂到 body，避免被句子列表的 overflow 裁掉。
 */
export default defineComponent({
  name: 'SaveableText',
  inheritAttrs: false,
  components: { AppIcon },
  props: {
    language: { type: String as PropType<Lang>, required: true },
    sentence: { type: String, default: '' },
  },
  setup(props, { attrs }) {
    const sessionId = inject(SESSION_ID, '')
    const host = ref<HTMLElement | null>(null)
    const menuEl = ref<HTMLElement | null>(null)
    const menu = ref<{ kind: CardKind; front: string } | null>(null)
    const pos = reactive({ x: 0, y: 0 })
    const busy = ref(false)
    const note = ref('')
    const noteErr = ref(false)
    const already = computed(() => {
      const m = menu.value
      return !!m && isSaved(props.language, m.kind, m.front)
    })

    let alive = true
    let holdTimer = 0
    let noteTimer = 0
    let startX = 0
    let startY = 0
    let lastTouchAt = 0
    let gesture = 0
    let cancelledGesture = -1
    // 长按松手后系统还会补一次点击，这段时间不要把刚打开的菜单关掉
    let ignoreOutsideUntil = 0

    onMounted(() => { if (props.language) loadSaved(props.language) })
    onBeforeUnmount(() => {
      alive = false
      clearHold()
      window.clearTimeout(noteTimer)
      closeMenu()
    })

    function isControl(target: EventTarget | null): boolean {
      const el = target instanceof Element ? target : null
      return !!el?.closest('input, textarea, button, a, [contenteditable="true"]')
    }

    function inField(node: Node | null): boolean {
      if (!node) return false
      const el = node instanceof Element ? node : node.parentElement
      return !!el?.closest('input, textarea, [contenteditable="true"]')
    }

    /** 选区与这段正文有交集时，只取落在本段里的文字，避免把中文译文一起收进去。 */
    function readSelection(root: HTMLElement): string {
      const sel = window.getSelection()
      if (!sel || sel.isCollapsed || sel.rangeCount === 0) return ''
      const range = sel.getRangeAt(0)
      if (typeof range.intersectsNode === 'function' && !range.intersectsNode(root)) return ''
      if (!root.contains(range.commonAncestorContainer) && !root.contains(range.startContainer) && !root.contains(range.endContainer)) {
        return ''
      }
      if (inField(range.startContainer) && inField(range.endContainer)) return ''
      const piece = range.cloneRange()
      try {
        if (!root.contains(piece.startContainer)) piece.setStart(root, 0)
        if (!root.contains(piece.endContainer)) piece.setEnd(root, root.childNodes.length)
      } catch {
        return ''
      }
      return collapsed(piece.toString())
    }

    function caretRange(x: number, y: number): Range | null {
      const doc = document as Document & {
        caretRangeFromPoint?: (cx: number, cy: number) => Range | null
        caretPositionFromPoint?: (cx: number, cy: number) => { offsetNode: Node; offset: number } | null
      }
      if (typeof doc.caretRangeFromPoint === 'function') return doc.caretRangeFromPoint(x, y)
      if (typeof doc.caretPositionFromPoint === 'function') {
        const caret = doc.caretPositionFromPoint(x, y)
        if (!caret?.offsetNode) return null
        const range = document.createRange()
        const node = caret.offsetNode
        const max = node.nodeType === Node.TEXT_NODE ? (node.textContent || '').length : node.childNodes.length
        try {
          range.setStart(node, Math.max(0, Math.min(caret.offset, max)))
          range.collapse(true)
        } catch {
          return null
        }
        return range
      }
      return null
    }

    /** 没有选区时长按：选中手指下的那个词。 */
    function selectWordAt(x: number, y: number, root: HTMLElement): string {
      const caret = caretRange(x, y)
      if (!caret || !root.contains(caret.startContainer)) return ''
      const node = caret.startContainer
      if (node.nodeType !== Node.TEXT_NODE) return ''
      if (node.parentElement?.closest('input, textarea, button, a, [contenteditable="true"]')) return ''
      const text = node.textContent || ''
      const hit = wordRangeIn(text, caret.startOffset, props.language)
      const sel = window.getSelection()
      if (!sel) return ''
      const range = document.createRange()
      if (hit) {
        range.setStart(node, hit.start)
        range.setEnd(node, hit.end)
      } else {
        const anySel = sel as Selection & { modify?: (cmd: string, dir: string, gran: string) => void }
        if (typeof anySel.modify !== 'function') return ''
        const off = Math.max(0, Math.min(caret.startOffset, text.length))
        range.setStart(node, off)
        range.collapse(true)
        sel.removeAllRanges()
        sel.addRange(range)
        try {
          anySel.modify('move', 'backward', 'word')
          anySel.modify('extend', 'forward', 'word')
        } catch {
          sel.removeAllRanges()
          return ''
        }
        if (!sel.anchorNode || !root.contains(sel.anchorNode) || !sel.focusNode || !root.contains(sel.focusNode)) {
          sel.removeAllRanges()
          return ''
        }
        return collapsed(sel.toString())
      }
      sel.removeAllRanges()
      sel.addRange(range)
      return collapsed(range.toString())
    }

    function place(x: number, y: number, above: boolean) {
      const pad = 8
      let top = above ? y - MENU_H - 12 : y + 8
      if (top + MENU_H > window.innerHeight - pad) top = y - MENU_H - 12
      if (top < pad) top = Math.min(y + 8, window.innerHeight - MENU_H - pad)
      if (top < pad) top = pad
      let left = above ? x - 16 : x
      if (left + MENU_W > window.innerWidth - pad) left = window.innerWidth - MENU_W - pad
      if (left < pad) left = pad
      pos.x = left
      pos.y = top
    }

    function closeMenu() {
      menu.value = null
    }

    function showNote(text: string, err = false) {
      note.value = text
      noteErr.value = err
      window.clearTimeout(noteTimer)
      noteTimer = window.setTimeout(() => { note.value = '' }, 1800)
    }

    function meaningFor(kind: CardKind, front: string): string {
      const direct = cachedTranslation(front, props.language) || ''
      if (direct) return direct
      if (kind !== 'sentence') return ''
      const whole = collapsed(props.sentence)
      if (whole && whole === front) return cachedTranslation(props.sentence, props.language) || ''
      return ''
    }

    function openMenu(x: number, y: number, raw: string, fromTouch: boolean) {
      const kind = selectionKind(raw, props.language)
      const front = cleanFront(raw, kind)
      if (!front) return
      menu.value = { kind, front }
      place(x, y, fromTouch)
      if (fromTouch) ignoreOutsideUntil = Date.now() + 500
      if (props.language) loadSaved(props.language)
    }

    function onContextMenu(e: MouseEvent) {
      const root = host.value
      if (!root || !root.contains(e.target as Node)) return
      const fromTouch = Date.now() - lastTouchAt < 800
      // 滑动取消了长按：不要拦系统，也不要弹出收藏
      if (fromTouch && cancelledGesture === gesture) return
      if (menu.value) {
        e.preventDefault()
        return
      }
      if (isControl(e.target) && !readSelection(root)) return
      let text = readSelection(root)
      // 桌面必须先划选；手机长按没有选区时，再取手指下的词
      if (!text && fromTouch && !isControl(e.target)) text = selectWordAt(e.clientX, e.clientY, root)
      if (!text) return
      // 只有我们的菜单要出现时才关掉浏览器自带的弹出菜单，普通划选不受影响
      e.preventDefault()
      openMenu(e.clientX, e.clientY, text, fromTouch)
    }

    function clearHold() {
      if (holdTimer) window.clearTimeout(holdTimer)
      holdTimer = 0
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', endHold)
      window.removeEventListener('pointercancel', endHold)
    }

    function endHold() {
      clearHold()
    }

    function onPointerMove(e: PointerEvent) {
      if (!holdTimer) return
      if (Math.hypot(e.clientX - startX, e.clientY - startY) > MOVE_PX) {
        cancelledGesture = gesture
        clearHold()
      }
    }

    function onPointerDown(e: PointerEvent) {
      if (e.pointerType === 'mouse' || isControl(e.target)) return
      lastTouchAt = Date.now()
      gesture += 1
      const id = gesture
      startX = e.clientX
      startY = e.clientY
      clearHold()
      window.addEventListener('pointermove', onPointerMove, { passive: true })
      window.addEventListener('pointerup', endHold)
      window.addEventListener('pointercancel', endHold)
      holdTimer = window.setTimeout(() => {
        holdTimer = 0
        if (!alive || id !== gesture || cancelledGesture === id) return
        const root = host.value
        if (!root) return
        const existing = readSelection(root)
        const text = existing || selectWordAt(startX, startY, root)
        if (!text) return
        openMenu(startX, startY, text, true)
      }, HOLD_MS)
    }

    function onDocPointerDown(e: PointerEvent) {
      if (Date.now() < ignoreOutsideUntil) return
      const t = e.target as Node | null
      if (t && menuEl.value?.contains(t)) return
      closeMenu()
    }

    function onDocKey(e: KeyboardEvent) {
      if (e.key === 'Escape') closeMenu()
    }

    watch(menu, (value, _prev, onCleanup) => {
      if (!value) return
      const timer = window.setTimeout(() => {
        document.addEventListener('pointerdown', onDocPointerDown, true)
        document.addEventListener('keydown', onDocKey)
      }, 0)
      onCleanup(() => {
        window.clearTimeout(timer)
        document.removeEventListener('pointerdown', onDocPointerDown, true)
        document.removeEventListener('keydown', onDocKey)
      })
    })

    async function save() {
      const current = menu.value
      if (!current || already.value || busy.value) return
      busy.value = true
      const kind = current.kind
      const front = current.front
      try {
        const result = await saveCard({
          language: props.language,
          kind,
          front,
          meaning: meaningFor(kind, front),
          example: exampleFor(kind, front, props.sentence),
          sourceSession: sessionId || '',
        })
        if (!alive) return
        if (result.created) showNote(kind === 'sentence' ? '已加入错句本' : '已加入生词本')
        else showNote('已在收藏里')
        closeMenu()
      } catch (e: unknown) {
        if (!alive) return
        const msg = e instanceof Error ? e.message : '收藏失败'
        showNote(msg || '收藏失败', true)
        closeMenu()
      } finally {
        busy.value = false
      }
    }

    return { fallthrough: attrs, host, menuEl, menu, pos, busy, note, noteErr, already, onContextMenu, onPointerDown, save }
  },
})
</script>
