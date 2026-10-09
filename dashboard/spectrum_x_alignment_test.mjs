import test from "node:test";
import assert from "node:assert/strict";
import { freqToPlotX, psdSpan, spectrumTraceEndX } from "./spectrum_geometry.mjs";

test("draw_max maps just right of AIS2 on balcony axis", () => {
  const w = 800;
  const psd = {
    plot_min_mhz: 156.238,
    plot_max_mhz: 162.237,
    draw_min_mhz: 156.55,
    draw_max_mhz: 162.041,
    freq_mhz: [156.55, 161.0, 162.041],
    psd_db_per_hz: [-110, -108, -112],
    tuner_center_mhz: 159.238,
  };
  const span = psdSpan(psd);
  const xAis2 = freqToPlotX(162.025, w, span);
  const xEnd = freqToPlotX(psd.draw_max_mhz, w, span);
  assert.ok(xEnd > xAis2);
  const frac = (psd.draw_max_mhz - span.minF) / (span.maxF - span.minF);
  assert.ok(frac > 0.95);
});

test("last drawn trace x within 1px of freqToPlotX(draw_max)", () => {
  const psd = {
    plot_min_mhz: 156.238,
    plot_max_mhz: 162.237,
    draw_min_mhz: 156.55,
    draw_max_mhz: 162.041,
    freq_mhz: [156.55, 160.0, 161.9, 162.041],
    psd_db_per_hz: [-110, -108, -109, -112],
    tuner_center_mhz: 159.238,
  };
  const { lastX, expectedX } = spectrumTraceEndX(psd, 640);
  assert.ok(Math.abs(lastX - expectedX) <= 1);
});
