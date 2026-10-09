import { formatMalta, formatMaltaTimeShort } from "./time_malta.js";
import { HarbourMap, typeColor } from "./harbour_map.js";

const GROUPS = [
  { key: "now", title: "Heard now" },
  { key: "recent", title: "Recently" },
  { key: "earlier", title: "Earlier today" },
];

const state = {
  snapshot: null,
  selectedMmsi: null,
  map: null,
  timer: null,
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

function renderHeader(snapshot) {
  const live = $("#headerLive");
  if (!live) return;
  if (!snapshot) {
    live.textContent = "Checking AIS…";
    return;
  }
  const fc = snapshot.freshness_counts || {};
  const dot = snapshot.online ? "live" : "offline";
  live.innerHTML = `<span class="pill pill-${dot}">${snapshot.online ? "Live" : "Offline"}</span>
    <span class="header-ship-count">${fc.now ?? 0} ships now · ${fc.today ?? 0} today</span>`;
}

function renderSummary(snapshot) {
  const el = $("#harbourSummary");
  if (!el || !snapshot) return;
  el.innerHTML = `<p class="harbour-summary-text">${snapshot.summary || ""}</p>
    <div class="summary-tiles">
      <div><span class="summary-num">${snapshot.freshness_counts?.now ?? 0}</span><span class="muted">Moving / nearby now</span></div>
      <div><span class="summary-num">${countMoored(snapshot.ships)}</span><span class="muted">Moored or slow</span></div>
    </div>`;
}

function countMoored(ships) {
  return (ships || []).filter(
    (s) => (s.speed_kn || 0) < 0.5 && (s.freshness === "now" || s.freshness === "recent"),
  ).length;
}

function shipCardHtml(s, selected) {
  const flag = flagEmoji(s.country);
  const col = typeColor(s.shiptype_category);
  const eta = s.eta_malta ? `ETA ${s.eta_malta} Malta` : "";
  const fade = s.freshness === "earlier" ? " ship-card-fade" : "";
  const sel = s.mmsi === selected ? " selected" : "";
  return `<li class="live-ship-card${fade}${sel}" data-mmsi="${s.mmsi}" role="button" tabindex="0" style="--ship-type-color:${col}">
    <div class="live-ship-card-head">
      <span class="ship-type-icon" aria-hidden="true"></span>
      <span class="live-ship-flag" title="${s.country || ""}">${flag}</span>
      <strong>${s.display_name}</strong>
      <span class="mono muted ship-fresh">${agoLabel(s.last_signal_s)}</span>
    </div>
    <p class="ship-lead">${s.lead_sentence}</p>
    <p class="muted ship-meta">${s.shiptype_label}${eta ? ` · ${eta}` : ""}</p>
    <details class="ship-raw-details"><summary>Details</summary>
      <p class="mono muted">MMSI ${s.mmsi_display}${s.callsign ? ` · ${s.callsign}` : ""}</p>
      <p class="mono muted">${s.destination_raw || "—"} · ${s.message_count ?? 0} msgs · ${s.level_db != null ? s.level_db.toFixed(0) + " dB" : "—"}</p>
    </details>
  </li>`;
}

function renderShipList(snapshot) {
  const ul = $("#liveShipList");
  if (!ul) return;
  const ships = snapshot?.ships || [];
  if (!ships.length) {
    ul.innerHTML = "<li class='muted'>No vessels in the AIS window.</li>";
    return;
  }
  const byGroup = new Map(GROUPS.map((g) => [g.key, []]));
  for (const s of ships) {
    const k = s.freshness || "earlier";
    (byGroup.get(k) || byGroup.get("earlier")).push(s);
  }
  ul.innerHTML = GROUPS
    .map((g) => {
      const list = byGroup.get(g.key) || [];
      if (!list.length) return "";
      return `<li class="ship-group-label">${g.title}</li>${list.map((s) => shipCardHtml(s, state.selectedMmsi)).join("")}`;
    })
    .join("");
  ul.querySelectorAll(".live-ship-card").forEach((li) => {
    const mmsi = Number(li.getAttribute("data-mmsi"));
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
    return;
  }
  const flag = flagEmoji(ship.country);
  sheet.hidden = false;
  backdrop.hidden = false;
  sheet.classList.add("open");
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
      <dt>ETA</dt><dd>${ship.eta_malta ? ship.eta_malta + " Malta" : "—"}</dd>
      <dt>Signals</dt><dd>${ship.level_db != null ? ship.level_db.toFixed(1) + " dB" : "—"} · ${ship.message_count ?? 0} msgs</dd>
    </dl>
    <a class="mmsi-link" href="https://www.vesselfinder.com/?mmsi=${ship.mmsi}" rel="noopener noreferrer" target="_blank">Look up MMSI (external)</a>
  `;
  $("#drawerClose")?.addEventListener("click", () => selectShip(null));
}

async function selectShip(mmsi) {
  state.selectedMmsi = mmsi;
  const ship = mmsi ? (state.snapshot?.ships || []).find((s) => s.mmsi === mmsi) : null;
  renderShipList(state.snapshot);
  if (state.map) {
    state.map.update({
      ships: state.snapshot?.ships,
      baseStations: state.snapshot?.base_stations,
      paths: state.snapshot?.paths,
      selectedMmsi: mmsi,
    });
    if (mmsi) state.map.focusShip(mmsi);
  }
  const narrow = (document.documentElement.clientWidth || 800) < 720;
  if (narrow) renderSheet(ship);
  else renderDrawer(ship);
  if (mmsi && ship) return;
  if (mmsi) {
    try {
      const res = await fetch(`/api/live-ais/ships/${mmsi}`);
      if (res.ok) {
        const detail = await res.json();
        if (narrow) renderSheet(detail);
        else renderDrawer(detail);
      }
    } catch {
      /* keep card */
    }
  }
}

export async function renderLiveEvents() {
  const ol = $("#timeline");
  const strip = $("#activityStrip");
  if (!ol) return;
  try {
    const res = await fetch("/api/live-ais/events?hours=24");
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    if (strip && data.activity_hourly?.length) {
      const max = Math.max(...data.activity_hourly.map((b) => b.new_ships), 1);
      strip.innerHTML = data.activity_hourly
        .map((b) => {
          const h = Math.round((b.new_ships / max) * 100);
          return `<span style="height:${h}%" title="${b.hour_utc}: ${b.new_ships} new"></span>`;
        })
        .join("");
    }
    const events = data.events || [];
    ol.innerHTML = events.length
      ? events
          .map((e) => {
            const t = e.ts_utc ? formatMaltaTimeShort(e.ts_utc) : "—";
            return `<li class="timeline-live"><span class="badge badge-live">Live</span> <span class="event-time mono">${t}</span> ${e.sentence}</li>`;
          })
          .join("")
      : "<li class='muted'>No live events logged yet.</li>";
  } catch {
    ol.innerHTML = "<li class='muted'>Could not load live event log.</li>";
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
    ["Status", snapshot.online ? "Live" : "Offline"],
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
    const res = await fetch("/api/live-ais/snapshot");
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    state.snapshot = data;
    renderHeader(data);
    renderSummary(data);
    const fcEl = $("#freshnessCounts");
    if (fcEl && data.freshness_counts) {
      fcEl.textContent = `${data.freshness_counts.now} now · ${data.freshness_counts.today} today`;
    }
    renderShipList(data);
    if (!state.map) {
      const host = $("#harbourMap");
      if (host) {
        state.map = new HarbourMap(host);
        state.map.setReceiver({ ...data.receiver, label: data.receiver?.label });
        state.map.onSelect((mmsi) => selectShip(mmsi));
      }
    }
    state.map?.setReceiver({ ...data.receiver, label: data.receiver?.label });
    state.map?.update({
      ships: data.ships,
      baseStations: data.base_stations,
      paths: data.paths,
      selectedMmsi: state.selectedMmsi,
    });
    renderStationLive(data);
    await renderLiveEvents();
  } catch {
    renderHeader({ online: false, freshness_counts: { now: 0, today: 0 } });
  }
}

export function initLiveAis() {
  pollLive();
  if (state.timer) clearInterval(state.timer);
  state.timer = setInterval(pollLive, 5000);
}
