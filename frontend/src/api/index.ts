// Every backend endpoint the frontend uses, typed.
import { audioForm, post, request, runJob, send } from './client'
import type {
  ChatReplyOut, ChatReplyReq, Credentials, FollowUpReq, GenerateReq, JobRef, LoginOut, MeOut, PreviousOut,
  RegisterReq, SessionOut, SessionSummary, ShareOut, SpokenText, StartedSession, TTSReq, TranslateOut,
  Turn as ApiTurn,
} from './types.gen'
import type { AppConfig, Card, Coach, Content, CoursePack, Notes, PracticeState, Report } from './models'

export { ApiError, runJob } from './client'

export interface TopicItem {
  id: string
  language?: string | null
  level?: string | null
  mode?: string | null
  topic?: string | null
  title?: string | null
  overall?: number | null
  createdAt: string
  updatedAt?: string | null
  done: boolean
  hasNotes: boolean
  answered: number
  attempts: number
}
export interface NotesResponse { notes: Notes | null; generatedAt: string | null }
export interface SharedReport { createdAt: string; content: Content; report: Report; owner: string }
export interface PronounceResult { score: number | null; transcript: string; issues: { quote?: string; note?: string }[]; note: string }

export const api = {
  // accounts
  me: () => request<MeOut>('/auth/me'),
  setup: (body: Credentials) => request<LoginOut>('/auth/setup', post(body)),
  login: (body: Credentials) => request<LoginOut>('/auth/login', post(body)),
  register: (body: RegisterReq) => request<LoginOut>('/auth/register', post(body)),
  checkInvite: (code: string) => request<{ valid: boolean; message: string }>(`/auth/invite/${encodeURIComponent(code)}`),
  logout: () => request('/auth/logout', post()),
  changePassword: (body: { oldPassword: string; newPassword: string }) => request('/auth/password', post(body)),

  // admin
  invites: () => request<any[]>('/admin/invites'),
  createInvite: (body: { maxUses: number; expiresDays: number | null; note: string }) => request('/admin/invites', post(body)),
  revokeInvite: (code: string) => request(`/admin/invites/${encodeURIComponent(code)}`, { method: 'DELETE' }),
  users: () => request<any[]>('/admin/users'),
  updateUser: (id: number, body: { disabled: boolean }) => request(`/admin/users/${id}`, send('PATCH', body)),
  resetPassword: (id: number) => request<{ password: string }>(`/admin/users/${id}/reset-password`, post()),
  usage: (days = 30) => request<any>(`/admin/usage?days=${days}`),
  mistakeStats: () => request<any>('/admin/stats/mistakes'),
  importPrompt: () => request<{ prompt: string }>('/admin/import-prompt'),
  importTopics: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<{ imported: { id: string; topic: string; mode: string; title: string; hasNotes: boolean }[]; errors: string[] }>(
      '/admin/import', { method: 'POST', body: form })
  },

  // practice
  config: () => request<AppConfig>('/config'),
  generate: (body: GenerateReq, onTick?: (s: number) => void) =>
    runJob<StartedSession>(request<JobRef>('/generate', post(body)), onTick),
  courseUpload: (form: FormData, onTick?: (s: number) => void) =>
    runJob<{ id: string; title: string; topic: string }>(request<JobRef>('/courses', { method: 'POST', body: form }), onTick),
  course: (id: string) => request<CoursePack>(`/courses/${id}`),
  previous: (q: { language: string; level: string; mode: string; topic: string }) =>
    request<PreviousOut>('/sessions/previous?' + new URLSearchParams(q)),
  repeat: (id: string) => request<StartedSession>(`/sessions/${id}/repeat`, post()),
  evaluate: (sessionId: string, turns: ApiTurn[], onTick?: (s: number) => void) =>
    runJob<Report>(request<JobRef>('/evaluate', post({ sessionId, turns })), onTick),
  saveProgress: (id: string, turns: ApiTurn[], state: PracticeState, keepalive = false) =>
    request<{ savedAt: string }>(`/sessions/${id}/progress`, { ...send('PUT', { turns, state }), keepalive }),
  followup: (body: FollowUpReq) => request<SpokenText>('/followup', post(body)),
  chatReply: (body: ChatReplyReq) => request<ChatReplyOut>('/chat/reply', post(body)),
  translate: (texts: string[], language: string) => request<TranslateOut>('/translate', post({ texts, language })),
  coach: (language: string) => request<Coach>(`/coach/${language}`),
  tts: (body: TTSReq) => request<Blob>('/tts', post(body)),
  stt: (blob: Blob, language: string) => request<{ text: string }>('/stt', { method: 'POST', body: audioForm(blob, { language }) }),
  /** Pronunciation assessment (billed): from a recording in hand, or one saved with the session. */
  pronounce: (src: { blob?: Blob | null; sessionId?: string; audioName?: string }, text: string, language: string) =>
    request<PronounceResult>('/pronounce', {
      method: 'POST',
      body: audioForm(src.blob || null, { text, language, sessionId: src.sessionId || '', audioName: src.audioName || '' }),
    }),

  // sessions
  sessions: (all = false) => request<SessionSummary[]>(`/sessions${all ? '?all=true' : ''}`),
  topics: () => request<TopicItem[]>('/topics'),
  session: (id: string) => request<SessionOut>(`/sessions/${id}`),
  deleteSession: (id: string) => request(`/sessions/${id}`, { method: 'DELETE' }),
  progress: (language: string) => request<{ createdAt: string; overall: number | null; dims: Record<string, number | null> }[]>(`/progress/${language}`),
  uploadAudio: (sid: string, key: string, blob: Blob) =>
    request<{ url: string }>(`/sessions/${sid}/audio`, { method: 'POST', body: audioForm(blob, { key }) }),
  share: (id: string) => request<ShareOut>(`/sessions/${id}/share`, post()),
  unshare: (id: string) => request<ShareOut>(`/sessions/${id}/share`, { method: 'DELETE' }),
  shared: (token: string) => request<SharedReport>(`/share/${encodeURIComponent(token)}`),

  // study notes
  notesList: () => request<any[]>('/notes'),
  notes: (id: string) => request<NotesResponse>(`/sessions/${id}/notes`),
  generateNotes: (id: string, onTick?: (s: number) => void) =>
    runJob<NotesResponse>(request<JobRef>(`/sessions/${id}/notes`, post()), onTick),

  // review cards
  cards: ({ language, kind, due }: { language?: string; kind?: string; due?: boolean } = {}) =>
    request<Card[]>('/cards?' + new URLSearchParams(
      Object.entries({ language, kind, due: due ? 'true' : undefined }).filter((e): e is [string, string] => Boolean(e[1])),
    )),
  cardsSummary: () => request<Record<string, { due: number; total: number }>>('/cards/summary'),
  addCard: (body: Partial<Card> & { language: string; kind: string; front: string }) =>
    request<{ card: Card; created: boolean }>('/cards', post(body)),
  reviewCard: (id: number, grade: string) => request(`/cards/${id}/review`, post({ grade })),
  deleteCard: (id: number) => request(`/cards/${id}`, { method: 'DELETE' }),
}

export type { SessionOut, SessionSummary }
