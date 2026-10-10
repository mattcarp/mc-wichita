const V = "?v=20261010-gev1";

function $(sel) {
  return document.querySelector(sel);
}

export async function loadScene(tsUtc) {
  const res = await fetch(`/api/incident-replay/scene?ts_utc=${encodeURIComponent(tsUtc)}`);
  if (!res.ok) return null;
  return res.json();
}

export function renderIncidentReplay(host, scene) {
  if (!host || !scene) return;
  const shots = scene.shots || [];
  host.innerHTML = `
    <p class="muted small">${scene.caveat || ""}</p>
    <p><strong>${scene.title || scene.scene_id}</strong></p>
    <label class="replay-scrub-label">Timeline <input type="range" id="incidentScrub" min="0" max="${Math.max(0, shots.length - 1)}" value="0" /></label>
    <ol id="incidentShotList" class="replay-shot-list"></ol>
    <button type="button" id="incidentExportBtn" class="timeline-more">Export static bundle</button>
  `;
  const scrub = $("#incidentScrub");
  const list = $("#incidentShotList");
  const renderShot = (idx) => {
    const shot = shots[idx];
    if (!shot || !list) return;
    const cam = shot.camera || {};
    list.innerHTML = `<li><span class="mono">${shot.at_utc}</span> ${shot.label}<br/>
      <span class="muted small">Camera focus ${cam.focus_lat?.toFixed?.(3) ?? "—"}, ${cam.focus_lon?.toFixed?.(3) ?? "—"} (${cam.default_zoom || "harbour"})</span></li>`;
    document.dispatchEvent(
      new CustomEvent("wichita-incident-camera", {
        detail: { lat: cam.focus_lat, lon: cam.focus_lon, zoom: cam.default_zoom },
      }),
    );
  };
  scrub?.addEventListener("input", () => renderShot(Number(scrub.value)));
  renderShot(0);
  $("#incidentExportBtn")?.addEventListener("click", async () => {
    const anchor = scene.timeline?.anchor_utc || scene.anchor_event?.ts_utc;
    if (!anchor) return;
    const res = await fetch(`/api/incident-replay/export?ts_utc=${encodeURIComponent(anchor)}`, { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      alert(`Exported ${data.scene_id} to server path (bundle JSON).`);
    }
  });
}

export function initIncidentReplay() {
  const host = $("#incidentReplayPanel");
  const ol = $("#timeline");
  if (!host || !ol) return;
  ol.addEventListener("click", async (ev) => {
    const li = ev.target.closest("li[data-ts]");
    if (!li) return;
    const ts = li.getAttribute("data-ts");
    const scene = await loadScene(ts);
    if (scene) renderIncidentReplay(host, scene);
  });
}
