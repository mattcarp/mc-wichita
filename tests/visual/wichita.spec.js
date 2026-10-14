import { test, expect } from "@playwright/test";

const TABS = ["harbour", "heard", "sky", "recordings", "station"];
const FORBIDDEN = /voice\s*lab|kansas|mayday|i['’]ve been everywhere|people who are vulnerable rarely say the right words/i;
const H2 = "People in trouble rarely say the right words. Wichita listens for how they sound.";
// Live regions masked in screenshot baselines (real data changes every poll).
const DYNAMIC = [
  "#harbourMap", "#mapSideList", "#mapFollowCard", "#headerLive", "#maltaClock", "#harbourSummary", "#maltaWeather",
  "#heardBadge", "#feedHealthRow", "#freshnessCounts", "#liveShipList", "#shoreStations", "#voiceTiles",
  "#activityStrip", "#timeline", "#incidentReplayPanel", "#alertReviewList", "#planesPanel", "#satellitesPanel",
  "#stationLive", "#stationStrip", "#captureCompare", "canvas", "#captureAisNote", "#bookmarkLegend",
  "#spectrumMarkers", ".sp-edge", "#groundVoiceSummary", "#groundVoiceList",
];

async function openApp(page) {
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto("/", { waitUntil: "load" });
  await page.waitForSelector("#appShell:not([hidden])", { timeout: 20000 });
  await page.waitForSelector("#harbourMap svg path", { state: "attached", timeout: 15000 });
  await page.waitForFunction(() => !/Checking/.test(document.querySelector("#headerLive")?.innerText || ""), null, { timeout: 15000 });
  await page.waitForTimeout(1500);
  return errors;
}

const STYLE_KEYS = ["fontFamily", "fontSize", "fontWeight", "letterSpacing", "textTransform", "color", "backgroundColor",
  "borderTopWidth", "borderBottomWidth", "borderBottomColor", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "lineHeight"];
const styles = (loc) => loc.evaluateAll((els, keys) => els.map((e) => {
  const cs = getComputedStyle(e);
  return { id: e.id || e.textContent.trim().slice(0, 30), s: Object.fromEntries(keys.map((k) => [k, cs[k]])) };
}), STYLE_KEYS);
function expectAllSame(list, what) {
  expect(list.length, `${what}: none found`).toBeGreaterThan(0);
  const ref = JSON.stringify(list[0].s);
  for (const x of list) expect(JSON.stringify(x.s), `${what} differs: "${x.id}" vs "${list[0].id}"`).toBe(ref);
}

test("(d) signed out: no user name, no forbidden strings", async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: { cookies: [], origins: [] } });
  const page = await ctx.newPage();
  await page.goto("/", { waitUntil: "load" });
  await page.waitForSelector("#authEmail", { timeout: 20000 });
  const text = await page.innerText("body");
  expect(text).not.toMatch(/\bmatt\b/i);
  expect(await page.locator("#appShell").isHidden()).toBe(true);
  expect(await page.locator("#wichitaUserMenu").innerText().catch(() => "")).toBe("");
  expect(text).not.toMatch(FORBIDDEN);
  await expect(page).toHaveScreenshot("signed-out.png");
  await ctx.close();
});

test("(e) map draws in under 1 s", async ({ page }) => {
  await openApp(page);
  const times = [];
  for (let i = 0; i < 3; i++) {
    await page.reload({ waitUntil: "commit" });
    const t = await page.waitForFunction(() => document.querySelectorAll("#harbourMap svg path").length > 0 ? performance.now() : false,
      null, { timeout: 15000, polling: 25 }).then((h) => h.jsonValue());
    times.push(t);
  }
  times.sort((a, b) => a - b);
  console.log("map draw ms", times.map(Math.round));
  expect(times[1], `median map draw ${Math.round(times[1])} ms`).toBeLessThan(1000);
});

test("(f) no console errors, no horizontal overflow; (h) no forbidden strings", async ({ page }) => {
  const errors = await openApp(page);
  const ov = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
  expect(ov.sw, "horizontal overflow").toBeLessThanOrEqual(ov.cw);
  const body = await page.innerText("body");
  expect(body).not.toMatch(FORBIDDEN);
  expect(body.split(H2).length - 1, "H2 text appears exactly once").toBe(1);
  // Only 1 is singular: "1 ships" etc. must never appear (0 and many stay plural).
  const badPlural = body.match(/\b1 (ships|vessels|aircrafts|satellites|recordings|alerts|messages|msgs|minutes|hours|days|others|times)\b/g);
  expect(badPlural, `singular count with plural noun: ${badPlural}`).toBeNull();
  expect(body, "0 and many take the plural").not.toMatch(/\b(0|[2-9]|\d{2,}) (ship|vessel|satellite|recording|alert|message)\b/);
  expect((body.match(/rarely say the right words/gi) || []).length, "phrase not repeated").toBe(1);
  expect(await page.locator('[data-tab-target="voicelab"], #panel-voicelab').count()).toBe(0);
  // Clerk's own bot-protection probe (client.protect.clerk.com) fails CORS on its side since 14 Oct;
  // ignore exactly those and one paired ERR_FAILED each. Every other console error still fails.
  let probes = errors.filter((e) => /client\.protect\.clerk\.com\/.*\/probe/.test(e)).length;
  const ours = errors.filter((e) => {
    if (/client\.protect\.clerk\.com\/.*\/probe/.test(e)) return false;
    if (probes > 0 && e === "Failed to load resource: net::ERR_FAILED") { probes--; return false; }
    return true;
  });
  expect(ours, ours.join("\n")).toEqual([]);
});

test("(i) ground voice: allowlist only, honest state, no source URLs", async ({ page }) => {
  await openApp(page);
  await page.click('[data-tab-target="heard"]');
  const rows = page.locator('[data-test-id="ground-voice-channel"]');
  await expect(rows).toHaveCount(5);
  const ids = await rows.evaluateAll((els) => els.map((e) => e.dataset.channel).sort());
  expect(ids).toEqual(["air-121-5", "cb-ch9", "ham-2m-calling", "ham-70cm-calling", "marine-ch16"]);
  const states = await rows.evaluateAll((els) => els.map((e) => e.dataset.state));
  for (const s of states) expect(["live", "idle", "limit"]).toContain(s);
  const html = await page.locator("#groundVoiceList").innerHTML();
  expect(html, "no stream URLs in the page").not.toMatch(/https?:\/\/|rtl_tcp|:1234|100\.\d+\.\d+/);
  expect(await page.locator("#groundVoiceList").innerText()).not.toMatch(/tetra|pmr446|446\.\d/i);
  // Idle channels offer no Listen button.
  expect(await page.locator('[data-state="idle"] .gv-listen').count()).toBe(0);
  const api = await page.evaluate(async () => (await fetch("/api/ground-voice/channels")).text());
  expect(api).not.toMatch(/https?:\/\//);
});

test("(j) ground voice API and audio proxy refuse signed-out callers", async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: { cookies: [], origins: [] } });
  const r1 = await ctx.request.get("/api/ground-voice/channels", { failOnStatusCode: false });
  expect(r1.status()).toBe(401);
  const r2 = await ctx.request.post("/api/ground-voice/channels/marine-ch16/ticket", { failOnStatusCode: false });
  expect(r2.status()).toBe(401);
  const r3 = await ctx.request.get("/api/ground-voice/listen/marine-ch16?ticket=nope", { failOnStatusCode: false });
  expect(r3.status()).toBe(401);
  await ctx.close();
});

test("(b) every tab button and panel heading is styled identically", async ({ page }) => {
  await openApp(page);
  const tabs = page.locator(".tab-btn");
  expect(await tabs.count()).toBe(TABS.length);
  const actives = [];
  for (const name of TABS) {
    await page.click(`.tab-btn[data-tab-target="${name}"]`);
    await page.waitForTimeout(300);
    const st = await styles(page.locator(".tab-btn:not(.active)"));
    expectAllSame(st, `inactive tab buttons (with ${name} active)`);
    actives.push(...(await styles(page.locator(".tab-btn.active"))));
  }
  expectAllSame(actives, "active tab button");
  expectAllSame(await styles(page.locator(".tab-panel .panel-head h2")), "panel h2");
  expectAllSame(await styles(page.locator(".tab-panel .panel-head .eyebrow")), "panel eyebrow");
  const heads = await page.locator(".tab-panel").evaluateAll((els) => els.map((e) => [e.id, Boolean(e.querySelector(":scope > .panel-head h2"))]));
  for (const [id, ok] of heads) expect(ok, `${id} has a standard panel heading`).toBe(true);
});

test("(c) no overlapping text labels on the map", async ({ page }) => {
  await openApp(page);
  for (const zoom of ["harbour", "malta"]) {
    await page.click(`.map-zoom-bar button[data-zoom="${zoom}"]`).catch(() => {});
    await page.waitForTimeout(800);
    const boxes = await page.locator("#harbourMap svg text").evaluateAll((ts) => ts.map((t) => {
      const r = t.getBoundingClientRect(); return { s: t.textContent, x0: r.left, x1: r.right, y0: r.top, y1: r.bottom };
    }).filter((b) => b.x1 > b.x0));
    const hits = [];
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], b = boxes[j];
      if (a.x0 < b.x1 && a.x1 > b.x0 && a.y0 < b.y1 && a.y1 > b.y0) hits.push(`${a.s} / ${b.s}`);
    }
    expect(hits, `${zoom}: ${hits.join(", ")}`).toEqual([]);
  }
});

test("(g) every expandable row shows 'More details' and toggles aria-expanded", async ({ page }) => {
  await openApp(page);
  const sums = page.locator("#liveShipList summary.expand-cue");
  const n = await sums.count();
  expect(n, "roster rows").toBeGreaterThan(0);
  for (let i = 0; i < n; i++) {
    await expect(sums.nth(i)).toContainText("More details");
    await expect(sums.nth(i)).toHaveAttribute("aria-expanded", "false");
  }
  const first = sums.first();
  await first.focus();
  await page.keyboard.press("Enter");
  await expect(first).toHaveAttribute("aria-expanded", "true");
  await expect(first).toContainText("Less");
  await page.keyboard.press("Enter");
  await expect(first).toHaveAttribute("aria-expanded", "false");

  const rows = page.locator("#mapSideList .side-ship");
  const m = await rows.count();
  expect(m, "sidebar rows").toBeGreaterThan(0);
  for (let i = 0; i < m; i++) {
    await expect(rows.nth(i).locator(".cue-more")).toHaveText("More details");
    await expect(rows.nth(i)).toHaveAttribute("aria-expanded", "false");
  }
  const mmsi = await rows.first().getAttribute("data-mmsi");
  await rows.first().focus();
  await page.keyboard.press("Enter");
  const row = page.locator(`#mapSideList .side-ship[data-mmsi="${mmsi}"]`);
  await expect(row).toHaveAttribute("aria-expanded", "true");
  await expect(row.locator(".cue-less")).toBeVisible();
  await expect(page.locator("#sideDetail a.mmsi-link")).toHaveAttribute("href", /vesselfinder\.com\/\?mmsi=\d+/);
  await row.click();
  await expect(page.locator(`#mapSideList .side-ship[data-mmsi="${mmsi}"]`)).toHaveAttribute("aria-expanded", "false");
});

test("(a) screenshot baselines per tab", async ({ page }) => {
  await openApp(page);
  const mask = DYNAMIC.map((s) => page.locator(s));
  await page.evaluate(() => window.scrollTo(0, 0));
  // Top of the page down to the bottom of the map; the live sidebar below it changes height with real data.
  const mapBox = await page.locator(".harbour-map-col").boundingBox();
  const vw = page.viewportSize().width;
  await expect(page).toHaveScreenshot("top.png", { mask, maxDiffPixelRatio: 0.05, clip: { x: 0, y: 0, width: vw, height: Math.min(Math.floor(mapBox.y + mapBox.height), page.viewportSize().height) } });
  for (const name of TABS) {
    await page.click(`.tab-btn[data-tab-target="${name}"]`);
    await page.waitForTimeout(700);
    // Panel headers are static, so they get strict baselines. Whole-viewport shots of live
    // sections shift with real data, so they are saved as artifacts, not compared.
    const bb = await page.locator(`#panel-${name} .panel-head`).boundingBox();
    const clip = { x: Math.floor(bb.x), y: Math.floor(bb.y), width: Math.ceil(bb.width), height: 44 };
    await expect(page).toHaveScreenshot(`tab-${name}-head.png`, { clip });
    await page.screenshot({ path: test.info().outputPath(`tab-${name}.png`), mask });
  }
});

test("(i) aircraft: exactly one aircraft layer, one row per ICAO hex, source labelled", async ({ page }) => {
  await openApp(page);
  // Only one plane layer on the map: every plane marker is a direct child of the single map SVG,
  // and no ICAO hex has two markers.
  const svgs = await page.locator("#harbourMap svg").evaluateAll((els) =>
    els.filter((s) => s.querySelector("[data-plane-id]")).length);
  expect(svgs, "SVG layers carrying aircraft").toBeLessThanOrEqual(1);
  const markerIds = await page.locator("#harbourMap [data-plane-id]").evaluateAll((els) => els.map((e) => e.getAttribute("data-plane-id")));
  expect(new Set(markerIds).size, "duplicate aircraft markers").toBe(markerIds.length);
  await page.click('.tab-btn[data-tab-target="sky"]');
  await expect(page.locator("#planesPanel [data-test-id=aircraft-source-label]")).toContainText("adsb.lol, community feed");
  expect(await page.locator("#planesPanel").count(), "aircraft panels").toBe(1);
  const paused = await page.locator("#planesPanel [data-test-id=aircraft-paused]").count();
  if (!paused) {
    const rowIds = await page.locator("#planesPanel .live-plane-card").evaluateAll((els) => els.map((e) => e.getAttribute("data-plane-id")));
    expect(rowIds.length, "aircraft rows").toBeGreaterThan(0);
    expect(new Set(rowIds).size, "duplicate aircraft rows").toBe(rowIds.length);
    const cards = page.locator("#planesPanel .live-plane-card");
    for (let i = 0; i < Math.min(rowIds.length, 5); i++) {
      await expect(cards.nth(i).locator("[data-test-id=plane-source]")).toHaveText(/^(adsb\.lol|local antenna|local \+ adsb\.lol)$/);
      await expect(cards.nth(i).locator("summary .cue-more")).toHaveText("More details");
    }
    // Emergencies pinned to the top.
    const em = await cards.evaluateAll((els) => els.map((e) => e.classList.contains("plane-emergency")));
    const firstNon = em.indexOf(false);
    if (firstNon >= 0) expect(em.slice(firstNon).includes(true), "emergency below a normal aircraft").toBe(false);
    await expect(page.locator("#planesPanel .counts")).not.toContainText(/\b1 aircrafts\b/);
  }
});
