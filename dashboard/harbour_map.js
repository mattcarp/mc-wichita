import { EntityMotion } from "./map_motion.js?v=20261009-23";

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
    this.selectedPlaneId = null;
    this.planes = [];
    this.satelliteTracks = [];
    this.follow = null;
    this.shipMotion = new EntityMotion(5000);
    this.planeMotion = new EntityMotion(5000);
    this.posHistory = new Map();
    this.view = { minLat: 35.82, maxLat: 36.08, minLon: 14.28, maxLon: 14.58 };
    this.zoomMode = "harbour";
    this._reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this._onSelect = null;
    this._svg = null;
    this._mapW = 400;
    this._mapH = 220;
    this._lastObservedW = 0;
    this.watchZones = [];
    this.watchDraft = [];
    this.wallMode = false;
    this._watchDraw = null;
    this._init();
    document.addEventListener("wichita-incident-camera", (ev) => {
      const { lat, lon } = ev.detail || {};
      if (lat != null && lon != null) this.focusPoint(lat, lon);
    });
  }

  setWatchZones(zones) {
    this.watchZones = zones || [];
    this._draw();
  }

  setWatchDraft(ring) {
    this.watchDraft = ring || [];
    this._draw();
  }

  setWatchDrawMode(on, handlers) {
    this._watchDraw = on ? handlers : null;
    this.container.classList.toggle("map-draw-watch", Boolean(on));
  }

  setWallMode(on) {
    this.wallMode = Boolean(on);
    this.container.classList.toggle("radar-wall", this.wallMode);
    if (this.wallMode && !this._reducedMotion) this._ensureAnimLoop();
    this._draw();
  }

  focusPoint(lat, lon, pad = 0.02) {
    this._centerOn(lat, lon, pad);
    this._draw();
  }

  onSelect(fn) {
    this._onSelect = fn;
  }

  onPlaneSelect(fn) {
    this._onPlaneSelect = fn;
  }

  setFollow(target) {
    this.follow = target;
    this._draw();
  }

  clearFollow() {
    this.follow = null;
    this._draw();
  }

  _centerOn(lat, lon, pad = 0.016) {
    this.view = {
      minLat: lat - pad,
      maxLat: lat + pad,
      minLon: lon - pad,
      maxLon: lon + pad,
    };
  }

  _ensureAnimLoop() {
    if (this._reducedMotion || this._animFrame) return;
    const tick = () => {
      this._draw();
      this._animFrame = requestAnimationFrame(tick);
    };
    this._animFrame = requestAnimationFrame(tick);
  }

  async _init() {
    await Promise.all([loadCoastline(), loadWater()]);
    this.container.innerHTML = "";
    this.container.classList.add("harbour-map-host");
    const wrap = document.createElement("div");
    wrap.className = "harbour-map-inner";
    wrap.innerHTML = `<svg class="harbour-svg" role="img" aria-label="Malta coastline map with live ship positions"></svg>
      <div class="map-zoom-bar" role="toolbar" aria-label="Map zoom">
        <button type="button" data-zoom="harbour" class="active">Harbour</button>
        <button type="button" data-zoom="malta">Malta</button>
        <button type="button" data-zoom="all">All ships</button>
      </div>`;
    this.container.appendChild(wrap);
    this._svg = wrap.querySelector("svg");
    wrap.querySelectorAll("[data-zoom]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this.zoomMode = btn.getAttribute("data-zoom");
        wrap.querySelectorAll("[data-zoom]").forEach((b) =>
          b.classList.toggle("active", b.getAttribute("data-zoom") === this.zoomMode),
        );
        this._fitView();
        this._draw();
      });
    });
    this._resizeObserver = new ResizeObserver(() => {
      const inner = this.container.querySelector(".harbour-map-inner");
      const w = Math.floor(inner?.clientWidth || 0);
      if (!w || w === this._lastObservedW) return;
      this._lastObservedW = w;
      this._draw();
    });
    this._resizeObserver.observe(wrap);
    this._svg.addEventListener("click", (ev) => {
      if (!this._watchDraw?.onPoint) return;
      const pt = this._clientToLatLon(ev.clientX, ev.clientY);
      if (!pt) return;
      this._watchDraw.onPoint(pt.lon, pt.lat);
    });
    this._svg.addEventListener("dblclick", () => {
      this._watchDraw?.onFinish?.();
    });
    wrap.querySelectorAll("[data-zoom]").forEach((b) =>
      b.classList.toggle("active", b.getAttribute("data-zoom") === this.zoomMode),
    );
    this._fitView();
    this._draw();
  }

  setReceiver(r) {
    if (!r) return;
    this.receiver = { ...this.receiver, ...r };
  }

  update({
    ships,
    baseStations,
    paths,
    selectedMmsi,
    planes,
    satelliteTracks,
    selectedPlaneId,
    follow,
  }) {
    const now = performance.now();
    for (const s of ships || []) {
      if (s.lat == null || s.lon == null) continue;
      this.shipMotion.ingest(`ship:${s.mmsi}`, s, now);
      this.posHistory.set(s.mmsi, { lat: s.lat, lon: s.lon, pulse: now });
    }
    for (const p of planes || []) {
      if (p.lat == null || p.lon == null) continue;
      this.planeMotion.ingest(`plane:${p.id}`, p, now);
    }
    this.ships = ships || [];
    this.planes = planes || [];
    this.bases = baseStations || [];
    this.paths = paths;
    this.satelliteTracks = satelliteTracks || [];
    this.selectedMmsi = selectedMmsi;
    this.selectedPlaneId = selectedPlaneId;
    if (follow !== undefined) this.follow = follow;
    if (this.follow) {
      this._applyFollowView(now);
    } else {
      this._fitView();
    }
    this._ensureAnimLoop();
    this._draw();
  }

  focusShip(mmsi) {
    const s = this.ships.find((x) => x.mmsi === mmsi);
    if (!s || s.lat == null) return;
    this._centerOn(s.lat, s.lon);
    this._draw();
  }

  _clampView(minSpan = 0.055) {
    const { minLat, maxLat, minLon, maxLon } = this.view;
    const latSpan = maxLat - minLat;
    const lonSpan = maxLon - minLon;
    if (latSpan >= minSpan && lonSpan >= minSpan) return;
    const cx = (minLat + maxLat) / 2;
    const cy = (minLon + maxLon) / 2;
    const half = minSpan / 2;
    this.view = {
      minLat: cx - half,
      maxLat: cx + half,
      minLon: cy - half,
      maxLon: cy + half,
    };
  }

  _applyFollowView(nowMs) {
    const f = this.follow;
    if (!f) return;
    if (f.kind === "ship") {
      const disp = this.shipMotion.displayPosition(`ship:${f.id}`, nowMs);
      if (disp) {
        this._centerOn(disp.lat, disp.lon, 0.022);
        this._clampView(0.06);
      }
      return;
    }
    if (f.kind === "plane") {
      const disp = this.planeMotion.displayPosition(`plane:${f.id}`, nowMs);
      if (disp) {
        this._centerOn(disp.lat, disp.lon, 0.04);
        this._clampView(0.08);
      }
    }
  }

  _fitView() {
    if (this.follow) return;
    const recentShips = this.ships.filter(
      (s) => s.lat != null && s.lon != null && (s.last_signal_s == null || s.last_signal_s < 900),
    );
    const pts = [
      ...recentShips,
      ...this.planes.filter((p) => p.lat != null && p.lon != null),
    ];
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
    const w = Math.max(280, Math.min(cw, 1200));
    const h = Math.round(w * 0.52);
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

  _clientToLatLon(clientX, clientY) {
    if (!this._svg) return null;
    const rect = this._svg.getBoundingClientRect();
    const { w, h } = this._measure();
    const x = ((clientX - rect.left) / rect.width) * w;
    const y = ((clientY - rect.top) / rect.height) * h;
    const { minLat, maxLat, minLon, maxLon } = this.view;
    const lonSpan = maxLon - minLon || 1e-6;
    const latSpan = maxLat - minLat || 1e-6;
    const lon = minLon + ((x - 8) / (w - 16)) * lonSpan;
    const lat = minLat + ((h - 8 - y) / (h - 16)) * latSpan;
    return { lat, lon };
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
    this._svg.style.height = "100%";
    this._svg.style.maxWidth = "100%";
    this._svg.style.display = "block";

    const latSpan = this.view.maxLat - this.view.minLat;
    const parts = [];
    parts.push(`<rect width="${w}" height="${h}" class="map-sea"/>`);
    if (this.wallMode && !this._reducedMotion) {
      const rx = this._project(this.receiver.lat, this.receiver.lon, w, h);
      const sweepR = Math.min(w, h) * 0.48;
      parts.push(
        `<g class="map-radar-sweep"><circle cx="${rx.x}" cy="${rx.y}" r="${sweepR}" class="map-radar-disc"/><line x1="${rx.x}" y1="${rx.y}" x2="${rx.x + sweepR}" y2="${rx.y}" class="map-radar-arm"/></g>`,
      );
    }
    parts.push(...this._drawPolygons(coastCache, "map-land", w, h));
    parts.push(...this._drawPolygons(waterCache, "map-water", w, h));

    for (const zone of this.watchZones) {
      const ring = zone.polygon || [];
      if (ring.length < 3) continue;
      const pts = ring
        .map(([lon, lat]) => {
          const p = this._project(lat, lon, w, h);
          return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
        })
        .join(" ");
      parts.push(`<polygon points="${pts}" class="map-watch-zone" data-zone="${zone.id || ""}"/>`);
    }
    if (this.watchDraft.length >= 2) {
      const pts = this.watchDraft
        .map(([lon, lat]) => {
          const p = this._project(lat, lon, w, h);
          return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
        })
        .join(" ");
      parts.push(`<polyline points="${pts}" class="map-watch-draft"/>`);
    }
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
    const placeZoom = this.zoomMode === "harbour" || latSpan < 0.08;
    if (placeZoom) {
      for (const p of PLACES) {
        const { x, y } = this._project(p.lat, p.lon, w, h);
        parts.push(`<text x="${x}" y="${y}" class="map-place">${p.name}</text>`);
      }
    }
    for (const track of this.satelliteTracks) {
      const coords = track.coordinates || [];
      if (coords.length < 2) continue;
      const pts = coords
        .map(([lon, lat]) => {
          const p = this._project(lat, lon, w, h);
          return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
        })
        .join(" ");
      parts.push(`<polyline points="${pts}" class="map-sat-track" data-sat="${track.id || ""}"/>`);
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
    if (this.follow) this._applyFollowView(now);
    for (const s of this.ships) {
      if (s.lat == null || s.lon == null) continue;
      const motion = this.shipMotion.displayPosition(`ship:${s.mmsi}`, now);
      let lat = motion?.lat ?? s.lat;
      let lon = motion?.lon ?? s.lon;
      const estimated = motion?.estimated;
      if (estimated && motion) {
        const real = motion.trail?.[motion.trail.length - 1];
        if (real) {
          const a = this._project(real.lat, real.lon, w, h);
          const b = this._project(lat, lon, w, h);
          parts.push(
            `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" class="map-estimated" />`,
          );
        }
      }
      const followTrail =
        this.follow?.kind === "ship" && this.follow.id === s.mmsi ? motion?.trail : null;
      if (followTrail && followTrail.length > 1) {
        const tpts = followTrail
          .map((pt) => {
            const p = this._project(pt.lat, pt.lon, w, h);
            return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
          })
          .join(" ");
        parts.push(`<polyline points="${tpts}" class="map-follow-trail"/>`);
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
    for (const p of this.planes) {
      if (p.lat == null || p.lon == null) continue;
      const motion = this.planeMotion.displayPosition(`plane:${p.id}`, now);
      let lat = motion?.lat ?? p.lat;
      let lon = motion?.lon ?? p.lon;
      const estimated = motion?.estimated;
      if (estimated && motion) {
        const real = motion.trail?.[motion.trail.length - 1];
        if (real) {
          const a = this._project(real.lat, real.lon, w, h);
          const b = this._project(lat, lon, w, h);
          parts.push(
            `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" class="map-estimated" />`,
          );
        }
      }
      const followTrail =
        this.follow?.kind === "plane" && this.follow.id === p.id ? motion?.trail : null;
      if (followTrail && followTrail.length > 1) {
        const tpts = followTrail
          .map((pt) => {
            const pr = this._project(pt.lat, pt.lon, w, h);
            return `${pr.x.toFixed(1)},${pr.y.toFixed(1)}`;
          })
          .join(" ");
        parts.push(`<polyline points="${tpts}" class="map-follow-trail"/>`);
      }
      const proj = this._projectShip(lat, lon, w, h);
      const hdg = (p.heading_deg ?? 0) * (Math.PI / 180);
      const sel = p.id === this.selectedPlaneId;
      const r = sel ? 8 : 6;
      const col = "#c9a4ff";
      const tipX = proj.x + Math.sin(hdg) * r;
      const tipY = proj.y - Math.cos(hdg) * r;
      const lx = proj.x + Math.sin(hdg + 2.4) * (r * 0.65);
      const ly = proj.y - Math.cos(hdg + 2.4) * (r * 0.65);
      const rx = proj.x + Math.sin(hdg - 2.4) * (r * 0.65);
      const ry = proj.y - Math.cos(hdg - 2.4) * (r * 0.65);
      if (proj.offFrame) {
        const deg = (proj.angle * 180) / Math.PI;
        parts.push(
          `<g class="map-plane-edge" data-plane-id="${p.id}" role="button" tabindex="0" transform="translate(${proj.x.toFixed(1)},${proj.y.toFixed(1)}) rotate(${deg.toFixed(1)})">
            <polygon points="0,-${r} ${r + 3},0 0,${r} -${r + 3},0" fill="${col}"/>
          </g>`,
        );
      } else {
        parts.push(
          `<g class="map-plane" data-plane-id="${p.id}" role="button" tabindex="0">
            <polygon points="${tipX.toFixed(1)},${tipY.toFixed(1)} ${lx.toFixed(1)},${ly.toFixed(1)} ${rx.toFixed(1)},${ry.toFixed(1)}" fill="${col}" class="${sel ? "map-plane-selected" : ""}"/>
            ${estimated ? `<title>Estimated position</title>` : ""}
          </g>`,
        );
      }
    }
    this._svg.innerHTML = parts.join("");
    this._svg.querySelectorAll("[data-mmsi]").forEach((el) => {
      const mmsi = Number(el.getAttribute("data-mmsi"));
      el.addEventListener("click", () => this._onSelect?.(mmsi));
    });
    this._svg.querySelectorAll("[data-plane-id]").forEach((el) => {
      const id = el.getAttribute("data-plane-id");
      el.addEventListener("click", () => this._onPlaneSelect?.(id));
    });
  }
}
