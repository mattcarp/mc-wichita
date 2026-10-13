import { formatMaltaTimeShort } from "./time_malta.js?v=20261013-sp8";

const replayState = {
  active: false,
  playing: false,
  speed: 1,
  cursorMs: null,
  firstMs: null,
  lastMs: null,
  timer: null,
  ships: [],
};

function $(sel) {
  return document.querySelector(sel);
}

function parseTs(ts) {
  if (!ts) return null;
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? null : d.getTime();
}

async function loadMeta() {
  const res = await fetch("/api/live-ais/history/meta");
  if (!res.ok) return null;
  return res.json();
}

async function frameAtIso(iso) {
  const res = await fetch(`/api/live-ais/history/at?ts_utc=${encodeURIComponent(iso)}`);
  if (!res.ok) return null;
  return res.json();
}

export function replayShipsNow() {
  return replayState.active ? replayState.ships : null;
}

export function isReplayActive() {
  return replayState.active;
}

async function applyFrame(iso, onFrame) {
  const data = await frameAtIso(iso);
  if (!data?.ships) return;
  replayState.ships = data.ships.map((s) => ({
    ...s,
    mmsi_display: String(s.mmsi).padStart(9, "0"),
    freshness: "earlier",
    freshness_label: "Replay",
    lead_sentence: s.display_name || `MMSI ${s.mmsi}`,
    last_signal_s: 99999,
  }));
  const label = $("#replayTimeLabel");
  if (label) label.textContent = formatMaltaTimeShort(iso);
  onFrame?.(replayState.ships);
}

function stopPlay() {
  replayState.playing = false;
  if (replayState.timer) {
    clearInterval(replayState.timer);
    replayState.timer = null;
  }
  $("#replayPlay")?.setAttribute("aria-pressed", "false");
}

function startPlay(onFrame) {
  if (replayState.firstMs == null || replayState.lastMs == null) return;
  replayState.playing = true;
  $("#replayPlay")?.setAttribute("aria-pressed", "true");
  const stepMs = 5000;
  replayState.timer = setInterval(() => {
    if (!replayState.playing) return;
    let next = (replayState.cursorMs ?? replayState.firstMs) + stepMs * replayState.speed;
    if (next > replayState.lastMs) {
      next = replayState.firstMs;
    }
    replayState.cursorMs = next;
    const scrub = $("#replayScrub");
    if (scrub) scrub.value = String(next);
    applyFrame(new Date(next).toISOString(), onFrame);
  }, 400);
}

export async function initHarbourReplay(onFrame, onExit) {
  const bar = $("#harbourReplayBar");
  if (!bar) return;
  const meta = await loadMeta();
  if (!meta?.first_ts_utc || !meta?.last_ts_utc) {
    bar.hidden = true;
    return;
  }
  replayState.firstMs = parseTs(meta.first_ts_utc);
  replayState.lastMs = parseTs(meta.last_ts_utc);
  replayState.cursorMs = replayState.lastMs;
  bar.hidden = false;
  const scrub = $("#replayScrub");
  if (scrub) {
    scrub.min = String(replayState.firstMs);
    scrub.max = String(replayState.lastMs);
    scrub.value = String(replayState.cursorMs);
    scrub.addEventListener("input", () => {
      stopPlay();
      replayState.cursorMs = Number(scrub.value);
      replayState.active = true;
      applyFrame(new Date(replayState.cursorMs).toISOString(), onFrame);
    });
  }
  $("#replayPlay")?.addEventListener("click", () => {
    if (replayState.playing) {
      stopPlay();
      return;
    }
    replayState.active = true;
    startPlay(onFrame);
  });
  $("#replayExit")?.addEventListener("click", () => {
    stopPlay();
    replayState.active = false;
    replayState.ships = [];
    onExit?.();
  });
  $("#replaySpeed")?.addEventListener("change", (ev) => {
    replayState.speed = Number(ev.target.value) || 1;
  });
}
