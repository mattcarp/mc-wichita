import { formatMalta, formatMaltaTimeShort } from "./time_malta.js?v=20261013-fr7";
import { HarbourMap, typeColor } from "./harbour_map.js?v=20261013-fr7";
import { provenanceBadge, freshnessClass, heardAntennaBadge, feedHealthChip } from "./entity_labels.js?v=20261013-fr7";
import { fetchSkySnapshots, renderPlanesPanel, renderSatellitesPanel } from "./live_sky.js?v=20261013-fr7";
import { initWatchZones } from "./watch_zones.js?v=20261013-fr7";
import { initIncidentReplay } from "./incident_replay.js?v=20261013-fr7";
import { initHarbourReplay, isReplayActive, replayShipsNow } from "./harbour_replay.js?v=20261013-fr7";

const GROUPS = [
  { key: "now", title: "Now" },
  { key: "recent", title: "Recent" },
  { key: "earlier", title: "Earlier" },
];

const timelineState = {
  nextBefore: null,
  hours: 2,
};

const state = {
  snapshot: null,
  sky: null,
  selectedMmsi: null,
  selectedPlaneId: null,
  follow: null,
  map: null,
  timer: null,
  entityQuery: "",
  activityHours: 24,
};

function $(sel) {
  return document.querySelector(sel);
}

function flagEmoji(iso2) {
  if (!iso2 || iso2.length !== 2) return "";
  const u = iso2.toUpperCase();
  return String.fromCodePoint(...[...u].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65));
}

function agoLabel(lastSignalS) {
  if (lastSignalS == null) return "";
  if (lastSignalS < 60) return "now";
  if (lastSignalS < 3600) return `${Math.round(lastSignalS / 60)} min ago`;
  return `${Math.round(lastSignalS / 3600)} h ago`;
}

function renderHarbourBadge(snapshot) {
  const b = $("#harbourLiveBadge");
  if (!b || !snapshot) return;
  const paused = Boolean(snapshot.feed_paused || snapshot.receiver_offline || snapshot.online === false);
  b.textContent = paused ? "Feed paused" : "LIVE";
  b.classList.toggle("badge-paused", paused);
}

function renderHeader(snapshot) {
  renderHarbourBadge(snapshot);
  const live = $("#headerLive");
  if (!live) return;
  if (!snapshot) {
    live.textContent = "Checking AIS…";
    return;
  }
  const fc = snapshot.freshness_counts || {};
  const dot = snapshot.online ? "live" : "offline";
  live.innerHTML = `<span class="pill pill-${dot}">${snapshot.online ? "Live" : "Feed paused"}</span>
    <span class="header-ship-count">${fc.now ?? 0} ships now · ${fc.today ?? 0} today</span>`;
}

function renderSummary(snapshot) {
  const el = $("#harbourSummary");
  if (!el || !snapshot) return;
  const mc = snapshot.movement_counts || {};
  const nearby = snapshot.freshness_counts?.now ?? mc.now ?? 0;
  const narrow = (document.documentElement.clientWidth || 800) < 720;
  const line = snapshot.summary || "";
  if (narrow) {
    el.innerHTML = `<p class="harbour-summary-oneline">${line}</p>
      <div class="summary-chips mono">
        <span class="chip">${nearby} nearby</span>
        <span class="chip">${mc.moving ?? 0} moving</span>
        <span class="chip">${mc.moored_or_slow ?? 0} moored</span>
      </div>`;
    return;
  }
  el.innerHTML = `<p class="harbour-summary-text">${line}</p>
    <div class="summary-tiles">
      <div><span class="summary-num">${nearby}</span><span class="muted">Nearby now</span></div>
      <div><span class="summary-num">${mc.moving ?? 0}</span><span class="muted">Moving</span></div>
      <div><span class="summary-num">${mc.moored_or_slow ?? 0}</span><span class="muted">Moored or slow</span></div>
    </div>`;
}

function shipCardHtml(s, selected) {
  const flag = flagEmoji(s.country);
  const col = typeColor(s.shiptype_category);
  const eta = s.eta_malta && !s.eta_malta_stale ? `ETA ${s.eta_malta} Malta` : "";
  const tierClass = freshnessClass(s.freshness);
  const fade = s.freshness === "earlier" ? " ship-card-fade" : s.freshness === "recent" ? " ship-card-recent" : "";
  const sel = s.mmsi === selected ? " selected" : "";
  const tierLabel = s.freshness_label || "Earlier";
  return `<li class="live-ship-card ${tierClass}${fade}${sel}" data-mmsi="${s.mmsi}" role="button" tabindex="0" style="--ship-type-color:${col}">
    <div class="live-ship-card-head">
      <span class="ship-type-icon" aria-hidden="true"></span>
      <span class="live-ship-flag" title="${s.country || ""}">${flag}</span>
      <strong>${s.display_name}</strong>${s.speed_known !== false && (s.speed_kn ?? 0) >= 1 ? `<span class="ship-moving mono">moving ${Number(s.speed_kn).toFixed(1)} kn</span>` : ""}
      <span class="mono ship-fresh ship-fresh-${s.freshness || "earlier"}">${(() => { const ago = agoLabel(s.last_signal_s); return !ago || ago.toLowerCase() === tierLabel.toLowerCase() ? tierLabel : `${tierLabel} · ${ago}`; })()}</span>
    </div>
    <p class="ship-lead">${s.lead_sentence}</p>
    <p class="muted ship-meta">${s.shiptype_label}${eta ? ` · ${eta}` : ""}</p>
    <details class="ship-raw-details"><summary>Details · MMSI lookup</summary>
      ${mmsiLookupHtml(s)}
      <p class="mono muted">MMSI ${s.mmsi_display}${s.callsign ? ` · ${s.callsign}` : ""}</p>
      <p class="mono muted">${s.destination_raw || "—"} · ${s.speed_known === false ? "speed unknown" : `${s.speed_kn ?? "—"} kn`} · ${s.message_count ?? 0} msgs</p>
    </details>
  </li>`;
}

function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function mmsiLookupHtml(s) {
  const m = s.mmsi_info;
  if (!m) return "";
  const st = m.static || {};
  const rows = [
    ["MMSI", m.mmsi],
    ["Station type", m.kind_label],
    ["Flag (MID)", m.mid ? `${m.mid_country || "—"} · MID ${m.mid}` : "—"],
    ["Name", st.shipname],
    ["Call sign", st.callsign],
    ["IMO", st.imo],
    ["Type", st.shiptype_label],
    ["Size", st.length_m ? `${st.length_m} m × ${st.beam_m ?? "—"} m` : null],
    ["Draught", st.draught ? `${st.draught} m` : null],
    ["Destination", st.destination],
    ["First heard", st.first_seen_utc ? formatMaltaTimeShort(st.first_seen_utc) : null],
  ].filter(([, v]) => v !== null && v !== undefined && v !== "");
  return `<dl class="mmsi-lookup" data-test-id="mmsi-lookup">${rows
    .map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`)
    .join("")}</dl><p class="mmsi-lookup-src muted">From the MMSI digits (ITU-R M.585), the ITU MID table and AIS data our receiver decoded.</p>`;
}

function matchesEntityQuery(item, q) {
  if (!q) return true;
  const hay = [
    item.display_name,
    item.shipname,
    item.mmsi_display,
    String(item.mmsi),
    item.callsign,
    item.id,
    item.hex,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return hay.includes(q);
}

function renderShipList(snapshot) {
  const ul = $("#liveShipList");
  if (!ul) return;
  const ships = (snapshot?.ships || [])
    .filter((s) => matchesEntityQuery(s, state.entityQuery))
    .slice()
    .sort((a, b) => (a.last_signal_s ?? 1e9) - (b.last_signal_s ?? 1e9));
  const paused = Boolean(snapshot?.feed_paused || snapshot?.receiver_offline);
  const sinceUtc = snapshot?.feed_last_ok_utc;
  const winMin = Math.round((snapshot?.roster_window_s || 3600) / 60);
  const note = paused
    ? `<li class="roster-note roster-note-paused" role="status" data-test-id="roster-paused">Feed paused${sinceUtc ? ` since ${formatMaltaTimeShort(sinceUtc)}` : ""}; showing the last ships heard.</li>`
    : `<li class="roster-note" data-test-id="roster-note">${ships.length} vessel${ships.length === 1 ? "" : "s"} heard in the last ${winMin >= 60 ? `${Math.round(winMin / 60)} h` : `${winMin} min`}, newest first.</li>`;
  if (!ships.length) {
    ul.innerHTML = `${note}<li class='muted'>${paused ? "No ships were heard before the feed paused." : "No vessels heard in the last hour."}</li>`;
    return;
  }
  const byGroup = new Map(GROUPS.map((g) => [g.key, []]));
  for (const s of ships) {
    const k = s.freshness || "earlier";
    (byGroup.get(k) || byGroup.get("earlier")).push(s);
  }
  ul.innerHTML = note + GROUPS
    .map((g) => {
      const list = byGroup.get(g.key) || [];
      if (!list.length) return "";
      return `<li class="ship-group-label">${g.title} · ${list.length}</li>${list.map((s) => shipCardHtml(s, state.selectedMmsi)).join("")}`;
    })
    .join("");
  state.openDetails = state.openDetails || new Set();
  ul.querySelectorAll(".live-ship-card").forEach((li) => {
    const mmsi = Number(li.getAttribute("data-mmsi"));
    const det = li.querySelector(".ship-raw-details");
    if (det) {
      if (state.openDetails.has(mmsi)) det.open = true;
      det.addEventListener("toggle", () => {
        if (det.open) state.openDetails.add(mmsi);
        else state.openDetails.delete(mmsi);
      });
      det.addEventListener("click", (ev) => ev.stopPropagation());
    }
    li.addEventListener("click", () => selectShip(mmsi));
  });
  const bases = snapshot?.base_stations || [];
  const baseEl = $("#shoreStations");
  if (baseEl) {
    baseEl.innerHTML = bases.length
      ? `<p class="eyebrow">Shore stations</p><ul class="shore-list">${bases
          .map(
            (b) =>
              `<li><span class="shore-diamond" aria-hidden="true"></span>${b.display_name} · ${b.message_count ?? 0} msgs</li>`,
          )
          .join("")}</ul>`
      : "";
  }
}

function renderSheet(ship) {
  const sheet = $("#shipSheet");
  const backdrop = $("#sheetBackdrop");
  if (!sheet || !backdrop) return;
  if (!ship) {
    sheet.hidden = true;
    backdrop.hidden = true;
    sheet.classList.remove("open");
    document.body.classList.remove("sheet-open");
    return;
  }
  const flag = flagEmoji(ship.country);
  sheet.hidden = false;
  backdrop.hidden = false;
  sheet.classList.add("open");
  document.body.classList.add("sheet-open");
  sheet.innerHTML = `
    <button type="button" class="sheet-close" id="sheetClose" aria-label="Close">×</button>
    <h3>${flag} ${ship.display_name}</h3>
    <p class="ship-lead">${ship.lead_sentence}</p>
    <p class="muted">${ship.shiptype_label}${ship.eta_malta ? ` · ETA ${ship.eta_malta} Malta` : ""}</p>
    <dl class="ship-detail-dl">
      <dt>Nav status</dt><dd>${ship.nav_status_label || "—"}</dd>
      <dt>Destination</dt><dd>${ship.destination_display || ship.destination_raw || "—"}${ship.destination_decoded === false ? " (code not decoded)" : ""}</dd>
      <dt>Speed / course</dt><dd>${ship.speed_kn ?? "—"} kn · ${ship.cog_deg != null ? Math.round(ship.cog_deg) + "°" : "—"}</dd>
      <dt>Last heard</dt><dd>${agoLabel(ship.last_signal_s)} (${ship.last_heard_utc ? formatMaltaTimeShort(ship.last_heard_utc) : "—"})</dd>
    </dl>
    <a class="mmsi-link" href="https://www.vesselfinder.com/?mmsi=${ship.mmsi}" rel="noopener noreferrer" target="_blank">Look up MMSI (external)</a>
  `;
  $("#sheetClose")?.addEventListener("click", () => selectShip(null));
  backdrop.onclick = () => selectShip(null);
}

function renderDrawer(ship) {
  const el = $("#liveShipDrawer");
  if (!el) return;
  if (!ship) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  const flag = flagEmoji(ship.country);
  el.innerHTML = `
    <button type="button" class="detail-close" id="drawerClose">Close</button>
    <h3>${flag} ${ship.display_name}</h3>
    <p class="ship-lead">${ship.lead_sentence}</p>
    <dl class="ship-detail-dl">
      <dt>Destination</dt><dd>${ship.destination_display || ship.destination_raw || "—"}</dd>
      <dt>ETA</dt><dd>${ship.eta_malta ? `${ship.eta_malta}${ship.eta_malta_stale ? " (out of date)" : ""} Malta` : "—"}</dd>
      <dt>Signals</dt><dd>${ship.level_db != null ? ship.level_db.toFixed(1) + " dB" : "—"} · ${ship.message_count ?? 0} msgs</dd>
    </dl>
    <a class="mmsi-link" href="https://www.vesselfinder.com/?mmsi=${ship.mmsi}" rel="noopener noreferrer" target="_blank">Look up MMSI (external)</a>
  `;
  $("#drawerClose")?.addEventListener("click", () => selectShip(null));
}

function shipFromSnapshot(mmsi) {
  if (mmsi == null) return null;
  return (state.snapshot?.ships || []).find((s) => s.mmsi === mmsi) || null;
}

function isNarrowViewport() {
  return (document.documentElement.clientWidth || 800) < 720;
}

function refreshSelectedShipPanels() {
  const ship = shipFromSnapshot(state.selectedMmsi);
  if (!state.selectedMmsi || !ship) {
    if (!state.selectedMmsi) {
      renderSheet(null);
      renderDrawer(null);
    }
    renderFollowCard();
    return;
  }
  if (isNarrowViewport()) {
    renderDrawer(null);
    renderSheet(ship);
  } else {
    renderSheet(null);
    renderDrawer(ship);
  }
  renderFollowCard();
}

function renderFollowCard() {
  const el = $("#mapFollowCard");
  if (!el) return;
  if (!state.follow) {
    el.hidden = true;
    el.innerHTML = "";
    return;
  }
  el.hidden = false;
  if (state.follow.kind === "ship") {
    const ship = shipFromSnapshot(state.follow.id);
    if (!ship) return;
    el.innerHTML = `<p><strong>Following ${ship.display_name}</strong></p>
      <p class="ship-lead">${ship.lead_sentence || ""}</p>
      <button type="button" class="btn-stop-follow" id="stopFollowBtn">Stop following</button>`;
    $("#stopFollowBtn")?.addEventListener("click", () => selectShip(null));
    return;
  }
  const plane = (state.sky?.adsb?.aircraft || []).find((p) => p.id === state.follow.id);
  if (!plane) return;
  el.innerHTML = `${provenanceBadge(plane)}
    <p><strong>Following ${plane.display_name}</strong> — tap again or press Esc to stop.</p>
    <p class="mono muted">${plane.altitude_ft != null ? `${Math.round(plane.altitude_ft)} ft` : "—"} · squawk ${plane.squawk || "—"}</p>
    ${plane.squawk_note ? `<p class="squawk-alert calm">${plane.squawk_note}</p>` : ""}`;
}

function satelliteTracksForMap(sky) {
  return (sky?.satellites?.satellites || []).map((s) => ({
    id: s.norad,
    coordinates: s.ground_track || [],
  }));
}

async function selectShip(mmsi) {
  if (mmsi && state.follow?.kind === "ship" && state.follow.id === mmsi) {
    state.follow = null;
    mmsi = null;
  } else if (mmsi) {
    state.follow = { kind: "ship", id: mmsi };
    state.selectedPlaneId = null;
  } else {
    state.follow = null;
  }
  state.selectedMmsi = mmsi;
  renderShipList(state.snapshot);
  if (state.map) {
    state.map.update({
      ships: state.snapshot?.ships,
      baseStations: state.snapshot?.base_stations,
      paths: state.snapshot?.paths,
      planes: state.sky?.adsb?.aircraft,
      satelliteTracks: satelliteTracksForMap(state.sky?.satellites),
      selectedMmsi: mmsi,
      selectedPlaneId: state.selectedPlaneId,
      follow: state.follow,
    });
    if (mmsi && !state.follow) state.map.focusShip(mmsi);
  }
  if (!mmsi) {
    refreshSelectedShipPanels();
    return;
  }
  if (shipFromSnapshot(mmsi)) {
    refreshSelectedShipPanels();
    return;
  }
  try {
    const res = await fetch(`/api/live-ais/ships/${mmsi}`);
    if (res.ok) {
      const detail = await res.json();
      if (isNarrowViewport()) {
        renderDrawer(null);
        renderSheet(detail);
      } else {
        renderSheet(null);
        renderDrawer(detail);
      }
      renderFollowCard();
    }
  } catch {
    refreshSelectedShipPanels();
  }
}

async function selectPlane(id) {
  if (id && state.follow?.kind === "plane" && state.follow.id === id) {
    state.follow = null;
    id = null;
  } else if (id) {
    state.follow = { kind: "plane", id };
    state.selectedMmsi = null;
  } else {
    state.follow = null;
  }
  state.selectedPlaneId = id;
  renderPlanesPanel(state.sky?.adsb);
  renderFollowCard();
  state.map?.update({
    ships: state.snapshot?.ships,
    baseStations: state.snapshot?.base_stations,
    paths: state.snapshot?.paths,
    planes: state.sky?.adsb?.aircraft,
    satelliteTracks: satelliteTracksForMap(state.sky?.satellites),
    selectedMmsi: state.selectedMmsi,
    selectedPlaneId: id,
    follow: state.follow,
  });
}

function timelineItemHtml(e) {
  const t = e.ts_utc ? formatMaltaTimeShort(e.ts_utc) : "—";
  const kind = e.kind || "";
  const cls = kind.startsWith("receiver")
    ? "timeline-receiver"
    : kind.startsWith("pattern_")
      ? "timeline-pattern"
      : kind.includes("silent")
        ? "timeline-quiet"
        : "timeline-live";
  const tsAttr = e.ts_utc ? ` data-ts="${e.ts_utc}"` : "";
  return `<li class="${cls}"${tsAttr}><span class="event-time mono">${t}</span> <span class="event-body">${e.sentence}</span></li>`;
}

async function renderActivityStrip() {
  const strip = $("#activityStrip");
  if (!strip) return;
  try {
    const res = await fetch(`/api/live-ais/activity?hours=${state.activityHours}`);
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    const buckets = data.buckets || [];
    const max = Math.max(...buckets.map((b) => b.vessels_total ?? 0), 1);
    strip.innerHTML = buckets
      .map((b) => {
        const n = b.vessels_total ?? 0;
        const h = n ? Math.max(8, Math.round((n / max) * 100)) : 2;
        const types = Object.entries(b.by_type || {})
          .map(([k, v]) => `${k}:${v}`)
          .join(", ");
        return `<span class="activity-bar" style="height:${h}%" title="${b.hour_utc}: ${n} vessels (${types || "—"})"></span>`;
      })
      .join("");
  } catch {
    strip.innerHTML = "";
  }
}

export async function renderLiveEvents(append = false) {
  const ol = $("#timeline");
  const moreBtn = $("#timelineMore");
  if (!ol) return;
  try {
    if (!append) timelineState.nextBefore = null;
    const qs = new URLSearchParams({
      hours: String(timelineState.hours),
      limit: "20",
    });
    if (append && timelineState.nextBefore) qs.set("before", timelineState.nextBefore);
    const res = await fetch(`/api/live-ais/events?${qs}`);
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    if (!append) await renderActivityStrip();
    const events = data.events || [];
    const html = events.length ? events.map(timelineItemHtml).join("") : "<li class='muted'>No live events logged yet.</li>";
    if (append) ol.innerHTML += html;
    else ol.innerHTML = html;
    timelineState.nextBefore = data.next_before || null;
    if (moreBtn) {
      moreBtn.hidden = !data.has_more;
      moreBtn.disabled = false;
    }
  } catch {
    if (!append) ol.innerHTML = "<li class='muted'>Could not load live event log.</li>";
  }
}

function setupTimelinePaging() {
  $("#timelineMore")?.addEventListener("click", () => renderLiveEvents(true));
  document.querySelectorAll(".activity-window").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".activity-window").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.activityHours = Number(btn.getAttribute("data-activity-hours")) || 24;
      renderActivityStrip();
    });
  });
}

function setupEntitySearch() {
  const input = $("#entitySearch");
  if (!input) return;
  input.addEventListener("input", () => {
    state.entityQuery = input.value.trim().toLowerCase();
    renderShipList(state.snapshot);
    const planes = state.sky?.adsb?.aircraft || [];
    const panel = $("#planesPanel");
    if (panel && planes.length) {
      const filtered = planes.filter((p) => matchesEntityQuery(p, state.entityQuery));
      renderPlanesPanel({ ...state.sky.adsb, aircraft: filtered });
    }
  });
}

function renderHeardAndHealth(snapshot, feedHealth) {
  const badgeEl = $("#heardBadge");
  const healthEl = $("#feedHealthRow");
  const merged = {
    ...(snapshot?.heard_badge || {}),
    count: (feedHealth?.heard_badge?.count ?? snapshot?.heard_badge?.count) || 0,
    bands: feedHealth?.heard_badge?.bands || snapshot?.heard_badge?.bands,
    label: "Heard by my antenna, last 60 s",
  };
  if (badgeEl) badgeEl.innerHTML = heardAntennaBadge(merged);
  if (healthEl && feedHealth) {
    healthEl.innerHTML = [feedHealth.ais, feedHealth.adsb].map((h) => feedHealthChip(h)).join("");
  }
}

async function renderMaltaWeather() {
  const el = $("#maltaWeather");
  if (!el) return;
  try {
    const res = await fetch("/api/malta/weather");
    if (!res.ok) throw new Error(String(res.status));
    const w = await res.json();
    const flags = w.flags || {};
    const flag = flags.medican_watch ? "Medicane watch" : flags.gale ? "Gale" : "";
    el.innerHTML = `<p class="malta-weather-text">${w.plain_english || "—"}</p>
      ${flag ? `<p class="weather-flag">${flag}</p>` : ""}
      <p class="muted small weather-attrib">${w.attribution || ""}</p>`;
  } catch {
    el.innerHTML = "<p class='muted'>Weather unavailable.</p>";
  }
}

function renderStationLive(snapshot) {
  const dl = $("#stationLive");
  if (!dl || !snapshot?.receiver_health) return;
  const h = snapshot.receiver_health;
  const run =
    h.run_time_sec != null
      ? `${Math.floor(h.run_time_sec / 3600)}h ${Math.floor((h.run_time_sec % 3600) / 60)}m`
      : "—";
  const items = [
    ["Status", h.state_label || (snapshot.online ? "Live" : "Offline")],
    ["Coverage", h.coverage_label || h.coverage || "—"],
    ["Hardware", h.hardware || "—"],
    ["AIS-catcher", h.build_version || "—"],
    ["Uptime", run],
    ["Msg rate", h.msg_rate != null ? `${(h.msg_rate * 60).toFixed(1)}/min` : "—"],
    ["Vessels tracked", h.vessel_count ?? "—"],
    ["SDR", (h.device_label || []).join(", ") || "—"],
  ];
  dl.innerHTML = items.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");
}

async function pollLive() {
  try {
    const healthP = fetch("/api/feed-health").catch(() => null);
    const res = await fetch("/api/live-ais/snapshot");
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    state.snapshot = data;
    ensureMap();
    setMapListening(false);
    state.map?.setReceiver({ ...data.receiver, label: data.receiver?.label });
    state.map?.update({
      ships: (isReplayActive() ? replayShipsNow() : null) || data.ships,
      baseStations: data.base_stations,
      paths: data.paths,
      planes: state.sky?.adsb?.aircraft,
      satelliteTracks: satelliteTracksForMap(state.sky?.satellites),
      selectedMmsi: state.selectedMmsi,
      selectedPlaneId: state.selectedPlaneId,
      follow: state.follow,
      replayMode: isReplayActive(),
    });
    renderShipList(data);
    const healthRes = await healthP;
    const feedHealth = healthRes && healthRes.ok ? await healthRes.json() : null;
    renderHeardAndHealth(data, feedHealth);
    await renderMaltaWeather();
    renderHeader(data);
    renderSummary(data);
    const fcEl = $("#freshnessCounts");
    if (fcEl && data.freshness_counts) {
      fcEl.textContent = `${data.freshness_counts.now} now · ${data.freshness_counts.today} today`;
    }
    renderShipList(data);
    state.sky = await fetchSkySnapshots();
    const planes = state.sky?.adsb?.aircraft || [];
    const planesView = state.entityQuery
      ? planes.filter((p) => matchesEntityQuery(p, state.entityQuery))
      : planes;
    renderPlanesPanel({ ...state.sky.adsb, aircraft: planesView });
    renderSatellitesPanel(state.sky.satellites);
    $("#planesPanel")?.querySelectorAll(".live-plane-card").forEach((li) => {
      li.addEventListener("click", () => selectPlane(li.getAttribute("data-plane-id")));
    });
    state.map?.setReceiver({ ...data.receiver, label: data.receiver?.label });
    const replayShips = isReplayActive() ? replayShipsNow() : null;
    const shipsForMap = replayShips || data.ships;
    state.map?.update({
      ships: shipsForMap,
      baseStations: data.base_stations,
      paths: data.paths,
      planes: state.sky?.adsb?.aircraft,
      satelliteTracks: satelliteTracksForMap(state.sky?.satellites),
      selectedMmsi: state.selectedMmsi,
      selectedPlaneId: state.selectedPlaneId,
      follow: state.follow,
      replayMode: Boolean(replayShips),
    });
    refreshSelectedShipPanels();
    renderStationLive(data);
    await renderLiveEvents();
  } catch {
    renderHeader({ online: false, freshness_counts: { now: 0, today: 0 } });
  }
}

function initHarbourSheetDrag() {
  const sheet = $("#harbourShipSheet");
  const grab = sheet?.querySelector(".sheet-grab");
  if (!sheet || !grab) return;
  let startY = 0;
  let startH = 0;
  const onMove = (clientY) => {
    const dy = startY - clientY;
    const next = Math.max(120, Math.min(window.innerHeight * 0.72, startH + dy));
    sheet.style.setProperty("--sheet-height", `${next}px`);
  };
  grab.addEventListener("pointerdown", (ev) => {
    grab.setPointerCapture(ev.pointerId);
    startY = ev.clientY;
    startH = sheet.getBoundingClientRect().height;
  });
  grab.addEventListener("pointermove", (ev) => {
    if (!grab.hasPointerCapture(ev.pointerId)) return;
    onMove(ev.clientY);
  });
  grab.addEventListener("pointerup", (ev) => grab.releasePointerCapture(ev.pointerId));
}

function refreshMapFromState() {
  const replayShips = isReplayActive() ? replayShipsNow() : null;
  state.map?.update({
    ships: replayShips || state.snapshot?.ships,
    baseStations: state.snapshot?.base_stations,
    paths: state.snapshot?.paths,
    planes: state.sky?.adsb?.aircraft,
    satelliteTracks: satelliteTracksForMap(state.sky?.satellites),
    selectedMmsi: state.selectedMmsi,
    selectedPlaneId: state.selectedPlaneId,
    follow: state.follow,
    replayMode: Boolean(replayShips),
  });
}

function ensureMap() {
  if (!state.map) {
      const host = $("#harbourMap");
      if (host) {
        state.map = new HarbourMap(host);
                state.map.onSelect((mmsi) => selectShip(mmsi));
        state.map.onPlaneSelect((id) => selectPlane(id));
        initWatchZones(state.map, {
          drawBtn: $("#watchZoneDraw"),
          status: $("#watchZoneStatus"),
          nameInput: $("#watchZoneName"),
        });
        $("#harbourMap")?.addEventListener("wichita-wall-mode", (ev) => {
          state.map?.setWallMode(Boolean(ev.detail?.on));
        });
      }
    }
}

function setMapListening(on) {
  const col = document.querySelector('.harbour-map-col');
  if (col) col.classList.toggle('map-listening', on);
}

export function initLiveAis() {
  setMapListening(true);
  ensureMap();
  setupTimelinePaging();
  setupEntitySearch();
  initHarbourSheetDrag();
  initIncidentReplay();
  pollLive().then(() => {
    initHarbourReplay(
      () => refreshMapFromState(),
      () => pollLive(),
    );
  });
  if (state.timer) clearInterval(state.timer);
  state.timer = setInterval(pollLive, 5000);
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && state.follow) {
      state.follow = null;
      state.selectedMmsi = null;
      state.selectedPlaneId = null;
      renderFollowCard();
      renderShipList(state.snapshot);
      renderPlanesPanel(state.sky?.adsb);
      state.map?.clearFollow();
      state.map?.update({
        ships: state.snapshot?.ships,
        baseStations: state.snapshot?.base_stations,
        paths: state.snapshot?.paths,
        planes: state.sky?.adsb?.aircraft,
        satelliteTracks: satelliteTracksForMap(state.sky?.satellites),
        selectedMmsi: null,
        selectedPlaneId: null,
        follow: null,
      });
    }
  });
}
