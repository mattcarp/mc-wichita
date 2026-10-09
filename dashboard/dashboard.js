const MALTA_TZ = "Europe/Malta";
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
  map: null,
  mapLayer: null,
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

function magma(t) {
  const x = Math.max(0, Math.min(1, t));
  const r = Math.min(1, 2.5 * Math.max(0, x - 0.25));
  const g = Math.min(1, 4 * Math.max(0, x - 0.5) * (1 - x));
  const b = Math.min(1, 1.2 * (1 - x));
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
  return colorBlind ? cividis(t) : magma(t);
}

function drawSpectrum(psd) {
  const canvas = $("#spectrumCanvas");
  if (!canvas || !psd?.available) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  const freqs = psd.freq_mhz;
  const vals = psd.psd_db_per_hz;
  if (!freqs?.length) return;
  const minF = freqs[0];
  const maxF = freqs[freqs.length - 1];
  const minV = Math.min(...vals);
  const maxV = Math.max(...vals);
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
    const y = h - norm * (h - 8) - 4;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.strokeStyle = "#3ec6c9";
  ctx.lineWidth = 1.5;
  ctx.stroke();
  for (const bm of BOOKMARKS) {
    const x = ((bm.mhz - minF) / (maxF - minF)) * w;
    ctx.strokeStyle = bm.color;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#9aa3b2";
    ctx.font = "11px Geist Mono, monospace";
    ctx.fillText(bm.key, x + 3, 12);
  }
}

function drawAisWaterfall(analysis, colorBlind) {
  const canvas = $("#waterfallCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.fillStyle = "#08090c";
  ctx.fillRect(0, 0, w, h);
  const channels = analysis?.channels || {};
  const duration = 120;
  const bursts = [];
  for (const [name, ch] of Object.entries(channels)) {
    if (!name.includes("AIS")) continue;
    for (const b of ch.bursts || []) {
      bursts.push({ ...b, band: name.includes("AIS1") ? 161.975 : 162.025 });
    }
  }
  if (!bursts.length) {
    ctx.fillStyle = "#9aa3b2";
    ctx.font = "13px Geist Sans, sans-serif";
    ctx.fillText("No AIS bursts in this capture window.", 12, h / 2);
    return;
  }
  const maxT = Math.max(duration, ...bursts.map((b) => b.t_s || 0));
  for (const b of bursts) {
    const y = ((b.t_s || 0) / maxT) * h;
    const x0 = b.band === 161.975 ? w * 0.35 : w * 0.55;
    const snr = b.snr_db || 15;
    const t = Math.min(1, (snr - 14) / 6);
    const [r, g, bl] = paletteColor(t, colorBlind);
    ctx.fillStyle = `rgb(${r},${g},${bl})`;
    ctx.fillRect(x0, y, w * 0.08, 3);
  }
}

function drawAirband(airband) {
  const canvas = $("#airbandCanvas");
  const note = $("#airbandNote");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
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
  for (let i = 0; i < chans.length; i++) {
    const c = chans[i];
    const x = ((c.freq_mhz - minF) / (maxF - minF)) * w;
    const barH = ((c.maxhold_over_floor_db ?? 0) / maxV) * (h - 20);
    const isSpur = c.tag?.includes("spur");
    ctx.fillStyle = isSpur ? "#8b93a7" : "#6bcf7f";
    ctx.fillRect(x, h - barH - 10, Math.max(2, w / chans.length), barH);
    if (c.tag) {
      ctx.fillStyle = "#9aa3b2";
      ctx.font = "10px Geist Mono, monospace";
      ctx.fillText(c.tag.split(" ")[0], x, h - 2);
    }
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
  ul.innerHTML = messages
    .slice(0, 40)
    .map((m) => {
      const label = m.label || m.mmsi_display || "AIS";
      const t = m.t_s != null ? `${m.t_s.toFixed ? m.t_s.toFixed(1) : m.t_s}s` : "";
      return `<li><span class="mono">${t}</span> · ${label} · type ${m.type ?? "?"}</li>`;
    })
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

function initMap(lat, lon) {
  const container = $("#harbourMap");
  if (!container || typeof L === "undefined") return;
  if (!state.map) {
    state.map = L.map(container, { zoomControl: false, attributionControl: true });
    state.mapLayer = L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      { maxZoom: 18, attribution: "&copy; OSM & CARTO" },
    );
    state.mapLayer.addTo(state.map);
  }
  state.map.setView([lat, lon], 12);
  state.map.eachLayer((layer) => {
    if (layer instanceof L.Marker) state.map.removeLayer(layer);
  });
  const icon = L.divIcon({
    className: "ais-base",
    html: '<span style="color:#3ec6c9;font-size:1.2rem">◆</span>',
    iconSize: [20, 20],
  });
  L.marker([lat, lon], { icon }).addTo(state.map).bindPopup("Valletta AIS base station");
}

function renderVoiceTiles(detail) {
  const grid = $("#voiceTiles");
  if (!grid) return;
  const marine = detail?.marine_watch || {};
  const air = detail?.airband?.watch || {};
  const tiles = [];
  const addTile = (title, freq, tile, kind) => {
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
  addTile("Channel 16", "156.800 MHz", marine.ch16, "marine");
  addTile("Channel 09", "156.450 MHz", marine.ch09, "marine");
  const air1215 = air.AIR_121p500MHz_distress || Object.values(air).find((a) => a.freq_mhz === 121.5);
  const air1231 = Object.values(air).find((a) => a.freq_mhz && Math.abs(a.freq_mhz - 123.1) < 0.05);
  addTile("121.5 guard", "121.500 MHz", air1215 || { quiet: true }, "air");
  addTile("123.1 SAR", "123.100 MHz", air1231 || { quiet: true }, "air");
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

async function loadCapture(captureId) {
  const detail = await fetchJson(`/api/capture-feed/${encodeURIComponent(captureId)}`);
  const psd = await fetchJson(
    `/api/capture-feed/${encodeURIComponent(captureId)}/wideband-psd?max_points=1500`,
  );
  state.captureId = captureId;
  drawSpectrum(psd);
  drawAisWaterfall(detail.analysis, state.colorBlind);
  drawAirband(detail.airband);
  renderAisCounts(detail.summary, detail.ais || []);
  renderAisFeed(detail.ais || []);
  const base = (detail.ais || []).find((m) => m.lat != null && m.lon != null);
  if (base) initMap(base.lat, base.lon);
  else initMap(35.8987, 14.5145);
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
    await loadCapture(id);
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
    });
  });
}

function main() {
  renderBookmarks();
  setupTabs();
  setupSubtabs();
  tickClock();
  setInterval(tickClock, 30000);
  $("#colorBlindMap")?.addEventListener("change", (e) => {
    state.colorBlind = e.target.checked;
    if (state.dashboard?.primary) {
      drawAisWaterfall(state.dashboard.primary.analysis, state.colorBlind);
    }
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
