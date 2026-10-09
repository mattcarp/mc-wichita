import {
  PLOT_PAD_X,
  freqToPlotX,
  plotInnerWidth,
  psdSpan,
  samplePsdAtMhz,
} from "./spectrum_geometry.mjs?v=20261009-14";

const MALTA_TZ = "Europe/Malta";
const VALLETTA = { lat: 35.8987, lon: 14.5145, span: 0.06 };

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

function chartCssHeight(defaultPx) {
  const vw = document.documentElement.clientWidth || 800;
  return vw < 420 ? Math.round(defaultPx * 0.72) : defaultPx;
}

function fitCanvas(canvas, cssHeight, logicalPixels = false) {
  const wrap = canvas.closest(".chart-wrap") || canvas.parentElement;
  const cssWidth = Math.max(240, Math.floor(wrap?.clientWidth || 320));
  cssHeight = chartCssHeight(cssHeight);
  canvas.style.width = `${cssWidth}px`;
  canvas.style.height = `${cssHeight}px`;
  const ctx = canvas.getContext("2d");
  if (logicalPixels) {
    canvas.width = cssWidth;
    canvas.height = cssHeight;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    return { ctx, w: cssWidth, h: cssHeight };
  }
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.floor(cssWidth * dpr);
  canvas.height = Math.floor(cssHeight * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w: cssWidth, h: cssHeight };
}

function formatCaption(sentences) {
  return sentences
    .filter(Boolean)
    .map((s, i) => {
      let t = String(s).trim();
      if (!t) return "";
      if (i > 0) t = t.charAt(0).toUpperCase() + t.slice(1);
      if (!/[.!?]$/.test(t)) t += ".";
      return t;
    })
    .join(" ");
}

function clampMarkerCenterX(x, width, w) {
  const half = width / 2;
  return Math.max(PLOT_PAD_X + half, Math.min(w - PLOT_PAD_X - half, x));
}

function updateWaterfallAxisLabels(psd) {
  const axis = document.querySelector(".waterfall-axis");
  if (!axis) return;
  const { minF, maxF } = psdSpan(psd);
  const spans = axis.querySelectorAll("span");
  if (spans.length >= 2) {
    spans[0].textContent = `${minF.toFixed(3)} MHz`;
    spans[1].textContent = `${maxF.toFixed(3)} MHz`;
  }
}

function updateLiveBandHeading(psd) {
  const h2 = $("#live-heading");
  if (!h2 || !psd?.available) return;
  const { minF, maxF } = psdSpan(psd);
  h2.textContent = `${minF.toFixed(3)}–${maxF.toFixed(3)} MHz`;
}

const MARKER_FONT = "10px Geist Mono, monospace";
const MARKER_ROW_STEP = 12;

function markerLabelWidth(ctx, key) {
  return ctx.measureText(key).width + 6;
}

function markerLabelBox(key, x, width, w) {
  const cx = clampMarkerCenterX(x, width, w);
  const half = width / 2;
  return { left: cx - half, right: cx + half, cx };
}

function layoutSpectrumMarkerRows(items, w, ctx) {
  ctx.font = MARKER_FONT;
  const sorted = [...items].sort((a, b) => a.x - b.x);
  const placed = [];
  const out = [];
  for (const item of sorted) {
    const width = markerLabelWidth(ctx, item.key);
    let chosenRow = null;
    for (let row = 0; row < 4; row++) {
      const box = markerLabelBox(item.key, item.x, width, w);
      const clash = placed.some(
        (p) =>
          p.row === row &&
          !(box.right < p.left - 2 || box.left > p.right + 2),
      );
      if (!clash) {
        chosenRow = row;
        placed.push({ row, left: box.left, right: box.right });
        out.push({ ...item, row, width });
        break;
      }
    }
    if (chosenRow == null) {
      out.push({ ...item, row: 3, width });
    }
  }
  return out;
}

function renderSpectrumMarkersHtml(w, h, ctx, span) {
  const { minF, maxF, drawMin, drawMax } = span;
  const items = BOOKMARKS.filter(
    (bm) =>
      bm.mhz >= minF - 0.001 &&
      bm.mhz <= maxF + 0.001 &&
      bm.mhz >= drawMin - 0.001 &&
      bm.mhz <= drawMax + 0.001,
  ).map((bm) => ({
    key: bm.key,
    bm,
    x: freqToPlotX(bm.mhz, w, span),
  }));
  const layout = layoutSpectrumMarkerRows(items, w, ctx);
  return layout
    .map(({ key, x, row, width }) => {
      const top = 4 + row * MARKER_ROW_STEP;
      const cx = clampMarkerCenterX(x, width, w);
      return `<span style="left:${cx}px;top:${top}px">${key}</span>`;
    })
    .join("");
}

function drawFilterRollOffBands(ctx, w, h, span) {
  const { minF, maxF, drawMin, drawMax } = span;
  ctx.save();
  ctx.font = "9px Geist Mono, monospace";
  ctx.fillStyle = "rgba(100, 110, 130, 0.14)";
  const xPlotMin = freqToPlotX(minF, w, span);
  const xDrawMin = freqToPlotX(drawMin, w, span);
  if (xDrawMin > xPlotMin + 4) {
    ctx.fillRect(xPlotMin, 0, xDrawMin - xPlotMin, h);
    ctx.fillStyle = "#8b93a7";
    ctx.textAlign = "center";
    ctx.fillText("filter roll-off", (xPlotMin + xDrawMin) / 2, 12);
  }
  const xDrawMax = freqToPlotX(drawMax, w, span);
  const xPlotMax = freqToPlotX(maxF, w, span);
  if (xPlotMax > xDrawMax + 4) {
    ctx.fillStyle = "rgba(100, 110, 130, 0.14)";
    ctx.fillRect(xDrawMax, 0, xPlotMax - xDrawMax, h);
    ctx.fillStyle = "#8b93a7";
    ctx.textAlign = "center";
    ctx.fillText("filter roll-off", (xDrawMax + xPlotMax) / 2, 12);
  }
  ctx.restore();
}

function drawSpectrum(psd) {
  const canvas = $("#spectrumCanvas");
  const caption = $("#spectrumCaption");
  if (!canvas || !psd?.available) return;
  const { ctx, w, h } = fitCanvas(canvas, 200);
  const freqs = psd.freq_mhz;
  const vals = psd.psd_db_per_hz;
  if (!freqs?.length) return;
  const span = psdSpan(psd);
  const { minF: axisMinF, maxF: axisMaxF, drawMin, drawMax } = span;
  const innerW = plotInnerWidth(w);
  const tunerMhz = psd.tuner_center_mhz;
  const dcHalfWidth = 0.06;
  const coreVals = [];
  for (let i = 0; i < freqs.length; i++) {
    const fm = freqs[i];
    if (fm < drawMin || fm > drawMax) continue;
    if (tunerMhz && Math.abs(fm - tunerMhz) < dcHalfWidth) continue;
    coreVals.push(vals[i]);
  }
  const sorted = coreVals.length ? [...coreVals].sort((a, b) => a - b) : [...vals].sort((a, b) => a - b);
  const pct = (p) => sorted[Math.floor(sorted.length * p)] ?? sorted[0];
  const yLoDb = pct(0.01) - 2.5;
  const yHiDb = pct(0.99) + 1.5;
  const ySpan = Math.max(3, yHiDb - yLoDb);
  ctx.fillStyle = "#08090c";
  ctx.fillRect(0, 0, w, h);
  drawFilterRollOffBands(ctx, w, h, span);
  ctx.strokeStyle = "#252a36";
  for (let i = 0; i <= 4; i++) {
    const y = (h * i) / 4;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
  ctx.save();
  ctx.beginPath();
  ctx.rect(PLOT_PAD_X, 0, innerW, h);
  ctx.clip();
  ctx.beginPath();
  let penDown = false;
  let lastFm = null;
  let lastX = null;
  for (let i = 0; i < freqs.length; i++) {
    const fm = freqs[i];
    if (fm < drawMin || fm > drawMax) {
      penDown = false;
      continue;
    }
    if (tunerMhz && Math.abs(fm - tunerMhz) < dcHalfWidth) {
      penDown = false;
      continue;
    }
    const x = freqToPlotX(fm, w, span);
    const y = Math.max(
      6,
      Math.min(h - 6, h - 6 - ((vals[i] - yLoDb) / ySpan) * (h - 12)),
    );
    if (!penDown) {
      ctx.moveTo(x, y);
      penDown = true;
    } else {
      ctx.lineTo(x, y);
    }
    lastFm = fm;
    lastX = x;
  }
  const expectedEndX =
    lastFm != null ? freqToPlotX(lastFm, w, span) : freqToPlotX(drawMax, w, span);
  canvas.dataset.traceEndMhz = String(lastFm ?? "");
  canvas.dataset.traceEndX = String(lastX ?? "");
  canvas.dataset.expectedTraceEndX = String(expectedEndX);
  ctx.strokeStyle = "#3ec6c9";
  ctx.lineWidth = 1.5;
  ctx.stroke();
  ctx.restore();
  if (tunerMhz && tunerMhz >= axisMinF && tunerMhz <= axisMaxF) {
    const tx = freqToPlotX(tunerMhz, w, span);
    ctx.strokeStyle = "#8b93a7";
    ctx.setLineDash([2, 3]);
    ctx.beginPath();
    ctx.moveTo(tx, 0);
    ctx.lineTo(tx, h);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#9aa3b2";
    ctx.font = "9px Geist Mono, monospace";
    ctx.fillText("tuner centre", Math.min(tx + 2, w - 52), h - 4);
  }
  const labelKeys = BOOKMARKS.map((b) => b.key);
  const markersEl = $("#spectrumMarkers");
  if (markersEl) {
    markersEl.style.height = `${h}px`;
    markersEl.innerHTML = renderSpectrumMarkersHtml(w, h, ctx, span);
  }
  for (const key of labelKeys) {
    const bm = BOOKMARKS.find((b) => b.key === key);
    if (
      !bm ||
      bm.mhz < axisMinF - 0.001 ||
      bm.mhz > axisMaxF + 0.001 ||
      bm.mhz < drawMin - 0.001 ||
      bm.mhz > drawMax + 0.001
    ) {
      continue;
    }
    const x = freqToPlotX(bm.mhz, w, span);
    ctx.strokeStyle = bm.color;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
    ctx.setLineDash([]);
  }
  if (caption) {
    caption.textContent = formatCaption([
      "Averaged PSD from capture (not live FFT)",
      psd.span_caption,
      ...(psd.span_notes || []),
      tunerMhz ? `Tuner centre ${tunerMhz.toFixed(3)} MHz (DC spike masked)` : null,
    ]);
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
  const { ctx, w, h } = fitCanvas(canvas, 180, true);
  const duration = Math.max(30, durationSec || 600);
  const grid = new Float32Array(w * h);
  const psdVals = psd?.psd_db_per_hz || [];
  const sortedPsd = [...psdVals].sort((a, b) => a - b);
  const minV = sortedPsd.length
    ? sortedPsd[Math.floor(sortedPsd.length * 0.05)]
    : -120;
  const maxV = sortedPsd.length
    ? sortedPsd[Math.floor(sortedPsd.length * 0.98)]
    : -90;

  const span = psdSpan(psd);
  const { minF, maxF, drawMax } = span;
  if (psd?.available) {
    const inner = plotInnerWidth(w);
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const t = Math.max(0, Math.min(1, (x - PLOT_PAD_X) / inner));
        const mhz = minF + t * (maxF - minF);
        const val = samplePsdAtMhz(psd, mhz);
        if (val == null) continue;
        const norm = Math.min(1, Math.max(0, (val - minV) / (maxV - minV + 1e-6)));
        grid[y * w + x] = norm * 0.22;
      }
    }
  }

  const bursts = collectAisBursts(analysis);
  if (bursts.length) {
    for (const b of bursts) {
      const y = Math.min(h - 2, Math.max(0, Math.floor((b.t_s / duration) * (h - 4))));
      const x = Math.min(
        w - 1,
        Math.max(0, Math.floor(freqToPlotX(b.freq_mhz, w, span))),
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

  if (caption) {
    caption.textContent = formatCaption([
      bursts.length
        ? "Time (vertical) vs marine band frequency (horizontal); colormap from AIS burst timing and averaged PSD floor — not a live IQ spectrogram"
        : "No burst timing in this capture; showing averaged PSD baseline only (not a live waterfall)",
    ]);
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

function bookmarkMeasurable(mhz, psd) {
  if (!psd?.available) return true;
  const { drawMin, drawMax } = psdSpan(psd);
  return mhz >= drawMin - 0.001 && mhz <= drawMax + 0.001;
}

function renderBookmarks(psd) {
  const ul = $("#bookmarkLegend");
  if (!ul) return;
  const narrow = (document.documentElement.clientWidth || 800) < 420;
  ul.innerHTML = BOOKMARKS.map((b) => {
    const ok = bookmarkMeasurable(b.mhz, psd);
    if (ok) {
      return `<li>${b.key} ${b.mhz.toFixed(3)} MHz</li>`;
    }
    if (narrow) {
      return `<li class="legend-unmeasurable">${b.key} ${b.mhz.toFixed(3)}, not measurable here</li>`;
    }
    return `<li class="legend-unmeasurable">${b.key} ${b.mhz.toFixed(3)} MHz — not measurable in this capture</li>`;
  }).join("");
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
      const time = e.time_utc ? formatMalta(e.time_utc) : "—";
      const caution = e.caution ? `<p class="caution">${e.caution}</p>` : "";
      return `<li><strong class="event-title">${e.title}</strong><span class="muted">${e.detail || ""}</span><span class="mono event-time">${time}</span>${caution}</li>`;
    })
    .join("");
}

function renderStation(station, comparison) {
  const dl = $("#stationStrip");
  const panel = $("#panel-station");
  if (!dl) return;
  const source = station?.source_label || "";
  let sourceEl = panel?.querySelector(".station-source");
  if (panel && !sourceEl) {
    sourceEl = document.createElement("p");
    sourceEl.className = "station-source mono";
    panel.querySelector(".panel-head")?.after(sourceEl);
  }
  if (sourceEl) sourceEl.textContent = source ? `${source} (not live)` : "";
  const items = [
    ["Receiver", station?.receiver],
    ["Serial", station?.device_serial],
    ["Bias-T", station?.bias_t],
    ["Overflows", station?.overflows ?? "—"],
    [
      "Noise (RMS)",
      station?.noise_rms_dbfs != null ? `${station.noise_rms_dbfs} dBFS` : "—",
    ],
    ["Antenna", station?.antenna_note || "—"],
  ];
  dl.innerHTML = items
    .map(([k, v]) => `<div><dt>${k}</dt><dd>${v ?? "—"}</dd></div>`)
    .join("");
  const cmp = $("#captureCompare");
  const rows = comparison || station?.capture_comparison || [];
  if (cmp && rows.length) {
    cmp.innerHTML =
      "<p><strong>Capture comparison</strong></p><ul class=\"compare-list mono\">" +
      rows
        .map(
          (s) =>
            `<li>${s.picker_label || s.capture_id} · ${s.ais_message_count ?? 0} AIS msgs</li>`,
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
      const short = c.picker_label || c.capture_id;
      const title = `${c.capture_id} — ${c.location || "unknown"}`;
      return `<option value="${c.capture_id}" title="${title.replace(/"/g, "'")}" ${c.capture_id === selected ? "selected" : ""}>${short}</option>`;
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
  updateLiveBandHeading(state.lastPsd);
  updateWaterfallAxisLabels(state.lastPsd);
  renderBookmarks(state.lastPsd);
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
  renderStation(detail.station_snapshot, null);
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
    renderStation(detail.station_snapshot, data.recent_captures);
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
    requestAnimationFrame(() => redrawCharts());
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
