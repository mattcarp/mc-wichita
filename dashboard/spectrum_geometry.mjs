export const PLOT_PAD_X = 10;
export const MARINE_FALLBACK_MIN_MHZ = 156.45;
export const MARINE_FALLBACK_MAX_MHZ = 162.4;

export function psdSpan(psd) {
  const minF = psd?.plot_min_mhz ?? MARINE_FALLBACK_MIN_MHZ;
  const maxF = psd?.plot_max_mhz ?? MARINE_FALLBACK_MAX_MHZ;
  const drawMin = psd?.draw_min_mhz ?? minF;
  const drawMax = psd?.draw_max_mhz ?? maxF;
  return { minF, maxF, drawMin, drawMax };
}

export function plotInnerWidth(w) {
  return Math.max(1, w - 2 * PLOT_PAD_X);
}

export function freqToAxisX(mhz, w, span) {
  const { minF, maxF } = span;
  return ((mhz - minF) / (maxF - minF + 1e-9)) * w;
}

/** Map MHz to canvas x with horizontal inset (single source for trace, markers, waterfall). */
export function freqToPlotX(mhz, w, span) {
  return PLOT_PAD_X + freqToAxisX(mhz, plotInnerWidth(w), span);
}

export function samplePsdAtMhz(psd, mhz) {
  const freqs = psd.freq_mhz;
  const vals = psd.psd_db_per_hz;
  if (!freqs?.length) return null;
  if (mhz <= freqs[0]) return vals[0];
  if (mhz >= freqs[freqs.length - 1]) return vals[vals.length - 1];
  for (let i = 1; i < freqs.length; i++) {
    if (freqs[i] >= mhz) {
      const t = (mhz - freqs[i - 1]) / (freqs[i] - freqs[i - 1]);
      return vals[i - 1] + t * (vals[i] - vals[i - 1]);
    }
  }
  return vals[vals.length - 1];
}

/** Last trace vertex x for a PSD payload (mirrors drawSpectrum loop). */
export function spectrumTraceEndX(psd, cssWidth) {
  const span = psdSpan(psd);
  const { drawMin, drawMax } = span;
  const freqs = psd.freq_mhz || [];
  const vals = psd.psd_db_per_hz || [];
  const tunerMhz = psd.tuner_center_mhz;
  const dcHalfWidth = 0.06;
  let lastFm = null;
  let lastX = null;
  for (let i = 0; i < freqs.length; i++) {
    const fm = freqs[i];
    if (fm < drawMin || fm > drawMax) continue;
    if (tunerMhz && Math.abs(fm - tunerMhz) < dcHalfWidth) continue;
    lastFm = fm;
    lastX = freqToPlotX(fm, cssWidth, span);
  }
  if (lastFm != null && lastFm < drawMax - 1e-4) {
    lastX = freqToPlotX(drawMax, cssWidth, span);
    lastFm = drawMax;
  }
  return { lastX, lastFm, expectedX: freqToPlotX(drawMax, cssWidth, span) };
}
