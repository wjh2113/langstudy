const BASE = '/api'

async function request(path, options = {}) {
  let res
  try {
    res = await fetch(BASE + path, { credentials: 'same-origin', ...options })
  } catch {
    throw new Error('连不上后端服务，请确认 backend 已启动（端口 8000）')
  }
  if (!res.ok) {
    let msg = `请求失败（${res.status}）`
    try {
      const data = await res.json()
      if (data.detail) msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch { /* not json */ }
    // session expired or account disabled: let the app show the login screen
    if (res.status === 401 && !path.startsWith('/auth/')) window.dispatchEvent(new Event('ls:unauthorized'))
    const err = new Error(msg)
    err.status = res.status
    throw err
  }
  const type = res.headers.get('content-type') || ''
  return type.includes('application/json') ? res.json() : res.blob()
}

const send = (method, body) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body),
})
const json = (body) => send('POST', body)

function audioForm(blob, fields) {
  const form = new FormData()
  const ext = blob.type.includes('mp4') ? 'mp4' : blob.type.includes('ogg') ? 'ogg' : 'webm'
  form.append('audio', blob, `speech.${ext}`)
  for (const [k, v] of Object.entries(fields)) form.append(k, v)
  return form
}

export const api = {
  // accounts
  me: () => request('/auth/me'),
  setup: (body) => request('/auth/setup', json(body)),
  login: (body) => request('/auth/login', json(body)),
  register: (body) => request('/auth/register', json(body)),
  checkInvite: (code) => request(`/auth/invite/${encodeURIComponent(code)}`),
  logout: () => request('/auth/logout', json({})),
  changePassword: (body) => request('/auth/password', json(body)),

  // admin
  invites: () => request('/admin/invites'),
  createInvite: (body) => request('/admin/invites', json(body)),
  revokeInvite: (code) => request(`/admin/invites/${encodeURIComponent(code)}`, { method: 'DELETE' }),
  users: () => request('/admin/users'),
  updateUser: (id, body) => request(`/admin/users/${id}`, send('PATCH', body)),
  resetPassword: (id) => request(`/admin/users/${id}/reset-password`, json({})),

  // practice
  config: () => request('/config'),
  generate: (body) => request('/generate', json(body)),
  tts: (body) => request('/tts', json(body)),
  stt: (blob, language) => request('/stt', { method: 'POST', body: audioForm(blob, { language }) }),
  pronounce: (blob, text, language) => request('/pronounce', { method: 'POST', body: audioForm(blob, { text, language }) }),
  followup: (body) => request('/followup', json(body)),
  evaluate: (body) => request('/evaluate', json(body)),
  sessions: (all = false) => request(`/sessions${all ? '?all=true' : ''}`),
  session: (id) => request(`/sessions/${id}`),
  deleteSession: (id) => request(`/sessions/${id}`, { method: 'DELETE' }),
  progress: (language) => request(`/progress/${language}`),
}
