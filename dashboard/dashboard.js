const MALTA_TZ = "Europe/Malta";
const VALLETTA = { lat: 35.8987, lon: 14.5145, span: 0.06 };
const MARINE_MIN_MHZ = 156.45;
const MARINE_MAX_MHZ = 162.55;

const BOOKMARKS = [
  { key: "CH09", mhz: 156.45, color: "#3ec6c9" },
  { key: "CH16", mhz: 156.8, color: "#3ec6c9" },
  { key: "CH70", mhz: 156.525, color: "#3ec6c9" },
  { key: "AIS1", mhz: 161.975, color: "#3ec6c9" },
  { key: "AIS2", mhz: 162.025, color: "#3ec6c9" },
];

const state = {
  dashboard: null,
  captureId: null,
  colorBlind: false,
  lastPsd: null,
  lastAnalysis: null,
  lastDuration: 600,
};

function $(sel) {
  return document.querySelector(sel);
}

function formatMalta(isoOrSec) {
  let d;
  if (typeof isoOrSec === "number") {
    d = new Date(isoOrSec * 1000);
  } else if (isoOrSec) {
    d = new Date(isoOrSec);
  } else {
    return "—";
  }
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: MALTA_TZ,
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(d);
}

function tickClock() {
  const el = $("#maltaClock");
  if (!el) return;
  const now = new Date();
  el.textContent = formatMalta(now.getTime() / 1000);
  el.dateTime = now.toISOString();
}

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} → ${res.status}`);
  return res.json();
}

function inferno(t) {
  const x = Math.max(0, Math.min(1, t));
  const r = Math.min(1, Math.max(0, 1.4 * x - 0.1));
  const g = Math.min(1, Math.max(0, 2.2 * x * x - 0.4 * x));
  const b = Math.min(1, Math.max(0, 3.5 * x * x * x - 1.2 * x));
  return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
}

function cividis(t) {
  const x = Math.max(0, Math.min(1, t));
  return [
    Math.round(255 * (0.15 + 0.85 * x)),
    Math.round(255 * (0.2 + 0.6 * x)),
    Math.round(255 * (0.35 + 0.25 * x)),
  ];
}

function paletteColor(t, colorBlind) {
  return colorBlind ? cividis(t) : inferno(t);
}

function fitCanvas(canvas, cssHeight) {
  const wrap = canvas.closest(".chart-wrap") || canvas.parentElement;
  const cssWidth = Math.max(240, Math.floor(wrap?.clientWidth || 320));
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.style.width = `${cssWidth}px`;
  canvas.style.height = `${cssHeight}px`;
  canvas.width = Math.floor(cssWidth * dpr);
  canvas.height = Math.floor(cssHeight * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w: cssWidth, h: cssHeight };
}

function samplePsdAtMhz(psd, mhz) {
  const freqs = psd.freq_mhz;
  const vals = psd.psd_db_per_hz;
  if (!freqs?.length) return null;
  if (mhz <= freqs[0]) return vals[0];
  if (mhz >= freqs[freqs.length - 1]) return vals[vals.length - 1];
  for (let i = 1; i < freqs.length; i++) {
    if (freqs[i] >= mhz) {
      const t = (mhz - freqs[i - 1]) / (freqs[i] - freqs[i - 1]);
      return vals[i - 1] + t * (vals[i] - vals[i - 1]);
    }
  }
  return vals[vals.length - 1];
}

function drawSpectrum(psd) {
  const canvas = $("#spectrumCanvas");
  const caption = $("#spectrumCaption");
  if (!canvas || !psd?.available) return;
  const { ctx, w, h } = fitCanvas(canvas, 200);
  const freqs = psd.freq_mhz;
  const vals = psd.psd_db_per_hz;
  if (!freqs?.length) return;
  const minF = freqs[0];
  const maxF = freqs[freqs.length - 1];
  const sorted = [...vals].sort((a, b) => a - b);
  const minV = sorted[Math.floor(sorted.length * 0.05)];
  const maxV = sorted[Math.floor(sorted.length * 0.98)];
  ctx.fillStyle = "#08090c";
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = "#252a36";
  for (let i = 0; i <= 4; i++) {
    const y = (h * i) / 4;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
  ctx.beginPath();
  for (let i = 0; i < freqs.length; i++) {
    const x = ((freqs[i] - minF) / (maxF - minF)) * w;
    const norm = (vals[i] - minV) / (maxV - minV + 1e-6);
    const y = h - norm * (h - 12) - 6;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.strokeStyle = "#3ec6c9";
  ctx.lineWidth = 1.5;
  ctx.stroke();
  for (const bm of BOOKMARKS) {
    if (bm.mhz < minF || bm.mhz > maxF) continue;
    const x = ((bm.mhz - minF) / (maxF - minF)) * w;
    ctx.strokeStyle = bm.color;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#9aa3b2";
    ctx.font = "10px Geist Mono, monospace";
    ctx.fillText(bm.key, x + 2, 11);
  }
  if (caption) {
    const parts = ["Averaged PSD from capture (not live FFT)."];
    if (psd.trim_note) parts.push(psd.trim_note);
    caption.textContent = parts.join(" ");
  }
}

function collectAisBursts(analysis) {
  const out = [];
  const channels = analysis?.channels || {};
  for (const [name, ch] of Object.entries(channels)) {
    if (!name.includes("AIS")) continue;
    const freq = name.includes("AIS1") ? 161.975 : 162.025;
    for (const b of ch.bursts || []) {
      const snr = b.snr_db ?? 15;
      out.push({
        t_s: b.t_s ?? 0,
        freq_mhz: freq,
        intensity: Math.min(1, Math.max(0.15, (snr - 13) / 8)),
      });
    }
  }
  for (const msg of analysis?.ais_messages || []) {
    if (msg.t_s == null) continue;
    const ch = msg.channel === "B" ? 162.025 : 161.975;
    out.push({ t_s: msg.t_s, freq_mhz: ch, intensity: 0.55 });
  }
  return out;
}

function splatEnergy(grid, w, h, cx, cy, energy, radius) {
  const r = radius || 3;
  for (let dy = -r; dy <= r; dy++) {
    for (let dx = -r; dx <= r; dx++) {
      const x = cx + dx;
      const y = cy + dy;
      if (x < 0 || y < 0 || x >= w || y >= h) continue;
      const d = Math.hypot(dx, dy);
      const falloff = Math.max(0, 1 - d / (r + 0.5));
      grid[y * w + x] = Math.min(1, grid[y * w + x] + energy * falloff);
    }
  }
}

function drawBurstWaterfall(analysis, psd, colorBlind, durationSec) {
  const canvas = $("#waterfallCanvas");
  const caption = $("#waterfallCaption");
  if (!canvas) return;
  const { ctx, w, h } = fitCanvas(canvas, 180);
  const duration = Math.max(30, durationSec || 600);
  const grid = new Float32Array(w * h);
  const minV = psd?.psd_db_per_hz ? Math.min(...psd.psd_db_per_hz) : -120;
  const maxV = psd?.psd_db_per_hz ? Math.max(...psd.psd_db_per_hz) : -90;

  if (psd?.available) {
    for (let x = 0; x < w; x++) {
      const mhz = MARINE_MIN_MHZ + (x / (w - 1)) * (MARINE_MAX_MHZ - MARINE_MIN_MHZ);
      const val = samplePsdAtMhz(psd, mhz);
      if (val == null) continue;
      const norm = Math.min(1, Math.max(0, (val - minV) / (maxV - minV + 1e-6)));
      grid[(h - 1) * w + x] = norm * 0.25;
    }
  }

  const bursts = collectAisBursts(analysis);
  if (bursts.length) {
    for (const b of bursts) {
      const y = Math.min(h - 2, Math.max(0, Math.floor((b.t_s / duration) * (h - 4))));
      const x = Math.min(
        w - 1,
        Math.max(0, Math.floor(((b.freq_mhz - MARINE_MIN_MHZ) / (MARINE_MAX_MHZ - MARINE_MIN_MHZ)) * (w - 1))),
      );
      splatEnergy(grid, w, h, x, y, b.intensity, 4);
    }
  }

  const img = ctx.createImageData(w, h);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const v = grid[y * w + x];
      const [r, g, b] = paletteColor(v, colorBlind);
      const i = (y * w + x) * 4;
      img.data[i] = r;
      img.data[i + 1] = g;
      img.data[i + 2] = b;
      img.data[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);

  ctx.fillStyle = "#9aa3b2";
  ctx.font = "9px Geist Mono, monospace";
  ctx.fillText(`${MARINE_MIN_MHZ}`, 2, h - 2);
  ctx.fillText(`${MARINE_MAX_MHZ}`, w - 36, h - 2);

  if (caption) {
    caption.textContent = bursts.length
      ? "Time (vertical) vs marine band frequency (horizontal). Colormap from AIS burst timing and averaged PSD floor — not a live IQ spectrogram."
      : "No burst timing in this capture; showing averaged PSD baseline only (not a live waterfall).";
  }
}

function drawAirband(airband) {
  const canvas = $("#airbandCanvas");
  const note = $("#airbandNote");
  if (!canvas) return;
  const { ctx, w, h } = fitCanvas(canvas, 200);
  ctx.fillStyle = "#08090c";
  ctx.fillRect(0, 0, w, h);
  if (!airband?.available || !airband.channels?.length) {
    ctx.fillStyle = "#9aa3b2";
    ctx.font = "13px Geist Sans, sans-serif";
    ctx.fillText(airband?.reason || "No airband scan in this capture.", 12, h / 2);
    if (note) note.textContent = "";
    return;
  }
  const chans = airband.channels;
  const minF = chans[0].freq_mhz;
  const maxF = chans[chans.length - 1].freq_mhz;
  const vals = chans.map((c) => c.maxhold_over_floor_db ?? 0);
  const maxV = Math.max(...vals, 1);
  const barW = Math.max(2, w / chans.length);
  for (let i = 0; i < chans.length; i++) {
    const c = chans[i];
    const x = ((c.freq_mhz - minF) / (maxF - minF)) * w;
    const barH = ((c.maxhold_over_floor_db ?? 0) / maxV) * (h - 20);
    const isSpur = c.tag?.includes("spur");
    ctx.fillStyle = isSpur ? "#8b93a7" : "#6bcf7f";
    ctx.fillRect(x, h - barH - 10, barW, barH);
  }
  if (note) {
    note.textContent =
      "120.000 and 132.000 MHz marked as known local spurs. 121.5 distress guard and 123.1 SAR labelled when present.";
  }
}

function renderBookmarks() {
  const ul = $("#bookmarkLegend");
  if (!ul) return;
  ul.innerHTML = BOOKMARKS.map((b) => `<li>${b.key} ${b.mhz.toFixed(3)} MHz</li>`).join("");
}

function renderAisCounts(summary, messages) {
  const el = $("#aisCounts");
  if (!el) return;
  const vessels = summary?.vessel_count ?? 0;
  const bases = summary?.base_station_count ?? 0;
  el.textContent = `${bases} station(s) · ${vessels} vessel(s) · ${messages.length} messages`;
}

function renderAisFeed(messages) {
  const ul = $("#aisFeed");
  if (!ul) return;
  if (!messages.length) {
    ul.innerHTML =
      "<li>No ships heard yet in these captures. Antenna is not on the roof — range is limited.</li>";
    return;
  }
  const byLabel = new Map();
  for (const m of messages) {
    const label = m.label || m.mmsi_display || "AIS";
    byLabel.set(label, (byLabel.get(label) || 0) + 1);
  }
  ul.innerHTML = [...byLabel.entries()]
    .map(([label, count]) => `<li>${label} · ${count} message${count === 1 ? "" : "s"} in capture</li>`)
    .join("");
  renderAisSpark(messages);
}

function renderAisSpark(messages) {
  const el = $("#aisSpark");
  if (!el) return;
  const buckets = new Array(12).fill(0);
  const maxT = Math.max(60, ...messages.map((m) => m.t_s || 0));
  for (const m of messages) {
    const idx = Math.min(11, Math.floor(((m.t_s || 0) / maxT) * 12));
    buckets[idx] += 1;
  }
  const maxB = Math.max(1, ...buckets);
  el.innerHTML = buckets
    .map((b) => {
      const h = (b / maxB) * 100;
      return `<span style="display:inline-block;width:7%;height:${h}%;background:#3ec6c9;vertical-align:bottom;margin:0 0.5%"></span>`;
    })
    .join("");
  el.style.display = "flex";
  el.style.alignItems = "flex-end";
  el.style.height = "2.5rem";
}

function initHarbourSchematicMap(lat, lon) {
  const container = $("#harbourMap");
  if (!container) return;
  const cx = 100 + ((lon - VALLETTA.lon) / VALLETTA.span) * 70;
  const cy = 105 - ((lat - VALLETTA.lat) / VALLETTA.span) * 70;
  const grid = [];
  for (let i = 0; i <= 8; i++) {
    const p = i * 25;
    grid.push(`<line x1="${p}" y1="0" x2="${p}" y2="200" stroke="#1a2030" stroke-width="0.5"/>`);
    grid.push(`<line x1="0" y1="${p}" x2="200" y2="${p}" stroke="#1a2030" stroke-width="0.5"/>`);
  }
  container.innerHTML = `<svg viewBox="0 0 200 200" width="100%" height="100%" class="harbour-svg" role="img" aria-label="Valletta harbour schematic">
    <rect width="200" height="200" fill="#0a0c10"/>
    ${grid.join("")}
    <path d="M 35 130 C 55 70, 95 55, 130 85 L 150 130 C 120 155, 70 160, 35 130 Z" fill="#121820" stroke="#2a3344" stroke-width="1"/>
    <text x="10" y="18" fill="#9aa3b2" font-size="9" font-family="Geist Sans, sans-serif">Grand Harbour · Valletta</text>
    <circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="6" fill="#3ec6c9" fill-opacity="0.9"/>
    <text x="${(cx + 8).toFixed(1)}" y="${(cy + 3).toFixed(1)}" fill="#3ec6c9" font-size="8" font-family="Geist Mono, monospace">AIS</text>
  </svg>`;
}

function renderVoiceTiles(detail) {
  const grid = $("#voiceTiles");
  if (!grid) return;
  const marine = detail?.marine_watch || {};
  const air = detail?.airband?.watch || {};
  const tiles = [];
  const addTile = (title, freq, tile) => {
    const quiet = tile?.quiet !== false;
    const led = quiet ? "quiet" : "active";
    const status = quiet ? "Quiet in this capture" : "Activity in capture (not confirmed distress)";
    tiles.push(`
      <article class="voice-tile">
        <h3><span class="led ${led}" aria-hidden="true"></span>${title}</h3>
        <p class="mono">${freq}</p>
        <p class="muted">${status}</p>
      </article>`);
  };
  addTile("Channel 16", "156.800 MHz", marine.ch16);
  addTile("Channel 09", "156.450 MHz", marine.ch09);
  const air1215 = air.AIR_121p500MHz_distress || Object.values(air).find((a) => a.freq_mhz === 121.5);
  const air1231 = Object.values(air).find((a) => a.freq_mhz && Math.abs(a.freq_mhz - 123.1) < 0.05);
  addTile("121.5 guard", "121.500 MHz", air1215 || { quiet: true });
  addTile("123.1 SAR", "123.100 MHz", air1231 || { quiet: true });
  grid.innerHTML = tiles.join("");
}

function renderTimeline(events) {
  const ol = $("#timeline");
  if (!ol) return;
  if (!events?.length) {
    ol.innerHTML =
      "<li class='muted'>Nothing notable in this capture besides routine AIS from the Valletta base station. Quiet is good news.</li>";
    return;
  }
  ol.innerHTML = events
    .map((e) => {
      const time = e.time_malta ? formatMalta(e.time_malta) : "—";
      const caution = e.caution ? `<p class="caution">${e.caution}</p>` : "";
      return `<li><strong>${e.title}</strong> <span class="mono">${time}</span><br/><span class="muted">${e.detail || ""}</span>${caution}</li>`;
    })
    .join("");
}

function renderStation(station, summaries) {
  const dl = $("#stationStrip");
  if (!dl) return;
  const items = [
    ["Receiver", station.receiver],
    ["Serial", station.device_serial],
    ["Bias-T", station.bias_t],
    ["Overflows", station.overflows ?? "—"],
    ["Noise (RMS)", station.noise_floor_dbfs != null ? `${station.noise_floor_dbfs} dBFS` : "—"],
    ["Antenna", station.antenna_note || "—"],
  ];
  dl.innerHTML = items
    .map(([k, v]) => `<div><dt>${k}</dt><dd>${v ?? "—"}</dd></div>`)
    .join("");
  const cmp = $("#captureCompare");
  if (cmp && summaries?.length) {
    cmp.innerHTML =
      "<p><strong>Capture comparison</strong></p><ul>" +
      summaries
        .map(
          (s) =>
            `<li class="mono">${s.capture_id}</li><li class="muted">${s.location || "unknown"} · ${s.ais_message_count ?? 0} AIS msgs</li>`,
        )
        .join("") +
      "</ul>";
  }
}

function populateCaptureSelect(captures, selected) {
  const sel = $("#captureSelect");
  if (!sel) return;
  sel.innerHTML = captures
    .map((c) => {
      const loc = (c.location || "unknown").slice(0, 40);
      return `<option value="${c.capture_id}" ${c.capture_id === selected ? "selected" : ""}>${c.capture_id} · ${loc}</option>`;
    })
    .join("");
}

function captureDurationSec(detail) {
  const wall = detail?.capture_settings?.wall_seconds;
  if (wall) return wall;
  const samples = detail?.capture_settings?.samples;
  const rate = detail?.capture_settings?.readback?.[0]?.sample_rate;
  if (samples && rate) return samples / rate;
  const times = (detail?.ais || []).map((m) => m.t_s || 0);
  return Math.max(120, ...(times.length ? times : [600]));
}

function redrawCharts() {
  if (!state.lastPsd || !state.lastAnalysis) return;
  drawSpectrum(state.lastPsd);
  drawBurstWaterfall(state.lastAnalysis, state.lastPsd, state.colorBlind, state.lastDuration);
}

async function loadCapture(captureId) {
  const detail = await fetchJson(`/api/capture-feed/${encodeURIComponent(captureId)}`);
  const psd = await fetchJson(
    `/api/capture-feed/${encodeURIComponent(captureId)}/wideband-psd?max_points=1500`,
  );
  state.captureId = captureId;
  state.lastPsd = psd;
  state.lastAnalysis = detail.analysis;
  state.lastDuration = captureDurationSec(detail);
  redrawCharts();
  drawAirband(detail.airband);
  renderAisCounts(detail.summary, detail.ais || []);
  renderAisFeed(detail.ais || []);
  const base = (detail.ais || []).find((m) => m.lat != null && m.lon != null);
  if (base) initHarbourSchematicMap(base.lat, base.lon);
  else initHarbourSchematicMap(VALLETTA.lat, VALLETTA.lon);
  renderVoiceTiles(detail);
  renderTimeline(detail.timeline);
  return detail;
}

async function refreshDashboard() {
  const banner = $("#feedBanner");
  const listen = $("#listenState");
  try {
    const data = await fetchJson("/api/capture-feed/dashboard");
    state.dashboard = data;
    if (!data.available) {
      if (banner) {
        banner.hidden = false;
        banner.textContent = data.message;
      }
      if (listen) listen.textContent = "No captures";
      return;
    }
    if (banner) banner.hidden = true;
    if (listen) listen.textContent = `Library · ${data.recent_captures?.length || 0} folders`;
    populateCaptureSelect(data.recent_captures || [], state.captureId || data.primary_capture_id);
    const id = state.captureId || data.primary_capture_id;
    const detail = await loadCapture(id);
    state.dashboard.primary = detail;
    renderStation(data.station, data.recent_captures);
  } catch (err) {
    if (banner) {
      banner.hidden = false;
      banner.textContent = `Could not load capture feed: ${err.message}. Set WICHITA_CAPTURES_DIRS and restart the API.`;
    }
    if (listen) listen.textContent = "Offline";
  }
}

function setupTabs() {
  const buttons = document.querySelectorAll(".tab-btn");
  const panels = document.querySelectorAll(".tab-panel");
  const show = (name) => {
    buttons.forEach((b) => b.classList.toggle("active", b.dataset.tabTarget === name));
    panels.forEach((p) => {
      const match = p.dataset.tab === name;
      p.classList.toggle("active", match);
    });
    const main = $("#main");
    if (main) main.scrollIntoView({ block: "start", behavior: "instant" in window ? "instant" : "auto" });
    window.scrollTo(0, 0);
  };
  buttons.forEach((b) => b.addEventListener("click", () => show(b.dataset.tabTarget)));
  show("live");
}

function setupSubtabs() {
  const tabs = document.querySelectorAll(".subtab");
  const marine = $("#marineBandView");
  const air = $("#airbandView");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => {
        t.classList.toggle("active", t === tab);
        t.setAttribute("aria-selected", t === tab ? "true" : "false");
      });
      const isAir = tab.dataset.subtab === "airband";
      marine?.classList.toggle("hidden", isAir);
      marine?.toggleAttribute("hidden", isAir);
      air?.classList.toggle("hidden", !isAir);
      air?.toggleAttribute("hidden", !isAir);
      if (!isAir) redrawCharts();
      else drawAirband(state.dashboard?.primary?.airband);
    });
  });
}

let resizeTimer;
function onResize() {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(redrawCharts, 150);
}

function main() {
  renderBookmarks();
  setupTabs();
  setupSubtabs();
  tickClock();
  setInterval(tickClock, 30000);
  window.addEventListener("resize", onResize);
  $("#colorBlindMap")?.addEventListener("change", (e) => {
    state.colorBlind = e.target.checked;
    redrawCharts();
  });
  $("#captureSelect")?.addEventListener("change", (e) => {
    loadCapture(e.target.value).catch(console.error);
  });
  refreshDashboard();
  setInterval(refreshDashboard, 60000);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", main);
} else {
  main();
}
