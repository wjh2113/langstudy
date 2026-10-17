// On-demand translations: practice material comes without them, so a sentence is
// translated only when the learner asks. Requests made in the same tick are batched
// into one call, and results are cached for the page's lifetime (and server-side).
import { shallowReactive } from 'vue'
import { api } from '../api'

const cache = shallowReactive(new Map<string, string>())
const pending = new Map<string, Promise<string>>()
let queue: { key: string; text: string; language: string; resolve: (s: string) => void; reject: (e: unknown) => void }[] = []
let timer: ReturnType<typeof setTimeout> | null = null

const keyOf = (text: string, language: string) => `${language}|${text}`

export const cachedTranslation = (text: string, language: string) => cache.get(keyOf(text, language))

async function flush() {
  timer = null
  const batch = queue
  queue = []
  const byLang = new Map<string, typeof batch>()
  for (const item of batch) byLang.set(item.language, [...(byLang.get(item.language) || []), item])
  for (const [language, items] of byLang) {
    for (let i = 0; i < items.length; i += 40) {
      const chunk = items.slice(i, i + 40)
      try {
        const { translations } = await api.translate(chunk.map((c) => c.text), language)
        chunk.forEach((c, k) => {
          cache.set(c.key, translations[k] || '')
          pending.delete(c.key)
          c.resolve(translations[k] || '')
        })
      } catch (e) {
        chunk.forEach((c) => { pending.delete(c.key); c.reject(e) })
      }
    }
  }
}

export function translate(text: string, language: string): Promise<string> {
  const key = keyOf(text, language)
  if (cache.has(key)) return Promise.resolve(cache.get(key) as string)
  if (pending.has(key)) return pending.get(key) as Promise<string>
  const p = new Promise<string>((resolve, reject) => {
    queue.push({ key, text, language, resolve, reject })
    if (!timer) timer = setTimeout(flush, 30)
  })
  pending.set(key, p)
  return p
}
