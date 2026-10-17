// Shared plumbing for the practice modes: per-mode resumable state and turn serialisation.
import { inject, type InjectionKey } from 'vue'
import type { Turn as ApiTurn } from '../api/types.gen'
import type { PracticeState, Turn } from '../api/models'
import { diffReference } from './diff'

export const PRACTICE_STATE: InjectionKey<PracticeState> = Symbol('practiceState')
export const SESSION_ID: InjectionKey<string> = Symbol('sessionId')

/**
 * This mode's slice of the practice state. It is reactive and autosaved with the
 * session, so whatever a mode keeps here survives a refresh or a closed tab.
 */
export function useModeState<T extends object>(key: string, defaults: T): T {
  const state = inject(PRACTICE_STATE) as PracticeState
  if (!state[key]) state[key] = { ...defaults }
  else for (const [k, v] of Object.entries(defaults)) if (!(k in state[key])) state[key][k] = v
  return state[key] as T
}

/** Blind-listening reveals, shared by all modes (and saved). */
export function useRevealed(): Record<string, boolean> {
  const state = inject(PRACTICE_STATE) as PracticeState
  if (!state.revealed) state.revealed = {}
  return state.revealed
}

/** The turn as the API stores it: no blobs, no local blob: URLs, no derived display data. */
export function toApiTurn(t: Turn): ApiTurn {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { audioBlob, diff, pronPending, ...rest } = t
  return { ...rest, audioUrl: String(t.audioUrl || '').startsWith('/api/') ? t.audioUrl : '' }
}

/** Turns loaded from the server get their (not stored) diff back. */
export function hydrateTurn(t: ApiTurn, language: string): Turn {
  const turn = { ...t, id: t.id || '' } as Turn
  if (turn.reference && turn.answer && !turn.freeResponse && (turn.kind === 'shadow' || turn.kind === 'line')) {
    turn.diff = diffReference(turn.reference, turn.answer, language)
  }
  return turn
}
