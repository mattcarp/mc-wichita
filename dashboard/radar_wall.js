const RX = { lat: 35.898666, lon: 14.5145 };
const MAX_KM = 40;

function haversineKm(lat1, lon1, lat2, lon2) {
  const r = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(a));
}

function bearingDeg(lat1, lon1, lat2, lon2) {
  const φ1 = (lat1 * Math.PI) / 180;
  const φ2 = (lat2 * Math.PI) / 180;
  const Δλ = ((lon2 - lon1) * Math.PI) / 180;
  const y = Math.sin(Δλ) * Math.cos(φ2);
  const x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

function placeBlip(host, lat, lon, label) {
  const dist = haversineKm(RX.lat, RX.lon, lat, lon);
  if (dist > MAX_KM) return;
  const brng = bearingDeg(RX.lat, RX.lon, lat, lon);
  const r = (dist / MAX_KM) * 50;
  const rad = (brng * Math.PI) / 180;
  const x = 50 + r * Math.sin(rad);
  const y = 50 - r * Math.cos(rad);
  const el = document.createElement("span");
  el.className = "radar-blip";
  el.style.left = `${x}%`;
  el.style.top = `${y}%`;
  el.title = label;
  host.appendChild(el);
}

function initRings(host) {
  [10, 20, 30, 40].forEach((km) => {
    const ring = document.createElement("div");
    ring.className = "radar-ring";
    ring.style.width = `${(km / MAX_KM) * 100}%`;
    ring.style.height = ring.style.width;
    host.appendChild(ring);
  });
}

async function poll() {
  const host = document.getElementById("radarCanvas");
  if (!host) return;
  host.querySelectorAll(".radar-blip").forEach((n) => n.remove());
  try {
    const [ais, adsb] = await Promise.all([
      fetch("/api/live-ais/snapshot").then((r) => r.json()),
      fetch("/api/sky/adsb/snapshot").then((r) => r.json()),
    ]);
    (ais.ships || []).forEach((s) => {
      if (s.lat != null && s.lon != null) placeBlip(host, s.lat, s.lon, s.display_name || "ship");
    });
    (adsb.aircraft || []).forEach((p) => {
      if (p.lat != null && p.lon != null) placeBlip(host, p.lat, p.lon, p.display_name || p.hex);
    });
  } catch {
    /* quiet */
  }
}

const host = document.getElementById("radarCanvas");
if (host) {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    host.classList.add("reduced-motion");
  }
  initRings(host);
  poll();
  setInterval(poll, 5000);
}
