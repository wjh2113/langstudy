import assert from 'node:assert/strict'
import { splitSentences } from '../src/lib/speechText.ts'

const q = "Let's start with a simple introduction. Could you tell me a little about yourself and what brings you here today?"
const parts = splitSentences(q)
assert.deepEqual(parts, [
  "Let's start with a simple introduction.",
  'Could you tell me a little about yourself and what brings you here today?',
])

assert.deepEqual(splitSentences('Hello there.'), ['Hello there.'])
assert.deepEqual(splitSentences('3.14 is pi. Next comes more.'), ['3.14 is pi. Next comes more.'])
const decimal = '3.14 is the start of a longer explanation about numbers. Next comes the part about how to say it aloud in a full sentence.'
assert.deepEqual(splitSentences(decimal), [
  '3.14 is the start of a longer explanation about numbers.',
  'Next comes the part about how to say it aloud in a full sentence.',
])
const titled = 'Mr. Smith is here today to talk about the account. Hello there, thanks for coming in this afternoon.'
assert.equal(splitSentences(titled)[0].startsWith('Mr. Smith'), true)
assert.equal(splitSentences('你好。我们开始吧。').length, 1)

const long = 'I worked on support tickets, talked to customers every day, and learned how to stay calm when someone is upset about a late delivery'
const cut = splitSentences(long)
assert.ok(cut.length >= 2, cut.join(' | '))
assert.ok(cut[0].length <= 60, cut[0])
assert.ok(cut[0].endsWith(','), cut[0])

const chat = "Hey! I didn't expect to see you with someone tonight. Is this your partner?"
const chatParts = splitSentences(chat)
assert.ok(chatParts.length >= 2, chatParts.join(' | '))
assert.ok(chatParts[0].length <= 60, chatParts[0])

console.log('ok splitSentences')
