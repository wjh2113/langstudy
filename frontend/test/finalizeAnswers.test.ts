import assert from 'node:assert/strict'
import { mock } from 'node:test'
import { reactive } from 'vue'
import { finalizeAnswers } from '../src/lib/finalizeAnswers.ts'

mock.timers.enable({ apis: ['setTimeout'] })
try {
  const turns = [{ answer: 'browser draft' }]
  const pending = new Promise<void>((resolve) => setTimeout(() => {
    turns[0].answer = 'server transcript'
    resolve()
  }, 20000))
  let finished = false
  const grading = finalizeAnswers([pending], () => turns).then((snapshot) => {
    finished = true
    return snapshot
  })
  mock.timers.tick(15000)
  await Promise.resolve()
  assert.equal(finished, false, 'must not grade a draft at 15 seconds')
  mock.timers.tick(5000)
  const snapshot = await grading
  assert.equal(snapshot[0].answer, 'server transcript')
  turns[0].answer = 'later edit'
  assert.equal(snapshot[0].answer, 'server transcript', 'report input must be immutable')
  const reactiveTurns = reactive([{ answer: 'voice', pron: { score: 88 } }])
  const voiceSnapshot = await finalizeAnswers([], () => reactiveTurns)
  reactiveTurns[0].pron.score = 50
  assert.equal(voiceSnapshot[0].pron.score, 88, 'Vue pronunciation proxies must serialize safely')
  const fallback = await finalizeAnswers([Promise.reject(new Error('STT failed'))], () => turns)
  assert.equal(fallback[0].answer, 'later edit', 'failed recognition must retain the browser result')
} finally {
  mock.timers.reset()
}
console.log('ok finalizeAnswers: slow STT, immutable snapshot, failed STT fallback')
