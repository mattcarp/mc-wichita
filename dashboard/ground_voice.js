// Ground voice: real state only. Lists the Malta allowlist from the server and
// shows each channel as live, idle or at its listener limit. Audio plays only
// through the server proxy, via a one-time ticket; the browser never sees a source URL.
import { plural } from "./plural.js?v=20261016-replay-voice";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const STATE_LABEL = { live: "Live", idle: "Idle", limit: "Listener limit reached" };

async function listen(id, row) {
  const msg = row.querySelector(".gv-msg");
  const res = await fetch(`/api/ground-voice/channels/${encodeURIComponent(id)}/ticket`, { method: "POST" });
  if (res.status === 429) { msg.textContent = "Listener limit reached. Try again shortly."; return; }
  if (!res.ok) { msg.textContent = "This channel is idle."; return; }
  const { ticket } = await res.json();
  const audio = row.querySelector("audio") || row.appendChild(Object.assign(document.createElement("audio"), { controls: true }));
  audio.src = `/api/ground-voice/listen/${encodeURIComponent(id)}?ticket=${encodeURIComponent(ticket)}`;
  audio.play().catch(() => { msg.textContent = "Couldn't start the audio."; });
}

export async function initGroundVoice() {
  const root = document.getElementById("groundVoiceList");
  const summary = document.getElementById("groundVoiceSummary");
  if (!root) return;
  let data;
  try {
    const res = await fetch("/api/ground-voice/channels");
    if (!res.ok) throw new Error(res.status);
    data = await res.json();
  } catch {
    summary.textContent = "Couldn't reach the server.";
    return;
  }
  const live = data.channels.filter((c) => c.state === "live").length;
  summary.textContent = live
    ? `${plural(live, "channel")} live · ${plural(data.listeners, "listener")} now`
    : `Idle. ${data.channels[0]?.reason || "No audio is received yet."}`;
  root.innerHTML = data.channels.map((c) => `
    <li class="voice-slot gv-row" data-test-id="ground-voice-channel" data-state="${esc(c.state)}" data-channel="${esc(c.id)}">
      <p class="voice-slot-flag mono">${esc(STATE_LABEL[c.state] || c.state)}</p>
      <dl>
        <div><dt>Channel</dt><dd>${esc(c.name)}</dd></div>
        <div><dt>Band · frequency · mode</dt><dd class="mono">${esc(c.band)} · ${Number(c.frequency_mhz).toFixed(3)} MHz · ${esc(c.mode)}</dd></div>
        <div><dt>Why we may receive it</dt><dd>${esc(c.legal_status)}</dd></div>
        <div><dt>Listeners</dt><dd>${c.listeners} of ${c.max_listeners}</dd></div>
      </dl>
      ${c.state === "live" ? `<button type="button" class="gv-listen">Listen</button>` : ""}
      <p class="muted small gv-msg"></p>
    </li>`).join("");
  root.querySelectorAll(".gv-listen").forEach((b) => b.addEventListener("click", () => {
    const row = b.closest(".gv-row");
    listen(row.dataset.channel, row);
  }));
}
