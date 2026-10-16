import { plural, pluralWord } from "./plural.js?v=20261016-replay-voice";
import { provenanceBadge, feedHealthChip } from "./entity_labels.js?v=20261016-replay-voice";

function $(sel) {
  return document.querySelector(sel);
}

function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function agoShort(sec) {
  if (sec == null) return "—";
  const s = Math.max(0, Math.round(sec));
  if (s < 60) return `${s} s ago`;
  return `${Math.round(s / 60)} min ago`;
}

export function planeSourceBadge(p) {
  const src = p.source || "local antenna";
  const cls = src === "adsb.lol" ? "src-feed" : src === "local antenna" ? "src-local" : "src-both";
  return `<span class="plane-src ${cls}" data-test-id="plane-source">${esc(src)}</span>`;
}

export function planeSummaryLine(p) {
  const alt = p.altitude_ft != null ? `${Math.round(p.altitude_ft).toLocaleString("en")} ft` : "—";
  const gs = p.speed_kts != null ? `${Math.round(p.speed_kts)} kt` : "—";
  const hdg = p.heading_deg != null ? `${Math.round(p.heading_deg)}°` : "—";
  return `${alt} · ${gs} · ${hdg}`;
}

const openPlaneDetails = new Set();

export function renderPlanesPanel(adsb) {
  const el = $("#planesPanel");
  if (!el) return;
  if (!adsb) {
    el.innerHTML = "<p class='muted'>Checking aircraft feed…</p>";
    return;
  }
  const label = `<p class="mono small plane-feed-label" data-test-id="aircraft-source-label">${esc(adsb.source_label || "Aircraft: adsb.lol, community feed")}</p>`;
  if (adsb.feed_paused || !adsb.receiver_connected) {
    el.innerHTML = `${label}<p class="plane-feed-paused" role="status" data-test-id="aircraft-paused"><span class="pill pill-paused">Feed paused</span> ${esc(adsb.error || "Aircraft feed unreachable")}; retrying.</p>`;
    return;
  }
  const planes = adsb.aircraft || [];
  if (!planes.length) {
    el.innerHTML = `${label}<p class="muted">No aircraft with position right now.</p>`;
    return;
  }
  const em = planes.filter((p) => p.is_emergency).length;
  el.innerHTML = `${label}<p class="mono counts">${plural(planes.length, "aircraft")} with position${em ? ` · <span class="plane-em-count">${plural(em, "emergency", "emergencies")}</span>` : ""}</p>
    <p class="muted small observed-caveat">Observed ADS-B only — not ground truth.</p>
    <ul class="live-plane-list">
      ${planes
        .map((p) => {
          const emCls = p.is_emergency ? " plane-emergency" : "";
          const sub = [p.registration, p.type].filter(Boolean).map(esc).join(" · ");
          return `<li class="live-plane-card${emCls}" data-plane-id="${esc(p.id)}" role="button" tabindex="0">
            <div class="live-plane-head"><strong>${esc(p.display_name)}</strong>${planeSourceBadge(p)}</div>
            ${sub ? `<span class="mono muted">${sub}</span>` : ""}
            <span class="mono muted">${planeSummaryLine(p)}${p.squawk ? ` · squawk <span class="${p.is_emergency ? "plane-squawk-em" : ""}">${esc(p.squawk)}</span>` : ""}</span>
            ${p.squawk_note ? `<p class="squawk-alert${p.is_emergency ? " squawk-red" : " calm"}">${esc(p.squawk_note)}</p>` : ""}
            <details class="ship-raw-details plane-details"><summary class="expand-cue" aria-expanded="false"><span class="cue-tri" aria-hidden="true"></span><span class="cue-more">More details</span><span class="cue-less">Less</span><span class="sr-only"> for ${esc(p.display_name)}</span></summary>
              <p class="mono muted">Callsign ${esc(p.callsign || "—")} · ICAO ${esc((p.hex || "").toUpperCase())}</p>
              <p class="mono muted">Registration ${esc(p.registration || "—")} · type ${esc(p.type || "—")}${p.type_desc ? ` (${esc(p.type_desc)})` : ""}</p>
              <p class="mono muted">Altitude ${p.altitude_ft != null ? `${Math.round(p.altitude_ft).toLocaleString("en")} ft` : "—"} · speed ${p.speed_kts != null ? `${Math.round(p.speed_kts)} kt` : "—"} · heading ${p.heading_deg != null ? `${Math.round(p.heading_deg)}°` : "—"}</p>
              <p class="mono muted">Squawk ${esc(p.squawk || "—")} · emergency ${esc(p.emergency || "none")} · last seen ${agoShort(p.last_signal_s)}</p>
              <p class="mono muted">Source: ${esc(p.source || "—")}</p>
            </details>
          </li>`;
        })
        .join("")}
    </ul>`;
  el.querySelectorAll(".live-plane-card").forEach((li) => {
    const id = li.getAttribute("data-plane-id");
    const det = li.querySelector(".plane-details");
    if (!det) return;
    const sum = det.querySelector("summary");
    if (openPlaneDetails.has(id)) det.open = true;
    sum?.setAttribute("aria-expanded", String(det.open));
    det.addEventListener("toggle", () => {
      sum?.setAttribute("aria-expanded", String(det.open));
      if (det.open) openPlaneDetails.add(id);
      else openPlaneDetails.delete(id);
    });
    det.addEventListener("click", (ev) => ev.stopPropagation());
  });
}

export function renderSatellitesPanel(sky) {
  const el = $("#satellitesPanel");
  if (!el) return;
  if (!sky) {
    el.innerHTML = "<p class='muted'>Loading satellite passes…</p>";
    return;
  }
  if (sky.error) {
    el.innerHTML = `<p class="muted">${sky.error}</p>`;
    return;
  }
  const header = provenanceBadge(sky);
  const sats = [...(sky.satellites || [])].sort((a, b) => {
    const pa = (a.next_passes || [])[0]?.max_utc || "";
    const pb = (b.next_passes || [])[0]?.max_utc || "";
    return pa.localeCompare(pb);
  });
  if (!sats.length) {
    el.innerHTML = `${header}<p class="muted">No TLE data cached yet.</p>`;
    return;
  }
  el.innerHTML = `${header}
    <p class="muted small">Next passes over ${sky.observer?.label || "Valletta"} (max elevation). Times Europe/Malta.</p>
    <ul class="sat-pass-list">
      ${sats
        .map((s) => {
          const pass = (s.next_passes || [])[0];
          const inProg = s.pass_in_progress ? " · in progress" : "";
          const passLine = pass
            ? `${pass.max_time_malta} · ${pass.max_elevation_deg}° max${inProg}`
            : "No pass in the next 36 h";
          return `<li><strong>${s.name}</strong><span class="mono muted">${passLine}</span></li>`;
        })
        .join("")}
    </ul>`;
}

export async function fetchSkySnapshots() {
  const [adsbRes, satRes] = await Promise.all([
    fetch("/api/sky/adsb/snapshot"),
    fetch("/api/sky/satellites"),
  ]);
  const adsb = adsbRes.ok ? await adsbRes.json() : { receiver_connected: false, feed_paused: true, error: "Aircraft feed unavailable" };
  const satellites = satRes.ok ? await satRes.json() : { error: "Satellites unavailable" };
  return { adsb, satellites };
}
