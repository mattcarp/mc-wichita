/** Run against the real API at :3000 and the explicit UI test runner at :3001.
 * Records on :3001 are presentation fixtures, not hardware observations.
 * PLAYWRIGHT_MODULE points to an existing Playwright install; no project dependency.
 */
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { mkdir } from 'node:fs/promises'
const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const { PNG } = require(require.resolve('pngjs', { paths: [process.env.PLAYWRIGHT_MODULE || process.cwd()] }))
const out = new URL('../output/playwright/alert-coverage-20260914/', import.meta.url).pathname
await mkdir(out, { recursive: true })
const browser = await chromium.launch({ headless: true })
let checks = 0
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
  await page.clock.install()
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('http://127.0.0.1:3000')
  await page.waitForFunction(() => document.querySelector('#queueFeedNotes').textContent.includes('Alerts: Empty'))
  assert.match(await page.locator('.rf-preview').innerText(), /Synthetic preview/)
  const traceBefore = await page.locator('#rfCanvas').evaluate(canvas => canvas.toDataURL())
  await page.clock.fastForward(300)
  const traceAfter = await page.locator('#rfCanvas').evaluate(canvas => canvas.toDataURL())
  assert.notEqual(traceBefore, traceAfter, 'Synthetic traces should animate')
  await page.locator('#pauseRf').click()
  const pausedTrace = await page.locator('#rfCanvas').evaluate(canvas => canvas.toDataURL())
  await page.clock.fastForward(300)
  assert.equal(await page.locator('#rfCanvas').evaluate(canvas => canvas.toDataURL()), pausedTrace)
  const waveformBefore = await page.locator('#audioPreviewCanvas').evaluate(canvas => canvas.toDataURL())
  await page.locator('[data-preview-frequency="121.500"]').click()
  assert.match(await page.locator('#previewFrequency').innerText(), /121.500/)
  assert.notEqual(await page.locator('#audioPreviewCanvas').evaluate(canvas => canvas.toDataURL()), waveformBefore, 'Channel selection updates waveform')
  const pausedWaveform = await page.locator('#audioPreviewCanvas').evaluate(canvas => canvas.toDataURL())
  await page.clock.fastForward(300)
  assert.equal(await page.locator('#audioPreviewCanvas').evaluate(canvas => canvas.toDataURL()), pausedWaveform, 'Pause applies to audio waveform')
  checks++
  assert.equal(await page.locator('[data-event]').count(), 0)
  assert.match(await page.locator('#sourceHealth').innerText(), /Unknown/)
  checks++
  // Explicit replay preserves an empty live queue on return.
  await page.selectOption('#dataMode', 'replay')
  await page.locator('[data-event]').first().focus()
  await page.keyboard.press('Enter')
  assert.equal(await page.evaluate(() => document.activeElement.dataset.event), 'capture:sample-d1')
  await page.locator('[data-question="missing"]').click()
  assert.match(await page.locator('#answerBox').innerText(), /Not recorded: transcript/)
  assert.match(await page.locator('#mapTitle').innerText(), /unlocated/)
  checks++
  for (const width of [1440, 768, 521, 375]) {
    await page.setViewportSize({ width, height: 1000 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `Overflow at ${width}`)
    // Fixed local sample state for repeatable visual comparison; exclude network tiles.
    if ((await page.locator('#showBasemap').innerText()).includes('Hide')) await page.locator('#showBasemap').click()
    await page.locator('#dataMode').focus()
    await page.screenshot({ path: out + `sample-${width}.png`, fullPage: true, animations: 'disabled' })
    await page.waitForTimeout(400) // Allow Leaflet's resize observer to settle.
    const first = await page.screenshot({ path: out + `stability-a-${width}.png`, fullPage: true, animations: 'disabled' })
    const second = await page.screenshot({ path: out + `stability-b-${width}.png`, fullPage: true, animations: 'disabled' })
    const a = PNG.sync.read(first), b = PNG.sync.read(second)
    assert.equal(a.width, b.width); assert.equal(a.height, b.height)
    let changed = 0
    for (let i = 0; i < a.data.length; i += 4) {
      if ([0, 1, 2].some(c => Math.abs(a.data[i + c] - b.data[i + c]) > 2)) changed++
    }
    assert.ok(changed / (a.width * a.height) < .001, `Visual instability at ${width}: ${changed} pixels`)
    checks++
  }
  await page.selectOption('#dataMode', 'live')
  await page.waitForFunction(() => document.querySelector('#queueFeedNotes').textContent.includes('Alerts: Empty'))
  assert.equal(await page.locator('[data-event]').count(), 0)
  checks++
  await page.setViewportSize({ width: 1440, height: 1100 })
  await page.goto('http://127.0.0.1:3001')
  await page.waitForSelector('[data-event="alert:ui-contract-mt"]')
  // Threat review must include alerts outside the stress-only endpoint.
  const stressOnly = await (await page.request.get('http://127.0.0.1:3001/stress-alerts')).json()
  assert.ok(!stressOnly.some(row => row.id === 'ui-contract-threat'))
  await page.locator('[data-event="alert:ui-contract-threat"]').click({ timeout: 5000 })
  await page.locator('[data-question="why"]').click()
  await page.waitForFunction(() => document.querySelector('#answerBox').textContent.includes('repeated channel interference'))
  await page.selectOption('#eventKind', 'alert')
  assert.equal(await page.locator('[data-event]').count(), 5)
  await page.selectOption('#eventKind', 'capture')
  assert.equal(await page.locator('[data-event]').count(), 1)
  await page.selectOption('#eventKind', 'all')
  assert.equal(await page.locator('[data-event]').count(), 6)
  checks++
  await page.locator('[data-event="alert:ui-contract-mt"]').click()
  await page.waitForFunction(() => document.querySelector('#mapTitle').textContent.includes('Recorded event'))
  assert.equal(await page.locator('.transcript img').count(), 0, 'Transcript must not become HTML')
  assert.match(await page.locator('.transcript').innerText(), /Għajnuna/)
  await page.locator('[data-question="time"]').click()
  await page.waitForFunction(() => document.querySelector('#answerBox').textContent.includes('11:59:00'))
  assert.match(await page.locator('#mapCoordinates').innerText(), /35.90000, 14.51000/)
  checks++
  // Load genuine local audio through the real API; no synthetic substitute.
  await page.locator('#evidenceAudio').evaluate(audio => { audio.muted = true; audio.load() })
  await page.waitForFunction(() => document.querySelector('#evidenceAudio').readyState >= 1)
  assert.ok(await page.locator('#evidenceAudio').evaluate(audio => audio.duration > 0))
  await page.locator('#evidenceAudio').evaluate(audio => audio.play())
  await page.waitForFunction(() => document.querySelector('#evidenceAudio').currentTime > 0)
  await page.locator('#evidenceAudio').evaluate(audio => audio.pause())
  checks++
  for (const [language, text] of [['ar', 'مساعدة'], ['it', 'Aiuto'], ['en', 'Help']]) {
    await page.locator(`[data-event="alert:ui-contract-${language}"]`).click()
    await page.waitForFunction(() => document.querySelector('#mapTitle').textContent.includes('unlocated'))
    assert.match(await page.locator('.transcript').innerText(), new RegExp(text))
    await page.locator('[data-question="language"]').click()
    await page.waitForFunction(lang => document.querySelector('#answerBox').textContent.includes(`language: ${lang}`), language)
    checks++
  }
  await page.locator('[data-event="capture:ui-contract-zero"]').click()
  assert.match(await page.locator('#evidenceBody').innerText(), /0\.0 dBFS/)
  assert.match(await page.locator('#evidenceBody').innerText(), /0\.000 MHz/)
  checks++
  // Refresh while the queue button has keyboard focus.
  await page.locator('[data-event="alert:ui-contract-en"]').focus()
  await page.keyboard.press('Enter')
  await page.locator('#refreshNow').evaluate(button => button.click())
  await page.waitForFunction(() => !document.querySelector('#refreshNow').disabled)
  assert.equal(await page.evaluate(() => document.activeElement.dataset.event), 'alert:ui-contract-en')
  checks++
  // Block only capture delivery: other real endpoints must continue to refresh.
  await page.route('**/captures?*', route => route.abort('failed'))
  await page.locator('#refreshNow').click()
  await page.waitForFunction(() => !document.querySelector('#refreshNow').disabled)
  assert.match(await page.locator('#queueFeedNotes').innerText(), /Captures: Stale/)
  assert.match(await page.locator('#queueFeedNotes').innerText(), /Alerts: Available/)
  assert.equal(await page.locator('[data-event]').count(), 6)
  await page.unroute('**/captures?*')
  await page.clock.fastForward(11000)
  await page.locator('#refreshNow').click()
  await page.waitForFunction(() => !document.querySelector('#refreshNow').disabled)
  checks++
  await page.locator('#autoRefreshToggle').uncheck()
  await page.clock.fastForward(31000)
  assert.match(await page.locator('#sourceHealth').innerText(), /Stale/)
  assert.match(await page.locator('#queueFeedNotes').innerText(), /Stale/)
  checks++
  // Full service disconnection, real browser offline state; retain last records.
  await page.context().setOffline(true)
  await page.locator('#refreshNow').click()
  await page.clock.fastForward(6000)
  await page.waitForFunction(() => document.querySelector('#queueFeedNotes').textContent.includes('Service unavailable'))
  assert.equal(await page.locator('[data-event]').count(), 6)
  await page.context().setOffline(false)
  await page.clock.fastForward(20000)
  await page.locator('#refreshNow').click()
  await page.waitForFunction(() => !document.querySelector('#refreshNow').disabled)
  assert.ok(!(await page.locator('#queueFeedNotes').innerText()).includes('Service unavailable'))
  checks++
  assert.deepEqual(errors, [])
  console.log(`${checks} browser scenarios passed; no JavaScript page errors.`)
} finally { await browser.close() }
