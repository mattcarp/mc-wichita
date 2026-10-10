import test from 'node:test'
import assert from 'node:assert/strict'
import { numberOrNull, normalizeRecord, resolveFeed, newFeed, feedState, positionOf, safeAudioUrl, localAnswer } from './evidence-model.mjs'

test('empty live response stays empty and zero measurements survive', () => {
  const feed = resolveFeed(newFeed(), { status: 'fulfilled', value: [] }, 1000)
  assert.deepEqual(feed.data, [])
  assert.equal(feedState(feed, 1001), 'Empty')
  const row = normalizeRecord({ average_power_dbfs: 0, voice_score: 0, voice_ratio: 0 })
  assert.equal(row.average_power_dbfs, 0)
  assert.equal(row.voice_score, 0)
  assert.equal(row.voice_ratio, 0)
  assert.equal(normalizeRecord({}).average_power_dbfs, null)
})

test('failed poll preserves last observation and successful-fetch time', () => {
  const first = resolveFeed(newFeed(), { status: 'fulfilled', value: [{ id: 'original' }] }, 1000)
  const failed = resolveFeed(first, { status: 'rejected', reason: new Error('offline') }, 5000)
  assert.equal(failed.fetchedAt, 1000)
  assert.deepEqual(failed.data, first.data)
  assert.equal(feedState(failed, 5001), 'Stale')
  assert.equal(failed.retryAt, 15000)
  assert.equal(resolveFeed(failed, { status: 'fulfilled', value: [] }, 16000).error, null)
})

test('credentials and quota failures avoid rapid retries', () => {
  assert.equal(resolveFeed(newFeed(), { status: 'rejected', reason: { status: 401 } }, 1000).retryAt, 301000)
  assert.equal(resolveFeed(newFeed(), { status: 'rejected', reason: { status: 429, retryAfterMs: 90000 } }, 1000).retryAt, 91000)
})

test('evidence identity and multilingual content are preserved without inference', () => {
  for (const [language, transcript] of [['mt', 'Għajnuna'], ['ar', 'مساعدة'], ['it', 'Aiuto'], ['en', 'Help']]) {
    const record = normalizeRecord({ id: 'event', language, transcript, audio_url: '/api/audio/local.wav', metadata: { trigger: 'recorded trigger' } })
    assert.equal(record.language, language)
    assert.equal(record.transcript, transcript)
    assert.equal(record.id, 'event')
    assert.equal(record.audio_url, '/api/audio/local.wav')
    assert.match(localAnswer(record, 'why'), /Recorded trigger/)
  }
})

test('missing or invalid coordinates never become Malta or zero by default', () => {
  assert.equal(positionOf({}), null)
  assert.equal(positionOf({ metadata: { event_location: { latitude: null, longitude: null } } }), null)
  assert.equal(positionOf({ metadata: { event_location: { latitude: 91, longitude: 181 } } }), null)
  assert.equal(positionOf({ metadata: { event_location: { latitude: 0, longitude: 0 } } }).lat, 0)
})

test('audio stays on the same-origin approved route', () => {
  const origin = 'http://localhost:3000'
  assert.equal(safeAudioUrl('/api/audio/local.wav', origin), origin + '/api/audio/local.wav')
  for (const url of ['https://other.test/api/audio/a.wav', 'javascript:alert(1)', '/api/audio/%2e%2e%2fsecret', '/api/audio/../../../secret', '/api/audio/a.wav?token=secret']) {
    assert.equal(safeAudioUrl(url, origin), null)
  }
})


test('blank and non-scalar measurements remain unknown', () => {
  for (const value of ['  ', [], {}, true, null, undefined, 'NaN']) assert.equal(numberOrNull(value), null)
  assert.equal(numberOrNull('0'), 0)
})
