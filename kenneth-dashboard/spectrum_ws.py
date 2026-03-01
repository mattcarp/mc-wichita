#!/usr/bin/env python3
"""Kenneth spectrum websocket server.

Streams FFT dBFS rows for live waterfall rendering.
- Tries SDRplay RSPdx-R2 via SoapySDR first
- Falls back to simulated noise floor if hardware or libs are unavailable
"""

from __future__ import annotations

import asyncio
import json
import math
import random
import signal
import time
from dataclasses import dataclass
from typing import Any

import websockets

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None  # type: ignore[assignment]

try:
    import SoapySDR

    SOAPY_OK = True
except Exception:  # pragma: no cover
    SoapySDR = None  # type: ignore[assignment]
    SOAPY_OK = False

HOST = "0.0.0.0"
PORT = 8766
DEFAULT_CENTER_HZ = 156_800_000.0
DEFAULT_BANDWIDTH_HZ = 2_000_000.0
MIN_BANDWIDTH_HZ = 2_000_000.0
DEFAULT_GAIN_DB = 38.0
FFT_SIZE = 1024
FRAME_RATE_HZ = 20.0
SAMPLES_PER_FRAME = FFT_SIZE * 4


@dataclass
class ClientConfig:
    center_hz: float = DEFAULT_CENTER_HZ
    bandwidth_hz: float = DEFAULT_BANDWIDTH_HZ


class SpectrumSource:
    def __init__(self) -> None:
        self.sim_phase = 0.0
        self.device = None
        self.stream = None
        self.center_hz = DEFAULT_CENTER_HZ
        self.sample_rate = DEFAULT_BANDWIDTH_HZ
        self.using_sdr = False
        self.source_name = "simulated"

        if np is None or not SOAPY_OK:
            return

        # Try explicit SDRplay, then any available SoapySDR RX device.
        for args in ({"driver": "sdrplay"}, {}):
            try:
                self.device = SoapySDR.Device(args)
                self.device.setSampleRate(SoapySDR.SOAPY_SDR_RX, 0, self.sample_rate)
                self.device.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, self.center_hz)
                self.device.setGain(SoapySDR.SOAPY_SDR_RX, 0, DEFAULT_GAIN_DB)
                self.stream = self.device.setupStream(SoapySDR.SOAPY_SDR_RX, SoapySDR.SOAPY_SDR_CF32)
                self.device.activateStream(self.stream)
                self.using_sdr = True
                self.source_name = "sdrplay"
                break
            except Exception:
                self.device = None
                self.stream = None

    def close(self) -> None:
        if not self.using_sdr or self.device is None or self.stream is None:
            return

        try:
            self.device.deactivateStream(self.stream)
        except Exception:
            pass

        try:
            self.device.closeStream(self.stream)
        except Exception:
            pass

        self.stream = None
        self.device = None

    def _set_tuning(self, center_hz: float, bandwidth_hz: float) -> None:
        if not self.using_sdr or self.device is None:
            return

        new_sr = max(MIN_BANDWIDTH_HZ, bandwidth_hz)
        if abs(new_sr - self.sample_rate) > 1:
            self.sample_rate = new_sr
            self.device.setSampleRate(SoapySDR.SOAPY_SDR_RX, 0, self.sample_rate)

        if abs(center_hz - self.center_hz) > 1:
            self.center_hz = center_hz
            self.device.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, self.center_hz)

    def _sdr_frame(self, center_hz: float, bandwidth_hz: float) -> list[float]:
        assert np is not None

        if self.device is None or self.stream is None:
            raise RuntimeError("SDR stream unavailable")

        self._set_tuning(center_hz, bandwidth_hz)

        iq = np.empty(SAMPLES_PER_FRAME, dtype=np.complex64)
        result = self.device.readStream(self.stream, [iq], SAMPLES_PER_FRAME, timeoutUs=120000)

        if result.ret <= 0:
            raise RuntimeError(f"No IQ samples read (ret={result.ret})")

        samples = iq[: result.ret]
        if samples.size < 128:
            raise RuntimeError("Insufficient IQ samples for FFT")

        window = np.hanning(samples.size)
        fft = np.fft.fftshift(np.fft.fft(samples * window, n=FFT_SIZE))
        mag = np.abs(fft)

        # Approximate dBFS scale with a conservative floor.
        dbfs = 20.0 * np.log10(np.maximum(mag, 1e-12))
        dbfs -= 20.0 * math.log10(FFT_SIZE)
        dbfs = np.clip(dbfs, -130.0, 10.0)

        return dbfs.astype(np.float32).tolist()

    def _sim_frame(self, center_hz: float) -> list[float]:
        bins = FFT_SIZE
        floor = -104.0
        now = time.time()

        if np is None:
            values = []
            for i in range(bins):
                noise = random.gauss(0, 2.2)
                wave = 2.2 * math.sin((i / bins) * math.tau * 3.0 + self.sim_phase)
                values.append(floor + noise + wave)
        else:
            x = np.linspace(0.0, 1.0, bins, endpoint=False)
            noise = np.random.normal(0.0, 2.0, bins)
            ripple = 2.5 * np.sin((x * math.tau * 3.0) + self.sim_phase)
            values = (floor + noise + ripple).tolist()

        # Add three moving synthetic carriers so UI visibly reacts.
        carriers = [0.23, 0.52, 0.77]
        drift = [0.035, 0.055, 0.025]
        for idx, base in enumerate(carriers):
            pos = int(((base + math.sin(now * drift[idx]) * 0.03) % 1.0) * bins)
            amp = -55.0 - idx * 7.0
            for delta in range(-3, 4):
                tap = pos + delta
                if 0 <= tap < bins:
                    bump = amp - abs(delta) * 6.0
                    values[tap] = max(values[tap], bump)

        self.sim_phase += 0.2 + (center_hz % 10_000_000) / 80_000_000
        return values

    def frame(self, config: ClientConfig) -> dict[str, Any]:
        spectrum: list[float]

        if self.using_sdr:
            try:
                spectrum = self._sdr_frame(config.center_hz, config.bandwidth_hz)
            except Exception:
                self.using_sdr = False
                self.source_name = "simulated"
                spectrum = self._sim_frame(config.center_hz)
        else:
            spectrum = self._sim_frame(config.center_hz)

        return {
            "type": "spectrum",
            "timestamp": time.time(),
            "center_hz": config.center_hz,
            "bandwidth_hz": max(MIN_BANDWIDTH_HZ, config.bandwidth_hz),
            "frame_rate_hz": FRAME_RATE_HZ,
            "fft_size": FFT_SIZE,
            "source": self.source_name,
            "dbfs": spectrum,
        }


async def receive_config(ws: websockets.WebSocketServerProtocol, config: ClientConfig) -> None:
    async for raw in ws:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if payload.get("type") not in {"set_config", "set_center_freq"}:
            continue

        if "center_hz" in payload:
            try:
                config.center_hz = float(payload["center_hz"])
            except (TypeError, ValueError):
                pass

        if "bandwidth_hz" in payload:
            try:
                config.bandwidth_hz = max(MIN_BANDWIDTH_HZ, float(payload["bandwidth_hz"]))
            except (TypeError, ValueError):
                pass


async def stream_fft(ws: websockets.WebSocketServerProtocol, config: ClientConfig, source: SpectrumSource) -> None:
    interval = 1.0 / FRAME_RATE_HZ
    while True:
        started = time.perf_counter()
        frame = source.frame(config)
        await ws.send(json.dumps(frame))
        elapsed = time.perf_counter() - started
        await asyncio.sleep(max(0.0, interval - elapsed))


async def handle_client(ws: websockets.WebSocketServerProtocol) -> None:
    config = ClientConfig()
    source = SpectrumSource()

    config_msg = {
        "type": "hello",
        "center_hz": config.center_hz,
        "bandwidth_hz": config.bandwidth_hz,
        "source": source.source_name,
    }
    await ws.send(json.dumps(config_msg))

    stream_task = asyncio.create_task(stream_fft(ws, config, source))
    recv_task = asyncio.create_task(receive_config(ws, config))

    done, pending = await asyncio.wait(
        {stream_task, recv_task}, return_when=asyncio.FIRST_COMPLETED
    )

    for task in pending:
        task.cancel()

    for task in done:
        task.exception()

    source.close()


async def main() -> None:
    stop_event = asyncio.Event()

    def _stop() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _stop)

    async with websockets.serve(handle_client, HOST, PORT, ping_interval=20, ping_timeout=20):
        print(f"Spectrum WebSocket listening on ws://{HOST}:{PORT}")
        await stop_event.wait()


if __name__ == "__main__":
    asyncio.run(main())
