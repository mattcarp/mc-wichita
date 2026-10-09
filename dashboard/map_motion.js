/**
 * Smooth display positions between real receiver reports.
 * Interpolation approach adapted from God's Eye View (MIT)
 * https://github.com/bilawalsidhu/gods-eye-view — see dashboard/data/ATTRIBUTION.md
 */

export const ESTIMATED_MAX_MS = 60_000;

/**
 * @param {number} lat1
 * @param {number} lon1
 * @param {number} lat2
 * @param {number} lon2
 * @param {number} t 0..1
 */
export function lerpLatLon(lat1, lon1, lat2, lon2, t) {
  return {
    lat: lat1 + (lat2 - lat1) * t,
    lon: lon1 + (lon2 - lon1) * t,
  };
}

function extrapolate(lat, lon, speedKn, cogDeg, dtSec) {
  if (speedKn == null || cogDeg == null || speedKn < 0.3 || dtSec <= 0) {
    return { lat, lon };
  }
  const km = (speedKn * 1.852 * dtSec) / 3600;
  const brng = (cogDeg * Math.PI) / 180;
  const dLat = (km / 111.32) * Math.cos(brng);
  const dLon = (km / (111.32 * Math.cos((lat * Math.PI) / 180))) * Math.sin(brng);
  return { lat: lat + dLat, lon: lon + dLon };
}

export class EntityMotion {
  constructor(pollIntervalMs = 5000) {
    this.pollIntervalMs = pollIntervalMs;
    /** @type {Map<string, {samples: Array<{lat:number,lon:number,t:number,speedKn?:number,cogDeg?:number}>, trail: Array<{lat:number,lon:number,t:number}>}>} */
    this._state = new Map();
    this._reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  /**
   * @param {string} key
   * @param {{lat:number,lon:number,last_signal_s?:number,speed_kn?:number,cog_deg?:number,heading_deg?:number}} entity
   * @param {number} nowMs
   */
  ingest(key, entity, nowMs) {
    if (entity.lat == null || entity.lon == null) return;
    const reportAgeMs = (entity.last_signal_s ?? 0) * 1000;
    const sampleT = nowMs - reportAgeMs;
    let row = this._state.get(key);
    if (!row) {
      row = { samples: [], trail: [] };
      this._state.set(key, row);
    }
    const last = row.samples[row.samples.length - 1];
    const moved =
      !last ||
      Math.abs(last.lat - entity.lat) > 1e-6 ||
      Math.abs(last.lon - entity.lon) > 1e-6;
    if (moved) {
      const cog = entity.cog_deg ?? entity.heading_deg;
      row.samples.push({
        lat: entity.lat,
        lon: entity.lon,
        t: sampleT,
        speedKn: entity.speed_kn ?? entity.speed_kts,
        cogDeg: cog,
      });
      if (row.samples.length > 8) row.samples.shift();
      row.trail.push({ lat: entity.lat, lon: entity.lon, t: sampleT });
      if (row.trail.length > 40) row.trail.shift();
    }
  }

  /**
   * @returns {{lat:number,lon:number,estimated:boolean,trail:Array<{lat:number,lon:number}>}}
   */
  displayPosition(key, nowMs) {
    const row = this._state.get(key);
    if (!row || !row.samples.length) return null;
    if (this._reducedMotion) {
      const s = row.samples[row.samples.length - 1];
      return { lat: s.lat, lon: s.lon, estimated: false, trail: row.trail };
    }
    const displayT = nowMs - this.pollIntervalMs;
    const samples = row.samples;
    let a = samples[0];
    let b = samples[samples.length - 1];
    for (let i = 0; i < samples.length - 1; i++) {
      if (samples[i].t <= displayT && samples[i + 1].t >= displayT) {
        a = samples[i];
        b = samples[i + 1];
        break;
      }
    }
    if (displayT <= a.t) {
      return { lat: a.lat, lon: a.lon, estimated: false, trail: row.trail };
    }
    if (displayT >= b.t) {
      const dtSec = (displayT - b.t) / 1000;
      if (dtSec * 1000 > ESTIMATED_MAX_MS) {
        return { lat: b.lat, lon: b.lon, estimated: false, trail: row.trail };
      }
      const ex = extrapolate(b.lat, b.lon, b.speedKn, b.cogDeg, dtSec);
      return { lat: ex.lat, lon: ex.lon, estimated: true, trail: row.trail };
    }
    const span = b.t - a.t || 1;
    const t = (displayT - a.t) / span;
    const p = lerpLatLon(a.lat, a.lon, b.lat, b.lon, t);
    return { lat: p.lat, lon: p.lon, estimated: false, trail: row.trail };
  }

  clear(key) {
    this._state.delete(key);
  }
}
