const TYPE_COLORS = {
  passenger: "#5eb8ff",
  cargo: "#d4a84b",
  tanker: "#b07ad9",
  sailing: "#7ec8a8",
  pleasure: "#9ad4ff",
  pilot: "#f0c674",
  tug: "#8b93a7",
  tender: "#8b93a7",
  sar: "#6bcf7f",
  fishing: "#6bcf7f",
  hsc: "#ff9f6b",
  other: "#3ec6c9",
};

const PLACES = [
  { name: "Valletta", lat: 35.8987, lon: 14.5145 },
  { name: "Grand Harbour", lat: 35.887, lon: 14.518 },
  { name: "Marsamxett", lat: 35.905, lon: 14.495 },
  { name: "Sliema", lat: 35.912, lon: 14.502 },
  { name: "Ċirkewwa", lat: 35.988, lon: 14.327 },
  { name: "Mġarr (Gozo)", lat: 36.025, lon: 14.303 },
];

let coastCache = null;
let waterCache = null;

export function typeColor(category) {
  return TYPE_COLORS[category] || TYPE_COLORS.other;
}

function haversineKm(lat1, lon1, lat2, lon2) {
  const r = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(a));
}

function ringCoords(lat, lon, radiusKm, steps = 64) {
  const pts = [];
  for (let i = 0; i <= steps; i++) {
    const brng = (i / steps) * 2 * Math.PI;
    const d = radiusKm / 6371;
    const lat1 = (lat * Math.PI) / 180;
    const lon1 = (lon * Math.PI) / 180;
    const lat2 = Math.asin(
      Math.sin(lat1) * Math.cos(d) + Math.cos(lat1) * Math.sin(d) * Math.cos(brng),
    );
    const lon2 =
      lon1 +
      Math.atan2(Math.sin(brng) * Math.sin(d) * Math.cos(lat1), Math.cos(d) - Math.sin(lat1) * Math.sin(lat2));
    pts.push([(lon2 * 180) / Math.PI, (lat2 * 180) / Math.PI]);
  }
  return pts;
}

async function loadCoastline() {
  if (coastCache) return coastCache;
  const res = await fetch("/dashboard/data/malta_coastline.geojson");
  coastCache = await res.json();
  return coastCache;
}

async function loadWater() {
  if (waterCache) return waterCache;
  const res = await fetch("/dashboard/data/malta_water.geojson");
  waterCache = await res.json();
  return waterCache;
}

function pathFromRing(ring, projectFn) {
  return ring
    .map(([lon, lat], i) => {
      const { x, y } = projectFn(lat, lon);
      return `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

export class HarbourMap {
  constructor(container) {
    this.container = container;
    this.receiver = { lat: 35.898666, lon: 14.5145, label: "Valletta balcony (approx.)" };
    this.ships = [];
    this.bases = [];
    this.paths = null;
    this.selectedMmsi = null;
    this.posHistory = new Map();
    this.view = { minLat: 35.82, maxLat: 36.08, minLon: 14.28, maxLon: 14.58 };
    this.zoomMode = "all";
    this._reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this._onSelect = null;
    this._svg = null;
    this._mapW = 400;
    this._mapH = 220;
    this._init();
  }

  onSelect(fn) {
    this._onSelect = fn;
  }

  async _init() {
    await Promise.all([loadCoastline(), loadWater()]);
    this.container.innerHTML = "";
    this.container.classList.add("harbour-map-host");
    const wrap = document.createElement("div");
    wrap.className = "harbour-map-inner";
    wrap.innerHTML = `<svg class="harbour-svg" role="img" aria-label="Malta coastline map with live ship positions"></svg>
      <div class="map-zoom-bar" role="toolbar" aria-label="Map zoom">
        <button type="button" data-zoom="harbour">Harbour</button>
        <button type="button" data-zoom="malta">Malta</button>
        <button type="button" data-zoom="all" class="active">All ships</button>
      </div>`;
    this.container.appendChild(wrap);
    this._svg = wrap.querySelector("svg");
    wrap.querySelectorAll("[data-zoom]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this.zoomMode = btn.getAttribute("data-zoom");
        wrap.querySelectorAll("[data-zoom]").forEach((b) => b.classList.toggle("active", b === btn));
        this._fitView();
        this._draw();
      });
    });
    this._resizeObserver = new ResizeObserver(() => this._draw());
    this._resizeObserver.observe(this.container);
    this._fitView();
    this._draw();
  }

  setReceiver(r) {
    if (!r) return;
    this.receiver = { ...this.receiver, ...r };
  }

  update({ ships, baseStations, paths, selectedMmsi }) {
    const now = performance.now();
    for (const s of ships || []) {
      if (s.lat == null || s.lon == null) continue;
      const prev = this.posHistory.get(s.mmsi);
      if (prev && !this._reducedMotion) {
        s._anim = { from: prev, to: { lat: s.lat, lon: s.lon }, t0: now, dur: 4800 };
      }
      this.posHistory.set(s.mmsi, { lat: s.lat, lon: s.lon, pulse: now });
    }
    this.ships = ships || [];
    this.bases = baseStations || [];
    this.paths = paths;
    this.selectedMmsi = selectedMmsi;
    this._fitView();
    this._draw();
  }

  focusShip(mmsi) {
    const s = this.ships.find((x) => x.mmsi === mmsi);
    if (!s || s.lat == null) return;
    const pad = 0.018;
    this.view = {
      minLat: s.lat - pad,
      maxLat: s.lat + pad,
      minLon: s.lon - pad,
      maxLon: s.lon + pad,
    };
    this._draw();
  }

  _fitView() {
    const pts = this.ships.filter((s) => s.lat != null && s.lon != null);
    if (this.zoomMode === "harbour") {
      this.view = { minLat: 35.88, maxLat: 35.92, minLon: 14.49, maxLon: 14.54 };
      return;
    }
    if (this.zoomMode === "malta") {
      this.view = { minLat: 35.82, maxLat: 36.1, minLon: 14.28, maxLon: 14.58 };
      return;
    }
    if (!pts.length) {
      this.view = { minLat: 35.82, maxLat: 36.1, minLon: 14.28, maxLon: 14.58 };
      return;
    }
    let minLat = 90;
    let maxLat = -90;
    let minLon = 180;
    let maxLon = -180;
    for (const s of pts) {
      minLat = Math.min(minLat, s.lat);
      maxLat = Math.max(maxLat, s.lat);
      minLon = Math.min(minLon, s.lon);
      maxLon = Math.max(maxLon, s.lon);
    }
    const padLat = Math.max(0.02, (maxLat - minLat) * 0.15);
    const padLon = Math.max(0.02, (maxLon - minLon) * 0.15);
    this.view = {
      minLat: minLat - padLat,
      maxLat: maxLat + padLat,
      minLon: minLon - padLon,
      maxLon: maxLon + padLon,
    };
  }

  _measure() {
    const inner = this.container.querySelector(".harbour-map-inner");
    const cw = Math.floor(inner?.clientWidth || this.container.clientWidth || 320);
    const ch = Math.floor(this.container.clientHeight || inner?.clientHeight || 0);
    const w = Math.max(280, Math.min(cw, 1200));
    const aspectH = Math.round(w * 0.52);
    const h = ch >= 120 ? Math.max(aspectH, ch) : aspectH;
    this._mapW = w;
    this._mapH = h;
    return { w, h };
  }

  _projectShip(lat, lon, w, h, pad = 11) {
    const p = this._project(lat, lon, w, h);
    const left = pad;
    const right = w - pad;
    const top = pad;
    const bottom = h - pad;
    if (p.x >= left && p.x <= right && p.y >= top && p.y <= bottom) {
      return { ...p, offFrame: false, angle: 0 };
    }
    const cx = (left + right) / 2;
    const cy = (top + bottom) / 2;
    const dx = p.x - cx;
    const dy = p.y - cy;
    const absDx = Math.abs(dx);
    const absDy = Math.abs(dy);
    let edgeX;
    let edgeY;
    if (absDx * (bottom - top) > absDy * (right - left)) {
      edgeX = dx > 0 ? right : left;
      edgeY = cy + (dy * Math.abs(edgeX - cx)) / (absDx || 1e-9);
    } else {
      edgeY = dy > 0 ? bottom : top;
      edgeX = cx + (dx * Math.abs(edgeY - cy)) / (absDy || 1e-9);
    }
    edgeX = Math.max(left, Math.min(right, edgeX));
    edgeY = Math.max(top, Math.min(bottom, edgeY));
    const angle = Math.atan2(p.y - edgeY, p.x - edgeX);
    return { x: edgeX, y: edgeY, offFrame: true, angle };
  }

  _project(lat, lon, w, h) {
    const { minLat, maxLat, minLon, maxLon } = this.view;
    const lonSpan = maxLon - minLon || 1e-6;
    const latSpan = maxLat - minLat || 1e-6;
    const x = 8 + ((lon - minLon) / lonSpan) * (w - 16);
    const y = h - 8 - ((lat - minLat) / latSpan) * (h - 16);
    return { x, y };
  }

  _drawPolygons(geojson, className, w, h) {
    const parts = [];
    if (!geojson?.features) return parts;
    const proj = (lat, lon) => this._project(lat, lon, w, h);
    for (const f of geojson.features) {
      const geom = f.geometry;
      if (!geom) continue;
      const polys = geom.type === "MultiPolygon" ? geom.coordinates : [geom.coordinates];
      for (const poly of polys) {
        if (!poly) continue;
        for (const ring of poly) {
          if (!ring?.length) continue;
          parts.push(`<path d="${pathFromRing(ring, proj)} Z" class="${className}"/>`);
        }
      }
    }
    return parts;
  }

  _draw() {
    if (!this._svg) return;
    const { w, h } = this._measure();
    this._svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    this._svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    this._svg.removeAttribute("width");
    this._svg.style.width = "100%";
    this._svg.style.height = `${h}px`;
    this._svg.style.maxWidth = "100%";
    this._svg.style.display = "block";

    const parts = [];
    parts.push(`<rect width="${w}" height="${h}" class="map-sea"/>`);
    parts.push(...this._drawPolygons(coastCache, "map-land", w, h));
    parts.push(...this._drawPolygons(waterCache, "map-water", w, h));

    for (const km of [5, 10, 20]) {
      const ring = ringCoords(this.receiver.lat, this.receiver.lon, km);
      const pts = ring
        .map(([lon, lat]) => {
          const p = this._project(lat, lon, w, h);
          return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
        })
        .join(" ");
      parts.push(`<polyline points="${pts}" class="map-range" data-km="${km}"/>`);
    }
    const rx = this._project(this.receiver.lat, this.receiver.lon, w, h);
    parts.push(
      `<polygon points="${rx.x},${rx.y - 7} ${rx.x + 6},${rx.y} ${rx.x},${rx.y + 7} ${rx.x - 6},${rx.y}" class="map-receiver"/>`,
    );
    parts.push(
      `<text x="${Math.min(w - 8, rx.x + 8)}" y="${rx.y + 3}" class="map-label">${this.receiver.label || "Receiver (approx.)"}</text>`,
    );
    for (const p of PLACES) {
      const { x, y } = this._project(p.lat, p.lon, w, h);
      parts.push(`<text x="${x}" y="${y}" class="map-place">${p.name}</text>`);
    }
    const pathFeatures = this.paths?.features || [];
    for (const f of pathFeatures) {
      const mmsi = Number(f.properties?.mmsi || f.id || 0);
      const coords = f.geometry?.coordinates || [];
      if (!coords.length) continue;
      const sel = mmsi === this.selectedMmsi;
      const pts = coords
        .map(([lon, lat]) => {
          const p = this._project(lat, lon, w, h);
          return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
        })
        .join(" ");
      parts.push(
        `<polyline points="${pts}" class="map-track${sel ? " map-track-selected" : ""}" data-mmsi="${mmsi}"/>`,
      );
    }
    for (const s of this.bases) {
      if (s.lat == null || s.lon == null) continue;
      const { x, y } = this._project(s.lat, s.lon, w, h);
      parts.push(
        `<g class="map-base" data-mmsi="${s.mmsi}" role="button" tabindex="0"><polygon points="${x},${y - 6} ${x + 5},${y} ${x},${y + 6} ${x - 5},${y}" /></g>`,
      );
    }
    const now = performance.now();
    for (const s of this.ships) {
      if (s.lat == null || s.lon == null) continue;
      let lat = s.lat;
      let lon = s.lon;
      if (s._anim && !this._reducedMotion) {
        const t = Math.min(1, (now - s._anim.t0) / s._anim.dur);
        lat = s._anim.from.lat + (s._anim.to.lat - s._anim.from.lat) * t;
        lon = s._anim.from.lon + (s._anim.to.lon - s._anim.from.lon) * t;
      }
      const proj = this._projectShip(lat, lon, w, h);
      const stale = (s.last_signal_s || 0) > 600;
      const fresh = (s.freshness || "") === "now";
      const col = typeColor(s.shiptype_category);
      const sel = s.mmsi === this.selectedMmsi;
      const pulse = fresh && this.posHistory.get(s.mmsi)?.pulse > now - 5000;
      if (proj.offFrame) {
        const deg = (proj.angle * 180) / Math.PI;
        const r = sel ? 7 : 5;
        parts.push(
          `<g class="map-ship-edge${stale ? " map-ship-stale" : ""}" data-mmsi="${s.mmsi}" role="button" tabindex="0" transform="translate(${proj.x.toFixed(1)},${proj.y.toFixed(1)}) rotate(${deg.toFixed(1)})">
            <polygon points="0,-${r} ${r + 3},0 0,${r} -${r + 3},0" fill="${col}" class="map-ship-arrow"/>
          </g>`,
        );
      } else {
        parts.push(
          `<circle cx="${proj.x.toFixed(1)}" cy="${proj.y.toFixed(1)}" r="${sel ? 7 : 5}" class="map-ship${stale ? " map-ship-stale" : ""}${pulse ? " map-ship-pulse" : ""}" fill="${col}" data-mmsi="${s.mmsi}" role="button" tabindex="0"/>`,
        );
      }
    }
    this._svg.innerHTML = parts.join("");
    this._svg.querySelectorAll("[data-mmsi]").forEach((el) => {
      const mmsi = Number(el.getAttribute("data-mmsi"));
      el.addEventListener("click", () => this._onSelect?.(mmsi));
    });
  }
}
