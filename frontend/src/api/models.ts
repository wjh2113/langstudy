// Shapes of data the backend sends as free-form JSON (practice material, reports, ...).
// Request/response envelopes come from types.gen.ts, generated from the backend's OpenAPI.
import type { Turn as ApiTurn } from './types.gen'

export type Lang = 'en' | 'ja'
export type Mode = 'questions' | 'dialogue' | 'article' | 'chat' | 'dictation'
export type Level = 'beginner' | 'intermediate' | 'advanced'

export interface Sentence { text: string; translation?: string; blanks?: string[] }
export interface Question { text: string; translation?: string; tip?: string; answerHint?: string }
export interface Role { id: string; name: string; description?: string }
export interface Line { role: string; text: string; translation?: string }

export interface Content {
  mode: Mode
  language: Lang
  level: Level
  topic: string
  title: string
  focus?: { key: string; name: string }
  notesLocked?: boolean
  intro?: string
  scene?: string
  goal?: string
  sentences?: Sentence[]
  questions?: Question[]
  roles?: Role[]
  lines?: Line[]
  aiRole?: Role
  userRole?: Role
  opening?: string
}

export interface DiffToken { t: string; ok: boolean }
export interface Diff { tokens: DiffToken[]; similarity: number }

/** A turn as the practice UI holds it: the API turn plus browser-only fields. */
export interface Turn extends ApiTurn {
  id: string
  audioBlob?: Blob | null
  diff?: Diff | null
  pronPending?: boolean
}

export interface Dimension { key: string; name: string; desc: string; score: number | null; comment: string }
export interface ReportItem {
  key?: string
  kind: string
  followUp?: boolean
  prompt: string
  reference: string
  answer: string
  input: string
  ok?: boolean
  correct?: boolean
  corrected: string
  better: string
  notes: string
  metrics: { rate?: number; fillers?: number; similarity?: number; pron?: number; lagSec?: number; durationRatio?: number }
  audioUrl?: string
  pronNote?: string
  pronIssues?: { quote?: string; note?: string }[]
  diff?: DiffToken[]
}
export interface VocabItem { word: string; reading?: string; meaning?: string; example?: string }
export interface Report {
  overall: number | null
  dimensions: Dimension[]
  summary: string
  strengths: string[]
  improvements: string[]
  items: ReportItem[]
  vocabulary: VocabItem[]
  stats: {
    turns: number; voiceTurns: number; avgRate: number | null; rateUnit: string; rateRange: number[]
    fillers: number; pronSource: string | null; dictationAccuracy: number | null
  }
  demo?: boolean
  cardsAdded?: number
}

export interface Accent { key: string; label: string; group: string; locale: string; simulated: boolean }
export interface LanguageMeta {
  code: Lang
  name: string
  sttLocale: string
  levels: { key: Level; label: string }[]
  accents: Accent[]
}
export interface AppConfig {
  languages: LanguageMeta[]
  demoMode: boolean
  model: string | null
  sttServer: boolean
  ttsServer: boolean
  pronounceServer: boolean
}

/** Everything a component needs to know about the target language and listening settings. */
export interface Env {
  language: Lang
  locale: string
  rate: number
  voice: 'female' | 'male'
  voiceIndex: number
  hideText: boolean
  showTranslation: boolean
  handsFree: boolean
  accents: Accent[]
  accent: string
  accentLocale: string | null
  serverSTT: boolean
  recognitionSupported: boolean
  pronounceServer: boolean
  textClass: string
}

export interface CourseItem {
  key: string
  kind: 'questions' | 'notes' | 'dictation' | 'chat' | 'dialogue' | 'listening' | 'introduce'
  title: string
  blurb: string
  sessionId: string
}

export interface CoursePack {
  id: string
  title: string
  topic: string
  language: Lang
  sourceName: string
  createdAt: string
  items: CourseItem[]
}

export interface Notes {
  summary: string
  vocabulary: { word: string; reading: string; pos: string; meaning: string; example: string; exampleTranslation: string }[]
  grammar: { point: string; explanation: string; examples: { text: string; translation: string }[]; pitfall: string }[]
  patterns: { pattern: string; usage: string; examples: { text: string; translation: string }[] }[]
}

export interface Card {
  id: number; language: Lang; kind: 'word' | 'pattern' | 'sentence'; front: string; reading: string; meaning: string
  example: string; exampleTranslation: string; extra: string; sourceSession: string | null; dueAt: string; reps: number
}

export interface Coach {
  level?: string; change?: boolean; reason?: string
  weakest?: { key: string; name: string; score: number }
}

/** Per-mode UI state, autosaved with the session so a refresh resumes where you were. */
export interface PracticeState {
  plays?: Record<string, number>
  revealed?: Record<string, boolean>
  [mode: string]: any
}
