// localStorage that never throws (private mode, blocked storage, previews).
export function load<T extends object>(key: string, fallback: T): T {
  try {
    return { ...fallback, ...JSON.parse(localStorage.getItem(key) || '{}') }
  } catch {
    return { ...fallback }
  }
}

export function save(key: string, value: unknown) {
  try {
    localStorage.setItem(key, typeof value === 'string' ? value : JSON.stringify(value))
  } catch { /* ignore */ }
}

export function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}
