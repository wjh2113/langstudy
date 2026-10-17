// Hands a freshly graded session to the report page without fetching it again.
import type { SessionOut } from '../api'

const cache = new Map<string, SessionOut>()

export function cacheReport(id: string, session: SessionOut) {
  cache.set(id, session)
}

export function takeReport(id: string): SessionOut | undefined {
  const s = cache.get(id)
  cache.delete(id)
  return s
}
