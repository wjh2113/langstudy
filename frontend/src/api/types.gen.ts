// Generated from the backend's OpenAPI document by backend/scripts/gen_types.py.
// Do not edit by hand: change backend/app/schemas.py and re-run the script.
/* eslint-disable */

export interface CardReq {
  language: string
  kind?: "word" | "pattern" | "sentence"
  front: string
  reading?: string
  meaning?: string
  example?: string
  exampleTranslation?: string
  extra?: string
  sourceSession?: string
}

export interface ChatReplyOut {
  text: string
  translation?: string
  end?: boolean
  summary?: string
}

export interface ChatReplyReq {
  sessionId: string
  history?: ChatTurn[]
  summary?: string
}

export interface ChatTurn {
  role: "ai" | "user"
  text: string
}

export interface Credentials {
  username: string
  password: string
}

export interface EvaluateReq {
  sessionId: string
  turns?: Turn[]
}

export interface FollowUpReq {
  sessionId: string
  question: string
  answer: string
  history?: QA[]
}

export interface GenerateReq {
  language?: string
  level?: string
  mode?: string
  topic?: string
  count?: number
  focus?: string
}

export interface InviteReq {
  maxUses?: number
  expiresDays?: number | null
  note?: string
}

export interface Job {
  id: string
  kind: "generate" | "evaluate" | "notes"
  status: "pending" | "running" | "done" | "error"
  result?: unknown | null
  error?: string | null
}

export interface JobRef {
  jobId: string
}

export interface LoginOut {
  user: User
}

export interface MeOut {
  user?: User | null
  setupRequired?: boolean
}

export interface PasswordReq {
  oldPassword: string
  newPassword: string
}

export interface PreviousOut {
  previous?: PreviousSession | null
}

export interface PreviousSession {
  id: string
  createdAt: string
  title?: string | null
  overall?: number | null
  done: boolean
}

export interface ProgressReq {
  turns?: Turn[]
  state?: Record<string, unknown> | null
}

export interface QA {
  q?: string
  a?: string
}

export interface RegisterReq {
  username: string
  password: string
  inviteCode: string
}

export interface ReviewReq {
  grade: "again" | "hard" | "good" | "easy"
}

export interface SessionOut {
  id: string
  createdAt: string
  content: Record<string, unknown>
  turns?: Record<string, unknown>[]
  state?: Record<string, unknown> | null
  report?: Record<string, unknown> | null
  shareToken?: string | null
}

export interface SessionSummary {
  id: string
  language?: string | null
  level?: string | null
  mode?: string | null
  topic?: string | null
  title?: string | null
  overall?: number | null
  username?: string | null
  createdAt: string
  updatedAt?: string | null
  done: boolean
  hasNotes: boolean
  answered?: number
}

export interface ShareOut {
  token?: string | null
  url?: string | null
}

export interface SpokenText {
  text: string
  translation?: string
}

export interface StartedSession {
  id: string
  content: Record<string, unknown>
}

export interface TTSReq {
  text: string
  language?: string
  voiceIndex?: number
  rate?: number
  accent?: string
}

export interface TranslateOut {
  translations: string[]
}

export interface TranslateReq {
  texts?: string[]
  language?: string
}

/** One answer in a practice. Saved as you go (PUT /api/sessions/{id}/progress) and graded at the end. */
export interface Turn {
  id?: string
  kind?: string
  prompt?: string
  reference?: string
  freeResponse?: boolean
  answer?: string
  input?: "voice" | "text"
  durationSec?: number
  confidence?: number | null
  plays?: number
  textHidden?: boolean
  followUp?: boolean
  audioUrl?: string
  shadowSync?: boolean
  lagSec?: number | null
  durationRatio?: number | null
  pronScore?: number | null
  pronNote?: string
  pronIssues?: Record<string, unknown>[]
  voiceStartAt?: number | null
}

export interface User {
  id: number
  username: string
  role: "admin" | "user"
  disabled?: boolean
  createdAt?: string | null
  lastLoginAt?: string | null
}

export interface UserPatch {
  disabled?: boolean | null
}
