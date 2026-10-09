import { formatMalta } from "./time_malta.js";

const HARBOUR_BOUNDS = {
  latMin: 35.888,
  latMax: 35.912,
  lonMin: 14.492,
  lonMax: 14.52,
};

const state = {
  seenMmsi: new Set(),
  liveTimeline: [],
  ships: [],
  paths: null,
  status: null,
  selectedMmsi: null,
  timer: null,
};

function $(sel) {
  return document.querySelector(sel);
}

function flagEmoji(iso2) {
  if (!iso2 || iso2.length !== 2) return "";
  const u = iso2.toUpperCase();
  return String.fromCodePoint(
    ...[...u].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65),
  );
}

function projectHarbour(lat, lon) {
  const { latMin, latMax, lonMin, lonMax } = HARBOUR_BOUNDS;
  const x = 12 + ((lon - lonMin) / (lonMax - lonMin)) * 176;
  const y = 188 - ((lat - latMin) / (latMax - latMin)) * 176;
  return { x, y };
}

function agoLabel(lastSignalS) {
  if (lastSignalS == null) return "—";
  if (lastSignalS < 60) return `${Math.round(lastSignalS)} s ago`;
  return `${Math.round(lastSignalS / 60)} min ago`;
}

function describeNewShip(ship) {
  const bits = [ship.display_name];
  if (ship.shiptype_label && ship.shiptype_label !== "not available") {
    bits.push(`(${ship.shiptype_label})`);
  }
  if (ship.destination) {
    bits.push(`heading ${ship.destination}`);
  }
  return `New ship heard: ${bits.join(", ")}`;
}

function renderLiveStrip(status) {
  const el = $("#liveAisStrip");
  if (!el) return;
  if (!status) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  const dot = status.online ? "live" : "offline";
  const mpm = status.messages_per_min != null ? status.messages_per_min.toFixed(1) : "—";
  const last = status.last_message_utc ? formatMalta(status.last_message_utc) : "—";
  el.innerHTML = `
    <span class="live-strip-label">Live AIS</span>
    <span class="pill pill-${dot}">${status.online ? "Receiver live" : "Receiver offline"}</span>
    <span>${mpm} msg/min</span>
    <span>${status.ships_in_last_hour ?? 0} ships (last hour)</span>
    <span class="muted">Last message ${last}</span>
  `;
}

function renderHarbourMap(ships, paths, selectedMmsi) {
  const container = $("#harbourMap");
  if (!container) return;
  const grid = [];
  for (let i = 0; i <= 8; i++) {
    const p = i * 25;
    grid.push(`<line x1="${p}" y1="0" x2="${p}" y2="200" stroke="#1a2030" stroke-width="0.5"/>`);
    grid.push(`<line x1="0" y1="${p}" x2="200" y2="${p}" stroke="#1a2030" stroke-width="0.5"/>`);
  }
  const pathLines = (paths?.features || [])
    .map((f) => {
      const coords = f.geometry?.coordinates || [];
      if (!coords.length) return "";
      const pts = coords
        .map(([lon, lat]) => {
          const { x, y } = projectHarbour(lat, lon);
          return `${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(" ");
      return `<polyline points="${pts}" fill="none" stroke="#3ec6c9" stroke-width="1" opacity="0.55"/>`;
    })
    .join("");
  const dots = ships
    .filter((s) => s.lat != null && s.lon != null)
    .map((s) => {
      const { x, y } = projectHarbour(s.lat, s.lon);
      const sel = s.mmsi === selectedMmsi ? " ship-dot-selected" : "";
      const r = s.is_base_station ? 7 : 5;
      return `<g class="ship-dot${sel}" data-mmsi="${s.mmsi}" role="button" tabindex="0">
        <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r}" fill="#3ec6c9" fill-opacity="0.9"/>
      </g>`;
    })
    .join("");
  container.innerHTML = `<svg viewBox="0 0 200 200" width="100%" height="100%" class="harbour-svg" role="img" aria-label="Live ship positions, local schematic">
    <rect width="200" height="200" fill="#0a0c10"/>
    ${grid.join("")}
    <path d="M 20 145 C 45 75, 100 50, 155 95 L 175 145 C 140 175, 60 180, 20 145 Z" fill="#121820" stroke="#2a3344" stroke-width="1"/>
    <text x="8" y="16" fill="#9aa3b2" font-size="8" font-family="Geist Sans, sans-serif">Malta · live positions (schematic)</text>
    ${pathLines}
    ${dots}
  </svg>`;
  container.querySelectorAll(".ship-dot").forEach((g) => {
    const mmsi = Number(g.getAttribute("data-mmsi"));
    g.addEventListener("click", () => selectShip(mmsi));
    g.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        selectShip(mmsi);
      }
    });
  });
}

function renderShipCards(ships) {
  const ul = $("#liveShipList");
  if (!ul) return;
  const sorted = [...ships].sort(
    (a, b) => (a.last_signal_s ?? 1e9) - (b.last_signal_s ?? 1e9),
  );
  if (!sorted.length) {
    ul.innerHTML = "<li class='muted'>No ships in the last AIS-catcher window.</li>";
    return;
  }
  ul.innerHTML = sorted
    .map((s) => {
      const flag = flagEmoji(s.country);
      const spd = s.speed_kn != null ? `${s.speed_kn} kn` : "—";
      const crs = s.cog_deg != null ? `${Math.round(s.cog_deg)}°` : "—";
      const lvl = s.level_db != null ? `${s.level_db.toFixed(0)} dB` : "—";
      const eta = s.eta ? `ETA ${s.eta}` : "";
      const dest = s.destination ? s.destination : "—";
      const sel = s.mmsi === state.selectedMmsi ? " selected" : "";
      return `<li class="live-ship-card${sel}" data-mmsi="${s.mmsi}" role="button" tabindex="0">
        <div class="live-ship-card-head">
          <span class="live-ship-flag" aria-hidden="true">${flag}</span>
          <strong>${s.display_name}</strong>
          <span class="mono muted">${agoLabel(s.last_signal_s)}</span>
        </div>
        <p class="muted">${s.shiptype_label} · ${dest}${eta ? ` · ${eta}` : ""}</p>
        <p class="mono">${spd} · course ${crs} · ${lvl} · ${s.message_count ?? 0} msgs</p>
      </li>`;
    })
    .join("");
  ul.querySelectorAll(".live-ship-card").forEach((li) => {
    const mmsi = Number(li.getAttribute("data-mmsi"));
    li.addEventListener("click", () => selectShip(mmsi));
    li.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        selectShip(mmsi);
      }
    });
  });
}

function renderShipDetail(ship) {
  const el = $("#liveShipDetail");
  if (!el) return;
  if (!ship) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  const flag = flagEmoji(ship.country);
  el.innerHTML = `
    <h3>${flag} ${ship.display_name}</h3>
    <p class="mono muted">MMSI ${ship.mmsi_display}${ship.callsign ? ` · ${ship.callsign}` : ""}</p>
    <dl class="ship-detail-dl">
      <dt>Type</dt><dd>${ship.shiptype_label}</dd>
      <dt>Destination</dt><dd>${ship.destination || "—"}</dd>
      <dt>ETA</dt><dd>${ship.eta || "—"}</dd>
      <dt>Speed / course</dt><dd>${ship.speed_kn ?? "—"} kn · ${ship.cog_deg != null ? Math.round(ship.cog_deg) + "°" : "—"}</dd>
      <dt>Signal</dt><dd>${ship.level_db != null ? ship.level_db.toFixed(1) + " dB" : "—"}</dd>
      <dt>Messages</dt><dd>${ship.message_count ?? "—"}</dd>
      <dt>Last heard</dt><dd>${agoLabel(ship.last_signal_s)} (${ship.last_heard_utc ? formatMalta(ship.last_heard_utc) : "—"})</dd>
    </dl>
    <button type="button" class="detail-close" id="liveShipDetailClose">Close</button>
  `;
  $("#liveShipDetailClose")?.addEventListener("click", () => selectShip(null));
}

async function selectShip(mmsi) {
  state.selectedMmsi = mmsi;
  renderHarbourMap(state.ships, state.paths, mmsi);
  renderShipCards(state.ships);
  if (!mmsi) {
    renderShipDetail(null);
    return;
  }
  const local = state.ships.find((s) => s.mmsi === mmsi);
  if (local) renderShipDetail(local);
  try {
    const res = await fetch(`/api/live-ais/ships/${mmsi}`);
    if (res.ok) renderShipDetail(await res.json());
  } catch {
    /* keep local card */
  }
}

function mergeLiveTimeline(ships) {
  const now = new Date().toISOString();
  for (const s of ships) {
    if (state.seenMmsi.has(s.mmsi)) continue;
    state.seenMmsi.add(s.mmsi);
    if (s.is_base_station) continue;
    state.liveTimeline.unshift({
      kind: "live_new_ship",
      title: describeNewShip(s),
      detail: "Live AIS from balcony receiver",
      time_utc: s.last_heard_utc || now,
      source: "live",
    });
  }
  state.liveTimeline = state.liveTimeline.slice(0, 40);
}

export function getLiveTimelineEvents() {
  return state.liveTimeline;
}

export function renderLiveTimelineSection(captureEvents, renderFn) {
  if (typeof renderFn === "function") {
    renderFn(captureEvents, state.liveTimeline);
  }
}

async function pollLive(onCaptureTimeline) {
  try {
    const res = await fetch("/api/live-ais/snapshot");
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    state.status = data;
    state.ships = data.ships || [];
    state.paths = data.paths;
    mergeLiveTimeline(state.ships);
    renderLiveStrip(data);
    renderHarbourMap(state.ships, state.paths, state.selectedMmsi);
    renderShipCards(state.ships);
    const heading = $("#harbour-heading");
    if (heading) heading.textContent = data.online ? "AIS · Live" : "AIS · offline";
    const counts = $("#aisCounts");
    if (counts) {
      counts.textContent = data.online
        ? `Live · ${data.ship_count} ship(s) on air`
        : "Live receiver offline";
    }
    if (onCaptureTimeline) onCaptureTimeline();
  } catch {
    renderLiveStrip({ online: false, messages_per_min: null, ships_in_last_hour: 0 });
  }
}

export function initLiveAis(onCaptureTimeline) {
  pollLive(onCaptureTimeline);
  if (state.timer) clearInterval(state.timer);
  state.timer = setInterval(() => pollLive(onCaptureTimeline), 5000);
}
