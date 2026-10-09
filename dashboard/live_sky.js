import { provenanceBadge } from "./entity_labels.js?v=20261009-23";

function $(sel) {
  return document.querySelector(sel);
}

export function renderPlanesPanel(adsb) {
  const el = $("#planesPanel");
  if (!el) return;
  if (!adsb) {
    el.innerHTML = "<p class='muted'>Checking ADS-B…</p>";
    return;
  }
  if (!adsb.receiver_connected) {
    el.innerHTML = `<p class="adsb-offline">${adsb.error || "Receiver not connected"}</p>
      <p class="muted small">Our readsb feed will appear here when the RTL-SDR is on 1090 MHz.</p>`;
    return;
  }
  const planes = adsb.aircraft || [];
  if (!planes.length) {
    el.innerHTML = `<p class="muted">No aircraft with position from our receiver right now.</p>
      <p class="prov-badge prov-stale">Heard by our antenna · Live</p>`;
    return;
  }
  el.innerHTML = `<p class="mono counts">${planes.length} aircraft with position</p>
    <ul class="live-plane-list">
      ${planes
        .map((p) => {
          const squawk = p.squawk_note
            ? `<p class="squawk-alert calm">${p.squawk_note}</p>`
            : "";
          return `<li class="live-plane-card" data-plane-id="${p.id}" role="button" tabindex="0">
            ${provenanceBadge(p)}
            <strong>${p.display_name}</strong>
            <span class="mono muted">${p.altitude_ft != null ? `${Math.round(p.altitude_ft)} ft` : "—"} · ${p.speed_kts != null ? `${Math.round(p.speed_kts)} kt` : "—"} · ${p.heading_deg != null ? `${Math.round(p.heading_deg)}°` : "—"}</span>
            ${p.squawk ? `<span class="mono muted">Squawk ${p.squawk}</span>` : ""}
            ${squawk}
          </li>`;
        })
        .join("")}
    </ul>`;
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
  const adsb = adsbRes.ok ? await adsbRes.json() : { receiver_connected: false, error: "ADS-B unavailable" };
  const satellites = satRes.ok ? await satRes.json() : { error: "Satellites unavailable" };
  return { adsb, satellites };
}
