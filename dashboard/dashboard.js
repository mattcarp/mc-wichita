import { normalizeRecord, newFeed, resolveFeed, feedState, numberOrNull, positionOf, safeAudioUrl, questions, localAnswer } from './evidence-model.mjs'

const $ = id => document.getElementById(id)
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]))
const endpoints = { delivery: '/delivery-health', captures: '/captures?limit=80', alerts: '/alerts?limit=40' }
const feeds = Object.fromEntries(Object.keys(endpoints).map(key => [key, newFeed()]))
let mode = 'live'
let selected = null
let context = null
let selectionEpoch = 0
let questionEpoch = 0
let refreshing = false
let records = []
let map = null
let point = null
let grid = null
let tiles = null

// Existing dashboard samples, retained only behind explicit sample selection.
// Provenance is unverified; SIM references are not real reception evidence.
const samples = [
  { id: 'sample-d1', title: 'CH09 · Calling channel', created_at: '2026-03-07T03:32:08Z', frequency_mhz: 156.45, average_power_dbfs: -26.8, voice_score: .398, voice_ratio: .957, source: 'Historical dashboard sample', metadata: { evidence: 'rf_captures/autonomous_hunt_20260307_033208/hunt_log.txt', provenance: 'unverified' } },
  { id: 'sample-d3', title: 'CH71 · Ship movement', created_at: '2026-03-07T03:26:51Z', frequency_mhz: 156.575, average_power_dbfs: -30.4, voice_score: .391, voice_ratio: .94, source: 'Historical dashboard sample', metadata: { evidence: 'rf_captures/autonomous_hunt_20260307_031716/SIM_CH71_(Ship_Movement)_20260307_032651_continued_03.metadata.json', provenance: 'SIM-labelled reference; not validated reception' } },
  { id: 'sample-d4', title: 'CH13 · Bridge-to-bridge', created_at: '2026-03-07T03:10:43Z', frequency_mhz: 156.65, average_power_dbfs: -27.4, voice_score: .39, voice_ratio: .936, source: 'Historical dashboard sample', metadata: { evidence: 'rf_captures/autonomous_hunt_20260307_030152/hunt_log.txt', provenance: 'unverified' } },
  { id: 'sample-d5', title: 'Malta Approach', created_at: '2026-03-04T14:12:48Z', frequency_mhz: 119.45, average_power_dbfs: -33.7, voice_score: .268, voice_ratio: .621, source: 'Historical dashboard sample', metadata: { evidence: 'rf_captures/autonomous_hunt_20260304_080508/SIM_Malta_Approach_(119.45)_20260304_141248.metadata.json', provenance: 'SIM-labelled reference; not validated reception' } },
  { id: 'sample-d6', title: '121.5 MHz · Priority watch', created_at: '2026-03-04T14:08:42Z', frequency_mhz: 121.5, average_power_dbfs: -24.2, voice_score: .504, voice_ratio: 1.204, source: 'Historical dashboard sample', metadata: { evidence: 'rf_captures/autonomous_hunt_20260304_080508/SIM_Emergency_(121.5)_20260304_140842_continued_10.metadata.json', provenance: 'SIM-labelled reference; not validated reception' } },
]

function dateText(value) {
  if (!value) return 'Not recorded'
  // Do not reinterpret timezone-less historical timestamps in the browser's timezone.
  if (!/(Z|[+-]\d\d:\d\d)$/i.test(value)) return `${String(value)} · timezone unknown`
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Invalid timestamp' : date.toLocaleString(undefined, { timeZone: 'UTC', hour12: false }) + ' UTC'
}
function ageText(ms) {
  const seconds = Math.max(0, Math.floor(ms / 1000))
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}
function measurement(value, suffix = '', decimals = 2) {
  const number = numberOrNull(value)
  return number === null ? 'Unavailable' : `${number.toFixed(decimals)}${suffix}`
}
function key(record) { return `${record.kind}:${record.id}` }
function selectedFeed() { return selected?.kind === 'alert' ? feeds.alerts : feeds.captures }
function feedNote(name, feed) {
  const state = feedState(feed, Date.now(), !$('autoRefreshToggle').checked)
  const fetched = feed.fetchedAt ? `Last fetch ${ageText(Date.now() - feed.fetchedAt)}.` : 'No successful fetch.'
  const retry = feed.retryAt > Date.now() ? ` Retry in ${Math.ceil((feed.retryAt - Date.now()) / 1000)}s.` : ''
  return `${name}: ${state}. ${fetched}${feed.error ? ` ${feed.error}${retry}` : ''}`
}
async function getJson(path) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 5000)
  try {
    const response = await fetch(path, { signal: controller.signal, headers: { Accept: 'application/json' }, cache: 'no-store' })
    if (!response.ok) {
      const error = new Error('Request failed')
      error.status = response.status
      const raw = response.headers.get('Retry-After')
      error.retryAfterMs = raw ? (/^\d+$/.test(raw) ? Number(raw) * 1000 : Math.max(0, Date.parse(raw) - Date.now())) : 0
      throw error
    }
    return await response.json()
  } finally { clearTimeout(timer) }
}
async function refresh() {
  if (refreshing || mode !== 'live') return
  refreshing = true
  $('refreshNow').disabled = true
  const keys = Object.keys(endpoints).filter(name => feeds[name].retryAt <= Date.now())
  try {
    const results = await Promise.allSettled(keys.map(async name => {
      const data = await getJson(endpoints[name])
      if (name === 'delivery' ? !data || !data.capture || !data.alerts : !Array.isArray(data) || data.some(row => !row || typeof row !== 'object' || typeof row.id !== 'string' || !row.id)) throw new Error('Invalid response shape')
      return data
    }))
    for (let i = 0; i < keys.length; i++) feeds[keys[i]] = resolveFeed(feeds[keys[i]], results[i], Date.now())
    if (mode === 'live') {
      const previous = selected
      collectRecords()
      renderQueue()
      renderHealth()
      if (previous) {
        const current = records.find(record => key(record) === key(previous))
        if (current && JSON.stringify(current) !== JSON.stringify(previous)) selectRecord(current, false)
        else updateSelectionState()
      }
    }
  } finally {
    refreshing = false
    $('refreshNow').disabled = mode !== 'live'
    renderFeedSummary()
  }
}
function collectRecords() {
  records = mode === 'replay' ? samples.map(row => normalizeRecord(row, 'capture'))
    : [...(feeds.alerts.data || []).map(row => normalizeRecord(row, 'alert')), ...(feeds.captures.data || []).map(row => normalizeRecord(row, 'capture'))]
  // API order is newest-first per source. Sort only timestamps with an explicit timezone.
  const time = value => value && /(Z|[+-]\d\d:\d\d)$/i.test(value) ? Date.parse(value) || 0 : 0
  records.sort((a, b) => time(b.observed_at || b.created_at) - time(a.observed_at || a.created_at))
}
function renderQueue() {
  const focusedKey = document.activeElement?.dataset?.event
  const filter = $('eventSearch').value.toLocaleLowerCase()
  const kind = $('eventKind').value
  const rows = records.filter(row => (kind === 'all' || row.kind === kind) && `${row.title} ${row.frequency_mhz ?? ''} ${row.language || ''} ${row.source || ''}`.toLocaleLowerCase().includes(filter))
  $('eventCount').textContent = String(rows.length)
  $('eventList').innerHTML = rows.length ? rows.map(row => `<button type="button" class="event border-border ${selected && key(selected) === key(row) ? 'active' : ''}" data-event="${escape(key(row))}" aria-pressed="${Boolean(selected && key(selected) === key(row))}"><span class="event-head"><span class="event-title">${escape(row.title)}</span><span class="state ${row.severity === 'critical' ? 'warn' : ''}">${escape(mode === 'replay' ? 'Sample' : row.severity || row.kind)}</span></span><span class="event-meta">${escape(measurement(row.frequency_mhz, ' MHz', 3))} · ${escape(row.language || 'Language unknown')}</span><span class="event-time">${row.observed_at ? 'Observed' : 'Record created'} ${escape(dateText(row.observed_at || row.created_at))}</span></button>`).join('')
    : `<div class="empty"><h3>${filter || kind !== 'all' ? 'No matching events' : 'No records to review'}</h3><p>${filter || kind !== 'all' ? 'Try a different filter.' : 'An empty queue does not establish whether the receiver is healthy. Source status is shown above.'}</p></div>`
  if (focusedKey) {
    const button = [...$('eventList').querySelectorAll('[data-event]')].find(item => item.dataset.event === focusedKey)
    button?.focus({ preventScroll: true })
  }
  renderFeedSummary()
}
function renderFeedSummary() {
  if (mode === 'replay') {
    $('overallState').textContent = 'Historical samples'
    $('overallState').className = 'state warn'
    $('updatedAt').textContent = 'March 2026 · unverified provenance · live polling paused'
    $('queueFeedNotes').textContent = 'Explicit sample view. Counts and dates below do not describe the current receiver.'
    return
  }
  const states = Object.values(feeds).map(feed => feedState(feed, Date.now(), !$('autoRefreshToggle').checked))
  const incomplete = states.some(state => ['Unavailable', 'Stale'].includes(state))
  $('overallState').textContent = incomplete ? 'Partial / unavailable' : states.includes('Loading') ? 'Connecting' : $('autoRefreshToggle').checked ? 'Local API' : 'Polling paused'
  $('overallState').className = `state ${incomplete ? 'warn' : 'good'}`
  $('updatedAt').textContent = 'Fetch status is separate from observation time. All times display in UTC when known.'
  $('queueFeedNotes').innerHTML = `<p>${escape(feedNote('Alerts', feeds.alerts))}</p><p>${escape(feedNote('Captures', feeds.captures))}</p>`
  updateSelectionState()
}
function renderHealth() {
  const health = feeds.delivery.data
  const available = !feeds.delivery.error && health
  const cards = mode === 'replay' ? [
    ['Data source', 'Historical samples', 'March 2026. Not current receiver data.'],
    ['Capture delivery', 'Not assessed', 'Sample selection makes no hardware claims.'],
    ['Decoder', 'Not assessed', 'No real AIS association is shown.'],
    ['Analysis', 'Not assessed', 'Sample indicators are not validated distress scores.'],
  ] : [
    ['API service', feedState(feeds.delivery, Date.now(), !$('autoRefreshToggle').checked), feedNote('Health', feeds.delivery)],
    ['Capture delivery', available ? `${health.capture.count} records` : 'Unknown', health?.capture.last_record_at ? `Last record: ${dateText(health.capture.last_record_at)}. Capture liveness unknown.` : 'No dated capture delivery established. Quiet or stalled cannot be determined.'],
    ['Decoder', 'Unknown', health?.decode.reason || 'No decoder heartbeat is available. A connection alone does not establish data delivery.'],
    ['Analysis', 'Unknown', health?.analysis.reason || 'No analysis heartbeat is available. No alerts does not imply a fault.'],
  ]
  $('sourceHealth').innerHTML = cards.map(([title, value, note]) => `<article class="health-card border-border"><h2>${escape(title)}</h2><div class="health-value">${escape(value)}</div><p>${escape(note)}</p></article>`).join('')
}
function localContext(record) {
  const position = positionOf(record)
  return { missing: [!record.transcript && 'Transcript', !record.audio_url && 'Audio reference', !record.language && 'Language', !record.observed_at && 'Observation time', !position && 'Event location', !record.metadata.trigger && 'Recorded trigger'].filter(Boolean), geography: { position, candidate_tracks: [], reason: position ? 'Coordinates are recorded, but unverified. No time-aligned vessel source is available.' : 'No event coordinates recorded. The overview is not the event location.' } }
}
async function selectRecord(record, moveFocus = true) {
  const epoch = ++selectionEpoch
  questionEpoch++
  selected = record
  context = localContext(record)
  renderQueue()
  renderEvidence()
  renderMap()
  for (const button of $('questionButtons').querySelectorAll('button')) { button.disabled = false; button.setAttribute('aria-pressed', 'false') }
  $('answerBox').innerHTML = '<p>Choose a question about this event.</p>'
  if (moveFocus && window.innerWidth < 1000) $('evidenceTitle').scrollIntoView({ behavior: 'instant', block: 'start' })
  if (mode === 'live' && record.kind === 'alert') {
    try {
      const data = await getJson(`/alerts/${encodeURIComponent(record.id)}/evidence`)
      if (epoch !== selectionEpoch) return
      if (!data || data.alert_id !== record.id || !Array.isArray(data.missing) || !data.geography) throw new Error('Invalid evidence response')
      context = data
      renderEvidence()
      renderMap()
    } catch {
      if (epoch !== selectionEpoch) return
      const note = document.createElement('p')
      note.className = 'source-note'
      note.textContent = 'Evidence service unavailable. Showing the selected queue record only.'
      $('evidenceBody').append(note)
    }
  }
}
function updateSelectionState() {
  if (!selected) return
  const state = mode === 'replay' ? 'Unverified sample' : records.some(row => key(row) === key(selected)) ? feedState(selectedFeed(), Date.now(), !$('autoRefreshToggle').checked) : 'Outside current queue'
  $('evidenceOrigin').textContent = state
  $('evidenceOrigin').className = `state ${['Stale', 'Unverified sample', 'Outside current queue'].includes(state) ? 'warn' : ''}`
}
function renderEvidence() {
  if (!selected) return
  const row = selected
  $('evidenceTitle').textContent = row.title
  updateSelectionState()
  const audio = mode === 'live' ? safeAudioUrl(row.audio_url, window.location.origin) : null
  const stress = numberOrNull(row.metadata.stress_score ?? row.metadata.stress_level)
  const facts = [ ['Frequency', measurement(row.frequency_mhz, ' MHz', 3)], ['Language', row.language || 'Unknown'], ['Signal power', measurement(row.average_power_dbfs, ' dBFS', 1)], ['Source', row.source || 'Not recorded'], ['Observation time', dateText(row.observed_at)], ['Record created', dateText(row.created_at)] ]
  $('evidenceBody').innerHTML = `<div class="evidence-content"><dl class="evidence-meta">${facts.map(([title, value]) => `<div><dt>${escape(title)}</dt><dd>${escape(value)}</dd></div>`).join('')}</dl><section class="evidence-section"><h3>Original transcript</h3><div class="transcript" dir="auto">${escape(row.transcript || 'No transcript recorded.')}</div></section><section class="evidence-section"><h3>Recording</h3>${audio ? `<audio id="evidenceAudio" controls preload="none" src="${escape(audio)}"></audio><p class="source-note" id="audioStatus">Local audio. Playback starts only when you press play.</p>` : `<p class="muted">${row.audio_url ? 'Audio reference is not available through the approved local audio route.' : 'No audio reference recorded.'}</p>`}</section><section class="evidence-section"><h3>Recorded interpretation</h3><p>${escape(row.description || 'No analysis narrative recorded.')}</p><p class="source-note">${stress === null ? 'No stress score recorded.' : `Experimental stress indicator: ${stress}.`} Method: ${escape(row.metadata.analysis_method || row.metadata.model || 'not recorded')}. This is not a validated probability of distress.</p></section><section class="evidence-section"><h3>Evidence gaps</h3><ul class="missing-list">${(context.missing || []).map(item => `<li>${escape(item)}</li>`).join('') || '<li>Basic fields present; accuracy unverified</li>'}</ul></section><details><summary>Source record and measurements</summary><pre>${escape(JSON.stringify(row, null, 2))}</pre></details></div>`
  if (audio) $('evidenceAudio').addEventListener('error', () => { $('audioStatus').textContent = 'Recording unavailable or unsupported. The reference is retained; no substitute audio is played.' })
}
function initMap() {
  if (!window.L) { $('evidenceMap').textContent = 'Map library unavailable. Coordinates remain available in the evidence panel.'; $('showBasemap').disabled = true; return }
  map = window.L.map('evidenceMap', { zoomControl: true, attributionControl: true, scrollWheelZoom: false }).setView([35.9, 14.51], 9)
  map.attributionControl.setPrefix(false)
  grid = window.L.layerGroup().addTo(map)
  map.on('moveend', drawGrid)
  drawGrid()
}
function drawGrid() {
  if (!map || !grid) return
  grid.clearLayers()
  if (tiles) return
  const bounds = map.getBounds()
  const width = bounds.getEast() - bounds.getWest()
  const step = width > 20 ? 10 : width > 4 ? 1 : width > 1 ? .25 : .05
  const color = getComputedStyle(document.documentElement).getPropertyValue('--mac-grid').trim()
  for (let lat = Math.ceil(bounds.getSouth() / step) * step, n = 0; lat < bounds.getNorth() && n < 30; lat += step, n++) window.L.polyline([[lat, bounds.getWest()], [lat, bounds.getEast()]], { color, weight: 1, interactive: false }).addTo(grid)
  for (let lon = Math.ceil(bounds.getWest() / step) * step, n = 0; lon < bounds.getEast() && n < 30; lon += step, n++) window.L.polyline([[bounds.getSouth(), lon], [bounds.getNorth(), lon]], { color, weight: 1, interactive: false }).addTo(grid)
}
function renderMap() {
  if (point) { point.remove(); point = null }
  const position = context?.geography?.position
  $('associationNote').textContent = 'No verified, time-aligned vessel feed is connected. No vessel association has been made.'
  if (position) {
    $('mapTitle').textContent = 'Recorded event position'
    $('mapSummary').textContent = context.geography.reason
    $('mapCoordinates').textContent = `${position.lat.toFixed(5)}, ${position.lon.toFixed(5)} · unverified · ${position.source || 'record metadata'}`
    if (map) {
      const color = getComputedStyle(document.documentElement).getPropertyValue('--mac-accent').trim()
      point = window.L.circleMarker([position.lat, position.lon], { radius: 8, color, fillColor: color, fillOpacity: .5 }).addTo(map)
      const label = document.createElement('span'); label.textContent = 'Recorded event position · unverified'
      point.bindTooltip(label)
      map.setView([position.lat, position.lon], 10, { animate: false })
    }
  } else {
    $('mapTitle').textContent = selected ? 'Event unlocated' : 'Malta overview'
    $('mapSummary').textContent = selected ? 'No event coordinates recorded. No point has been placed for this transmission.' : 'Select an event to see whether it has recorded coordinates.'
    $('mapCoordinates').textContent = '35.9000° N · 14.5100° E · overview only'
    if (map) map.setView([35.9, 14.51], 9, { animate: false })
  }
}
async function ask(question) {
  if (!selected) return
  const row = selected
  const epoch = ++questionEpoch
  for (const button of $('questionButtons').querySelectorAll('button')) button.setAttribute('aria-pressed', String(button.dataset.question === question))
  $('answerBox').innerHTML = '<p>Reading the selected record…</p>'
  if (mode === 'replay' || row.kind !== 'alert') {
    $('answerBox').innerHTML = `<p>${escape(localAnswer(row, question))}</p><small>${mode === 'replay' ? 'Unverified historical sample.' : 'Selected capture record.'} Answer from this record only.</small>`
    return
  }
  try {
    const result = await getJson(`/alerts/${encodeURIComponent(row.id)}/question?question=${encodeURIComponent(question)}`)
    if (epoch !== questionEpoch) return
    $('answerBox').innerHTML = `<p>${escape(result.answer)}</p><small>Recorded fields: ${escape(result.evidence_fields?.join(', ') || 'none supporting a positive finding')}. No conclusion inferred.</small>`
  } catch {
    if (epoch !== questionEpoch) return
    $('answerBox').innerHTML = '<p>The evidence service could not answer. No conclusion has been generated. You can still inspect the selected record.</p>'
  }
}
$('questionButtons').innerHTML = questions.map(([id, label]) => `<button type="button" data-question="${id}" aria-pressed="false" disabled>${label}</button>`).join('')
$('questionButtons').addEventListener('click', event => { const button = event.target.closest('[data-question]'); if (button) ask(button.dataset.question) })
$('eventList').addEventListener('click', event => { const button = event.target.closest('[data-event]'); if (button) { const record = records.find(row => key(row) === button.dataset.event); if (record) selectRecord(record) } })
$('eventSearch').addEventListener('input', renderQueue)
$('eventKind').addEventListener('change', renderQueue)
$('refreshNow').addEventListener('click', refresh)
$('autoRefreshToggle').addEventListener('change', () => { renderFeedSummary(); renderHealth(); if ($('autoRefreshToggle').checked) refresh() })
$('dataMode').addEventListener('change', () => {
  mode = $('dataMode').value
  selected = null; context = null; selectionEpoch++; questionEpoch++
  $('replayNotice').hidden = mode !== 'replay'
  $('refreshNow').disabled = mode !== 'live'
  $('autoRefreshToggle').disabled = mode !== 'live'
  $('evidenceTitle').textContent = 'Inspect the evidence'
  $('evidenceOrigin').textContent = 'No selection'
  $('evidenceBody').innerHTML = '<div class="selection-empty"><h3>Select an event</h3><p>Inspect its source, timing and supporting evidence.</p></div>'
  $('answerBox').innerHTML = '<p>Select an event, then choose a question.</p>'
  for (const button of $('questionButtons').querySelectorAll('button')) { button.disabled = true; button.setAttribute('aria-pressed', 'false') }
  collectRecords(); renderQueue(); renderHealth(); renderMap()
  if (mode === 'live') refresh()
})
$('showBasemap').addEventListener('click', () => {
  if (!map) return
  if (tiles) { tiles.remove(); tiles = null; drawGrid(); $('showBasemap').textContent = 'Show basemap'; $('mapSource').textContent = 'Coordinate grid only. Show basemap loads OpenStreetMap tiles for the visible area.'; return }
  tiles = window.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a>' }).addTo(map)
  drawGrid()
  tiles.on('tileerror', () => { $('mapSource').textContent = 'Some basemap tiles are unavailable. Recorded coordinates remain unchanged.' })
  $('showBasemap').textContent = 'Hide basemap'
  $('mapSource').textContent = 'OpenStreetMap basemap. Tiles show geography, not live observations.'
})
$('resetMap').addEventListener('click', renderMap)
initMap(); renderHealth(); refresh()
// Reuse the app's existing OpenStreetMap basemap. Audio and transcripts stay local.
if (map) $('showBasemap').click()
setInterval(() => { if ($('autoRefreshToggle').checked && mode === 'live') refresh() }, 10000)
setInterval(() => { renderFeedSummary(); renderHealth() }, 1000)

// Illustrative display only. Never connected to evidence stores or hardware controls.
function initSyntheticTraces() {
  const canvas = $('rfCanvas')
  const ctx = canvas.getContext('2d')
  const audioCanvas = $('audioPreviewCanvas')
  const audioCtx = audioCanvas?.getContext('2d')
  const buffer = document.createElement('canvas')
  const history = buffer.getContext('2d')
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
  const frequencies = [119.45, 121.5, 156.45, 156.8, 162.025]
  const bins = 768
  let selectedFrequency = 156.8
  let paused = motion.matches
  let last = 0
  let time = 0
  let width = 0
  let height = 0
  const styles = getComputedStyle(document.documentElement)
  const color = (name, fallback) => styles.getPropertyValue(name).trim() || styles.getPropertyValue(fallback).trim()
  const background = color('--mac-background')
  const muted = color('--mac-text-secondary')
  const gridColor = color('--mac-grid')
  const blue = color('--mac-signal-mid', '--mac-primary-blue-400')
  const cyan = color('--mac-signal-high', '--mac-accent')
  const ochre = color('--mac-signal-peak', '--mac-warning')
  const palette = [color('--mac-signal-low', '--mac-map'), blue, cyan, ochre]

  function samples(t) {
    return Array.from({ length: bins }, (_, i) => {
      const frequency = 108 + i / (bins - 1) * 66
      let strength = .09 + .035 * Math.sin(i * 11.7 + t * 3) + .03 * Math.sin(i * 4.1 - t * 5)
      frequencies.forEach((peak, n) => {
        const distance = (frequency - peak) / (n === 2 ? .19 : .3)
        const burst = .36 + .38 * Math.pow((1 + Math.sin(t * (1 + n * .2) + n)) / 2, 2)
        strength += Math.exp(-distance * distance) * burst
        strength += Math.exp(-Math.pow(distance / 3, 2)) * .08
      })
      return Math.min(.98, Math.max(.01, strength))
    })
  }
  function historyRow(t) {
    history.drawImage(buffer, 0, 0, bins, buffer.height - 1, 0, 1, bins, buffer.height - 1)
    history.fillStyle = background
    history.fillRect(0, 0, bins, 1)
    samples(t).forEach((value, i) => {
      const level = value < .17 ? 0 : value < .35 ? 1 : value < .6 ? 2 : 3
      history.globalAlpha = level === 0 ? .45 + value * 3 : .5 + value * .5
      history.fillStyle = palette[level]
      history.fillRect(i, 0, 1, 1)
    })
    history.globalAlpha = 1
  }
  function drawAudio() {
    if (!audioCtx || !audioCanvas) return
    const w = audioCanvas.clientWidth, h = audioCanvas.clientHeight
    audioCtx.clearRect(0, 0, w, h)
    audioCtx.fillStyle = background; audioCtx.fillRect(0, 0, w, h)
    audioCtx.strokeStyle = gridColor; audioCtx.lineWidth = 1
    for (let x = 0; x < w; x += 32) {
      audioCtx.beginPath(); audioCtx.moveTo(x, 0); audioCtx.lineTo(x, h); audioCtx.stroke()
    }
    for (let y = 16; y < h; y += 32) {
      audioCtx.beginPath(); audioCtx.moveTo(0, y); audioCtx.lineTo(w, y); audioCtx.stroke()
    }
    const channel = frequencies.indexOf(selectedFrequency) + 1
    const middle = h * .5
    // A synthetic speech-shaped envelope, never derived from a recording.
    for (let x = 8; x < w - 8; x += 3) {
      const phase = x / Math.max(w, 1) * 20 + time * 2
      const envelope = .12 + .6 * Math.pow(Math.sin(phase * .64 + channel), 4)
      const carrier = .3 + .7 * Math.abs(Math.sin(x * .7 + time * 8 + channel))
      const amplitude = envelope * carrier * h * .48
      audioCtx.strokeStyle = amplitude > h * .24 ? ochre : cyan
      audioCtx.globalAlpha = .65 + carrier * .35
      audioCtx.beginPath(); audioCtx.moveTo(x, middle - amplitude); audioCtx.lineTo(x, middle + amplitude); audioCtx.stroke()
    }
    audioCtx.globalAlpha = 1
    audioCtx.strokeStyle = blue
    audioCtx.beginPath(); audioCtx.moveTo(0, middle); audioCtx.lineTo(w, middle); audioCtx.stroke()
  }
  function draw() {
    const left = 40, right = width - 16, top = 24, bottom = Math.floor(height * .46)
    const plotWidth = Math.max(1, right - left)
    const selectedX = left + (selectedFrequency - 108) / 66 * plotWidth
    ctx.fillStyle = background; ctx.fillRect(0, 0, width, height)
    ctx.font = '11px ui-monospace, monospace'; ctx.lineWidth = 1
    ctx.textAlign = 'left'
    for (let n = 0; n <= 3; n++) {
      const y = top + (bottom - top) * n / 3
      ctx.strokeStyle = gridColor
      ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke()
      ctx.fillStyle = muted; ctx.fillText(String(-20 - n * 30), 4, y + 4)
    }
    ctx.fillStyle = muted; ctx.fillText('dB*', 4, 12)
    ctx.fillStyle = ochre; ctx.globalAlpha = .09
    ctx.fillRect(selectedX - 8, top, 16, bottom - top)
    ctx.globalAlpha = 1
    const values = samples(time)
    ctx.beginPath(); ctx.moveTo(left, bottom)
    values.forEach((value, i) => ctx.lineTo(left + i / (bins - 1) * plotWidth, bottom - value * (bottom - top)))
    ctx.lineTo(right, bottom); ctx.closePath(); ctx.fillStyle = blue; ctx.globalAlpha = .16; ctx.fill(); ctx.globalAlpha = 1
    ctx.strokeStyle = cyan; ctx.lineWidth = 1.5; ctx.beginPath()
    values.forEach((value, i) => {
      const x = left + i / (bins - 1) * plotWidth, y = bottom - value * (bottom - top)
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
    })
    ctx.stroke()
    ctx.fillStyle = muted
    const ticks = width < 500 ? [108, 130, 152, 174] : [108, 119, 130, 141, 152, 163, 174]
    ticks.forEach(f => { const x = left + (f - 108) / 66 * plotWidth; ctx.textAlign = f === 174 ? 'right' : 'center'; ctx.fillText(String(f), x, bottom + 16) })
    ctx.textAlign = 'left'
    const waterfallTop = bottom + 24
    ctx.imageSmoothingEnabled = false
    ctx.drawImage(buffer, left, waterfallTop, plotWidth, height - waterfallTop - 24)
    ctx.strokeStyle = ochre; ctx.lineWidth = 1; ctx.setLineDash([4, 4])
    ctx.beginPath(); ctx.moveTo(selectedX, top); ctx.lineTo(selectedX, height - 24); ctx.stroke(); ctx.setLineDash([])
    ctx.fillStyle = ochre
    ctx.beginPath(); ctx.moveTo(selectedX - 4, top - 8); ctx.lineTo(selectedX + 4, top - 8); ctx.lineTo(selectedX, top - 2); ctx.closePath(); ctx.fill()
    ctx.fillStyle = muted
    ctx.fillText(width < 500 ? 'MHz → · synthetic levels' : 'MHz → · synthetic levels · newest sweep at top', left, height - 6)
    drawAudio()
  }
  function sizeCanvas(element, context) {
    const ratio = Math.min(window.devicePixelRatio || 1, 2)
    element.width = Math.max(1, Math.floor(element.clientWidth * ratio))
    element.height = Math.max(1, Math.floor(element.clientHeight * ratio))
    context.setTransform(ratio, 0, 0, ratio, 0, 0)
  }
  function resize() {
    width = Math.floor(canvas.clientWidth); height = Math.floor(canvas.clientHeight)
    sizeCanvas(canvas, ctx)
    if (audioCanvas && audioCtx) sizeCanvas(audioCanvas, audioCtx)
    buffer.width = bins; buffer.height = Math.max(2, Math.floor(height / 2))
    for (let row = buffer.height; row >= 0; row--) historyRow(time - row / 15)
    draw()
  }
  function tick(now) {
    if (!paused && !document.hidden && now - last >= 66) {
      time += .066; last = now; historyRow(time); draw()
    }
    requestAnimationFrame(tick)
  }
  function updateButton() {
    $('pauseRf').textContent = paused ? 'Resume traces' : 'Pause traces'
  }
  function selectFrequency(frequency) {
    selectedFrequency = frequency
    document.querySelectorAll('[data-preview-frequency]').forEach(button => button.setAttribute('aria-pressed', String(Number(button.dataset.previewFrequency) === frequency)))
    if ($('previewFrequency')) $('previewFrequency').textContent = frequency.toFixed(3) + ' MHz'
    draw()
  }
  document.querySelectorAll('[data-preview-frequency]').forEach(button => {
    button.addEventListener('click', () => {
      const frequency = Number(button.dataset.previewFrequency)
      if (frequencies.includes(frequency)) selectFrequency(frequency)
    })
  })
  $('pauseRf').addEventListener('click', () => { paused = !paused; updateButton() })
  motion.addEventListener('change', event => { paused = event.matches; updateButton() })
  const observer = new ResizeObserver(resize)
  observer.observe(canvas)
  if (audioCanvas) observer.observe(audioCanvas)
  updateButton(); resize(); selectFrequency(selectedFrequency); requestAnimationFrame(tick)
}
initSyntheticTraces()
