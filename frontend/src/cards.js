// Which words / patterns / sentences the learner has saved, so star buttons show the right state.
import { reactive, ref } from 'vue'
import { api } from './api'

const saved = reactive(new Set()) // "lang|kind|front"
const loaded = new Set()
export const dueCount = ref(0)

const key = (language, kind, front) => `${language}|${kind}|${(front || '').trim()}`

export async function loadSaved(language) {
  if (loaded.has(language)) return
  loaded.add(language)
  try {
    for (const c of await api.cards({ language })) saved.add(key(c.language, c.kind, c.front))
  } catch {
    loaded.delete(language)
  }
}

export const isSaved = (language, kind, front) => saved.has(key(language, kind, front))

export async function saveCard(card) {
  const r = await api.addCard(card)
  saved.add(key(card.language, card.kind, card.front))
  if (r.created) dueCount.value++
  return r
}

/** Re-read saved cards for a language next time (e.g. the server added mistake sentences). */
export function invalidate(language) {
  loaded.delete(language)
}

export function forget(language, kind, front) {
  saved.delete(key(language, kind, front))
}

export async function refreshDue() {
  try {
    const s = await api.cardsSummary()
    dueCount.value = Object.values(s).reduce((n, l) => n + (l.due || 0), 0)
    return s
  } catch {
    return null
  }
}

export function resetCards() {
  saved.clear()
  loaded.clear()
  dueCount.value = 0
}
