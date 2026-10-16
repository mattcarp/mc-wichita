import { plural } from "./plural.js?v=20261016-loading";
import { formatMaltaTimeShort } from "./time_malta.js?v=20261016-loading";
import { createReplayClock, parseReplayTs } from "./harbour_replay.js?v=20261016-loading";

const incidentState = {
  active: false,
  anchorUtc: null,
  frame: null,
  clock: null,
  audio: null,
  lastClipId: null,
  clipBlobs: new Map(),
};

function $(sel) {
  return document.querySelector(sel);
}

export function isIncidentReplayActive() {
  return incidentState.active;
}

export function incidentReplayFrameNow() {
  return incidentState.active ? incidentState.frame : null;
}

export async function loadScene(tsUtc) {
  const res = await fetch(`/api/incident-replay/scene?ts_utc=${encodeURIComponent(tsUtc)}`);
  if (!res.ok) return null;
  return res.json();
}

async function fetchFrame(tsUtc, anchorUtc) {
  const qs = new URLSearchParams({ ts_utc: tsUtc, anchor_utc: anchorUtc });
  const res = await fetch(`/api/incident-replay/frame?${qs}`);
  if (!res.ok) return null;
  return res.json();
}

async function clipObjectUrl(clipId, playbackUrl) {
  if (incidentState.clipBlobs.has(clipId)) {
    return incidentState.clipBlobs.get(clipId);
  }
  const res = await fetch(playbackUrl, { credentials: "include" });
  if (!res.ok) return null;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  incidentState.clipBlobs.set(clipId, url);
  return url;
}

function stopIncidentReplay() {
  incidentState.active = false;
  incidentState.frame = null;
  incidentState.lastClipId = null;
  incidentState.clock?.destroy();
  incidentState.clock = null;
  if (incidentState.audio) {
    incidentState.audio.pause();
    incidentState.audio.removeAttribute("src");
  }
  for (const url of incidentState.clipBlobs.values()) URL.revokeObjectURL(url);
  incidentState.clipBlobs.clear();
  document.dispatchEvent(new CustomEvent("wichita-incident-replay-end"));
}

function assistHtml(assist) {
  if (!assist?.length) {
    return "<p class='muted small'>No vessels or aircraft with positions near this moment.</p>";
  }
  return `<ul class="replay-assist-list">${assist
    .map(
      (a) =>
        `<li><span class="mono">${a.kind}</span> ${a.label} · ${a.distance_nm} nm${
          a.speed_kn != null ? ` · ${Number(a.speed_kn).toFixed(1)} kn` : ""
        }${a.altitude_ft != null ? ` · ${Math.round(a.altitude_ft)} ft` : ""}</li>`,
    )
    .join("")}</ul>`;
}

function voiceSummary(clips) {
  const n = clips?.length ?? 0;
  if (!n) {
    return "No retained voice clips in this window (only flagged segments scoring 70 or more are kept, up to 72 hours).";
  }
  return `${plural(n, "retained clip")} from our receivers in this window.`;
}

function renderContext(host, scene, frame) {
  const tl = scene.timeline || {};
  const w = frame?.weather || {};
  const clips = frame?.voice_clips || scene.voice_clips || [];
  const active = frame?.voice_active_clip_ids || [];
  host.innerHTML = `
    <p class="muted small">${scene.caveat || ""}</p>
    <p><strong>${scene.title || scene.scene_id}</strong></p>
    <p class="mono small" id="incidentReplayTime">${frame?.ts_utc ? formatMaltaTimeShort(frame.ts_utc) : "—"}</p>
    <label class="replay-scrub-label">Replay timeline
      <input type="range" id="incidentScrub" min="0" max="0" value="0" aria-label="Incident replay time" />
    </label>
    <div class="replay-controls incident-replay-controls">
      <button type="button" id="incidentReplayPlay" class="timeline-more" aria-pressed="false">Play</button>
      <label class="replay-speed-label mono">
        Speed
        <select id="incidentReplaySpeed" aria-label="Incident replay speed">
          <option value="1">1×</option>
          <option value="2">2×</option>
          <option value="4">4×</option>
        </select>
      </label>
      <button type="button" id="incidentReplayExit" class="timeline-more">Live</button>
    </div>
    <section aria-label="Weather at replay time">
      <p class="eyebrow">Weather</p>
      <p id="incidentWeatherText">${w.plain_english || "—"}</p>
      <p class="muted small">${w.note || ""}</p>
    </section>
    <section aria-label="Nearest assist">
      <p class="eyebrow">Nearest assist</p>
      <div id="incidentAssist">${assistHtml(frame?.nearest_assist)}</div>
    </section>
    <section aria-label="Voice clips">
      <p class="eyebrow">Voice</p>
      <p class="muted small">${voiceSummary(clips)}</p>
      <p id="incidentVoiceActive" class="mono small">${active.length ? `Playing ${active[0]}` : "Silent"}</p>
      <audio id="incidentReplayAudio" preload="none" controls class="incident-replay-audio"></audio>
    </section>
    <button type="button" id="incidentExportBtn" class="timeline-more">Export static bundle</button>
  `;
}

async function syncVoice(frame) {
  const audio = incidentState.audio || $("#incidentReplayAudio");
  incidentState.audio = audio;
  const activeEl = $("#incidentVoiceActive");
  const active = frame?.voice_active_clip_ids || [];
  if (!active.length) {
    incidentState.lastClipId = null;
    if (activeEl) activeEl.textContent = "Silent";
    if (audio && !audio.paused) audio.pause();
    return;
  }
  const clipId = active[0];
  const clip = (frame.voice_clips || []).find((c) => c.clip_id === clipId);
  if (!clip) return;
  if (incidentState.lastClipId === clipId && audio && !audio.paused) {
    if (activeEl) activeEl.textContent = `Playing ${clip.channel_name || clipId}`;
    return;
  }
  const url = await clipObjectUrl(clipId, clip.playback_url);
  if (!url || !audio) return;
  incidentState.lastClipId = clipId;
  audio.src = url;
  if (activeEl) {
    activeEl.textContent = `Playing ${clip.channel_name} · ${clip.frequency_mhz?.toFixed?.(3) ?? ""} MHz`;
  }
  audio.play().catch(() => {
    if (activeEl) activeEl.textContent = "Tap play on the clip control to hear audio.";
  });
}

async function applyIncidentFrame(scene, cursorMs, anchorUtc) {
  const iso = new Date(cursorMs).toISOString();
  const frame = await fetchFrame(iso, anchorUtc);
  if (!frame) return;
  incidentState.frame = frame;
  const timeEl = $("#incidentReplayTime");
  if (timeEl) timeEl.textContent = formatMaltaTimeShort(frame.ts_utc);
  const weatherEl = $("#incidentWeatherText");
  if (weatherEl) weatherEl.textContent = frame.weather?.plain_english || "—";
  const assist = $("#incidentAssist");
  if (assist) assist.innerHTML = assistHtml(frame.nearest_assist);
  document.dispatchEvent(
    new CustomEvent("wichita-incident-camera", {
      detail: { lat: scene.map?.center_lat, lon: scene.map?.center_lon, zoom: "harbour" },
    }),
  );
  document.dispatchEvent(new CustomEvent("wichita-incident-replay-frame", { detail: { frame } }));
  await syncVoice(frame);
}

function bindIncidentControls(scene, anchorUtc, firstMs, lastMs) {
  const scrub = $("#incidentScrub");
  if (scrub) {
    scrub.min = String(firstMs);
    scrub.max = String(lastMs);
    scrub.value = String(parseReplayTs(scene.timeline?.anchor_utc) ?? firstMs);
  }
  let speed = 1;
  incidentState.clock?.destroy();
  incidentState.clock = createReplayClock({
    firstMs,
    lastMs,
    getSpeed: () => speed,
    onStep: (ms) => {
      if (scrub) scrub.value = String(ms);
      applyIncidentFrame(scene, ms, anchorUtc);
    },
  });
  incidentState.clock.setCursor(parseReplayTs(scene.timeline?.anchor_utc) ?? firstMs);

  scrub?.addEventListener("input", () => {
    incidentState.clock?.stop();
    $("#incidentReplayPlay")?.setAttribute("aria-pressed", "false");
    const ms = Number(scrub.value);
    incidentState.clock?.setCursor(ms);
    applyIncidentFrame(scene, ms, anchorUtc);
  });

  $("#incidentReplayPlay")?.addEventListener("click", () => {
    if (incidentState.clock?.playing) {
      incidentState.clock.stop();
      $("#incidentReplayPlay")?.setAttribute("aria-pressed", "false");
      return;
    }
    incidentState.active = true;
    incidentState.clock?.start();
    $("#incidentReplayPlay")?.setAttribute("aria-pressed", "true");
  });

  $("#incidentReplaySpeed")?.addEventListener("change", (ev) => {
    speed = Number(ev.target.value) || 1;
  });

  $("#incidentReplayExit")?.addEventListener("click", () => {
    stopIncidentReplay();
    const host = $("#incidentReplayPanel");
    if (host) host.innerHTML = "";
  });

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

export async function startIncidentReplay(host, scene) {
  if (!host || !scene?.timeline) return;
  stopIncidentReplay();
  incidentState.active = true;
  incidentState.anchorUtc = scene.timeline.anchor_utc;
  const firstMs = parseReplayTs(scene.timeline.start_utc);
  const lastMs = parseReplayTs(scene.timeline.end_utc);
  if (firstMs == null || lastMs == null) return;
  renderContext(host, scene, null);
  bindIncidentControls(scene, scene.timeline.anchor_utc, firstMs, lastMs);
  document.dispatchEvent(new CustomEvent("wichita-incident-replay-start", { detail: { scene } }));
}

export function renderIncidentReplay(host, scene) {
  startIncidentReplay(host, scene);
}

export function initIncidentReplay() {
  const host = $("#incidentReplayPanel");
  const ol = $("#timeline");
  if (!host || !ol) return;
  ol.addEventListener("click", async (ev) => {
    const li = ev.target.closest("li[data-ts]");
    if (!li) return;
    const ts = li.getAttribute("data-ts");
    host.hidden = false;
    host.innerHTML = '<div class="load-state" role="status" data-state="loading"><span class="load-spin" aria-hidden="true"></span><span class="load-msg">Loading replay…</span></div>';
    const scene = await loadScene(ts);
    if (scene) await startIncidentReplay(host, scene);
    else if (window.wichitaLoadError) {
      window.wichitaLoadError(host, "The replay could not be loaded.", () => li.click());
    }
  });
}
