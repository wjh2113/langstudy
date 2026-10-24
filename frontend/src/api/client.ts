// Fetch wrapper: JSON in/out, readable errors, 401 -> back to login, background jobs.
import type { Job, JobRef } from './types.gen'

const BASE = '/api'

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message)
  }
}

export async function request<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  let res: Response
  try {
    res = await fetch(BASE + path, { credentials: 'same-origin', ...options })
  } catch (e: any) {
    if (e?.name === 'AbortError') throw e
    throw new ApiError('连不上后端服务，请确认 backend 已启动（端口 8000）', 0)
  }
  if (!res.ok) {
    let msg = `请求失败（${res.status}）`
    try {
      const data = await res.json()
      if (data.detail) msg = typeof data.detail === 'string' ? data.detail : '提交的内容格式不对'
    } catch { /* not json */ }
    // session expired or account disabled: let the app show the login screen
    if (res.status === 401 && !path.startsWith('/auth/') && !path.startsWith('/share/')) {
      window.dispatchEvent(new Event('ls:unauthorized'))
    }
    throw new ApiError(msg, res.status)
  }
  const type = res.headers.get('content-type') || ''
  return (type.includes('application/json') ? res.json() : res.blob()) as Promise<T>
}

export const send = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body),
})
export const post = (body?: unknown) => send('POST', body ?? {})

export function audioForm(blob: Blob | null, fields: Record<string, string>): FormData {
  const form = new FormData()
  if (blob) {
    const ext = blob.type.includes('mp4') ? 'mp4' : blob.type.includes('ogg') ? 'ogg' : 'webm'
    form.append('audio', blob, `speech.${ext}`)
  }
  for (const [k, v] of Object.entries(fields)) form.append(k, v)
  return form
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/**
 * Slow work (generate / evaluate / notes) runs as a background job on the server:
 * start it, then poll until it is done. `onTick` gets the seconds waited so far.
 */
export async function runJob<T>(start: Promise<JobRef>, onTick?: (seconds: number) => void, maxSeconds = 300): Promise<T> {
  const { jobId } = await start
  const began = Date.now()
  let delay = 700
  for (;;) {
    await sleep(delay)
    delay = Math.min(2000, delay + 300)
    const job = await request<Job>(`/jobs/${jobId}`)
    onTick?.(Math.round((Date.now() - began) / 1000))
    if (job.status === 'done') return job.result as T
    if (job.status === 'error') throw new ApiError(job.error || '处理失败，请重试', 502)
    if (Date.now() - began > maxSeconds * 1000) throw new ApiError('等待太久了，请稍后在历史记录里查看', 504)
  }
}
