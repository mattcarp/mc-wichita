// Pure display policy. No capture, inference, or external actions.
export function numberOrNull(value) {
  if (!['number', 'string'].includes(typeof value) || (typeof value === 'string' && value.trim() === '')) return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

export function normalizeRecord(record, kind = 'alert') {
  const metadata = record.metadata && typeof record.metadata === 'object' ? record.metadata : {}
  const mhz = numberOrNull(record.frequency_mhz)
  const hz = numberOrNull(record.frequency_hz)
  return {
    ...record, kind, metadata,
    title: record.title || record.channel || record.signal_type || 'RF capture',
    frequency_mhz: mhz ?? (hz === null ? null : hz / 1000000),
    average_power_dbfs: numberOrNull(record.average_power_dbfs),
    voice_score: numberOrNull(record.voice_score ?? metadata.voice_score),
    voice_ratio: numberOrNull(record.voice_ratio ?? metadata.voice_ratio),
    confidence: numberOrNull(record.confidence),
    source: record.source || metadata.source || null,
    language: record.language || null,
    observed_at: metadata.observed_at || null,
  }
}

export function newFeed() {
  return { data: null, fetchedAt: null, error: null, retryAt: 0, failures: 0 }
}

export function resolveFeed(previous, result, now) {
  if (result.status === 'fulfilled') {
    return { data: result.value, fetchedAt: now, error: null, retryAt: 0, failures: 0 }
  }
  const error = result.reason || {}
  const failures = previous.failures + 1
  const status = error.status
  const delay = status === 401 || status === 403 ? 300000
    : status === 429 ? Math.max(60000, error.retryAfterMs || 0)
    : Math.min(120000, 10000 * 2 ** Math.min(failures - 1, 4))
  const message = status === 401 || status === 403 ? 'Access denied. Check service credentials.'
    : status === 429 ? 'Service rate limited. Waiting before retry.'
    : 'Service unavailable. Last successful result retained.'
  return { ...previous, error: message, failures, retryAt: now + delay }
}

export function feedState(feed, now, paused = false) {
  if (feed.fetchedAt === null) return feed.error ? 'Unavailable' : 'Loading'
  if (feed.error || now - feed.fetchedAt > 30000) return 'Stale'
  if (paused) return 'Paused'
  if (Array.isArray(feed.data) && !feed.data.length) return 'Empty'
  return 'Available'
}

export function positionOf(record) {
  const m = record.metadata || {}
  const location = m.event_location || {}
  const lat = typeof location.latitude === 'number' ? numberOrNull(location.latitude) : null
  const lon = typeof location.longitude === 'number' ? numberOrNull(location.longitude) : null
  if (lat === null || lon === null || Math.abs(lat) > 90 || Math.abs(lon) > 180) return null
  return { lat, lon, source: location.source || 'Record metadata; not independently verified' }
}

export function safeAudioUrl(value, origin) {
  if (!value || typeof value !== 'string') return null
  try {
    const url = new URL(value, origin)
    if (url.origin !== origin || !url.pathname.startsWith('/api/audio/') || url.search || url.hash) return null
    const filename = decodeURIComponent(url.pathname.slice('/api/audio/'.length))
    if (!filename || /[/\\]/.test(filename) || filename === '.' || filename === '..') return null
    return url.href
  } catch { return null }
}

export const questions = [
  ['why', 'Why was this flagged?'], ['missing', 'What evidence is missing?'],
  ['source', 'Where did this come from?'], ['language', 'What language is recorded?'],
  ['time', 'When did this happen?'], ['location', 'Can we locate it?'],
]

export function localAnswer(record, question) {
  const m = record.metadata || {}
  const missing = [!record.transcript && 'transcript', !record.audio_url && 'audio reference',
    !record.language && 'language', !record.source && 'source', !record.observed_at && 'observation time',
    !positionOf(record) && 'location'].filter(Boolean)
  const answers = {
    why: m.trigger ? `Recorded trigger: ${String(m.trigger)}. This has not been independently validated.`
      : 'No explicit trigger is recorded. A title or severity alone does not establish distress.',
    missing: missing.length ? `Not recorded: ${missing.join(', ')}.` : 'The basic evidence fields are present. Their presence does not verify their accuracy.',
    source: record.source ? `Recorded source: ${record.source}.` : 'No source is recorded.',
    language: record.language ? `Recorded language: ${record.language}. Original transcript is preserved without translation.` : 'No language is recorded. No language has been inferred.',
    time: record.observed_at ? `Recorded observation time: ${record.observed_at}.` : `Observation time is unknown. Record creation time: ${record.created_at || 'unknown'}.`,
    location: positionOf(record) ? 'Coordinates are present in the record. They do not identify a speaker or prove a vessel association.' : 'This event is unlocated. The Malta overview is not its position.',
  }
  return answers[question] || 'Choose one of the supported evidence questions.'
}
