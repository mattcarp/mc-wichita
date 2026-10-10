import { formatMaltaTimeShort } from "./time_malta.js?v=20261010-01";

const RECEIVER_LABELS = {
  live: "Live",
  stale: "Stale feed",
  quiet: "Quiet — no contacts",
  unreachable: "Unreachable",
  invalid: "Invalid feed",
};

export function receiverStatePill(health) {
  if (!health) return "";
  const state = health.state || "unreachable";
  const badge = health.badge || {};
  const band = badge.band || health.band || "";
  const src = badge.source || health.source || "our_antenna";
  const title = `${RECEIVER_LABELS[state] || state} · ${band} · ${src}`;
  return `<span class="receiver-pill receiver-${state}" title="${title}">${badge.label || RECEIVER_LABELS[state] || state}</span>`;
}

export async function renderMaltaWeather(host) {
  if (!host) return;
  try {
    const res = await fetch("/api/gev/weather/malta");
    const data = await res.json();
    if (!data.ok) {
      host.innerHTML = `<p class="muted">Weather unavailable right now.</p>`;
      return;
    }
    const flags = [];
    if (data.gale_warning) flags.push('<span class="flag-warn">Gale conditions possible</span>');
    if (data.medicane_watch) flags.push('<span class="flag-warn">Medicane watch — extreme wind</span>');
    host.innerHTML = `
      <p>${data.wind_plain}</p>
      <p class="muted">${data.sea_plain}</p>
      ${flags.join(" ")}
      <p class="weather-attrib muted">${data.attribution}</p>`;
  } catch {
    host.innerHTML = `<p class="muted">Weather unavailable.</p>`;
  }
}

export async function loadWatchZones(map) {
  try {
    const res = await fetch("/api/gev/watch-zones");
    const data = await res.json();
    map?.setWatchZones?.(data.zones || []);
  } catch {
    /* ignore */
  }
}

export function initWatchZoneDraw(map) {
  const btn = document.querySelector("#watchZoneDraw");
  const status = document.querySelector("#watchZoneStatus");
  if (!btn || !map) return;
  let corners = [];
  btn.addEventListener("click", () => {
    corners = [];
    btn.classList.add("active");
    status.textContent = "Tap two corners on the map (south-west, then north-east).";
  });
  map.onMapClick?.((lat, lon) => {
    if (!btn.classList.contains("active")) return;
    corners.push([lat, lon]);
    if (corners.length < 2) return;
    btn.classList.remove("active");
    const [a, b] = corners;
    const polygon = [
      [Math.min(a[0], b[0]), Math.min(a[1], b[1])],
      [Math.min(a[0], b[0]), Math.max(a[1], b[1])],
      [Math.max(a[0], b[0]), Math.max(a[1], b[1])],
      [Math.max(a[0], b[0]), Math.min(a[1], b[1])],
    ];
    const name = window.prompt("Name this watch zone", "Harbour approach") || "Watch zone";
    fetch("/api/gev/watch-zones", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, polygon }),
    })
      .then((r) => r.json())
      .then(() => {
        status.textContent = `Saved zone “${name}”. Alerts appear in the Heard log.`;
        loadWatchZones(map);
      })
      .catch(() => {
        status.textContent = "Could not save watch zone.";
      });
  });
}

export async function initIncidentReplay() {
  const scrub = document.querySelector("#replayScrub");
  const label = document.querySelector("#replayLabel");
  const caveat = document.querySelector("#replayCaveat");
  if (!scrub || !label) return;
  try {
    const res = await fetch("/api/gev/replay/scene?hours=6");
    const scene = await res.json();
    if (caveat) caveat.textContent = scene.caveat || "";
    const beats = scene.beats || [];
    if (!beats.length) {
      label.textContent = "No heard events in this window yet.";
      scrub.hidden = true;
      return;
    }
    scrub.hidden = false;
    scrub.min = 0;
    scrub.max = String(beats.length - 1);
    scrub.value = "0";
    const renderBeat = (idx) => {
      const beat = beats[Number(idx)];
      if (!beat) return;
      label.innerHTML = `<span class="mono">${formatMaltaTimeShort(beat.ts_utc)}</span> — ${beat.sentence}`;
      window.dispatchEvent(
        new CustomEvent("wichita-replay-camera", { detail: beat.camera || scene.map_center }),
      );
    };
    scrub.addEventListener("input", () => renderBeat(scrub.value));
    renderBeat(0);
  } catch {
    label.textContent = "Replay unavailable.";
  }
}
