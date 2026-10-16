"""Ground voice: receive-only audio from our own antenna, behind sign-in.

Two separate models, on purpose:
  * GroundChannel  - public metadata (name, band, frequency, mode, legal status).
                     Served by GET /api/ground-voice/channels.
  * private sources - stream URLs on the Mini. Server-only config, read from the
                     file named by WICHITA_GROUND_VOICE_SOURCES. Never serialised.

Rules enforced here, server-side:
  * Malta allowlist (docs/notes/opensky.md, section 5.1). Anything else, and any
    frequency inside a forbidden range (TETRA, phones, DECT), is refused.
  * Receive-only: nothing in this module can key a transmitter. Sources are
    plain HTTP audio streams that the server reads.
  * Listener cap per channel and overall.
  * Legal gate: no audio flows until WICHITA_GROUND_VOICE_CLEARED=true, which is
    set only once the MCA/IDPC opinions are in (AGENTS.md, ground voice).
  * Pipeline: metadata and scores only; audio kept only for flagged distress
    events, for at most 72 hours.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import secrets
import shutil
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse


# ---------------------------------------------------------------- public model
@dataclass(frozen=True)
class GroundChannel:
    id: str
    name: str
    band: str
    frequency_mhz: float
    mode: str
    legal_status: str


# PMR446 analogue channels 1-8: 12.5 kHz steps from 446.00625 to 446.09375 MHz.
PMR446_MHZ: Tuple[float, ...] = (446.00625, 446.01875, 446.03125, 446.04375,
                                 446.05625, 446.06875, 446.08125, 446.09375)

# The only channels Wichita may receive. Source: docs/notes/opensky.md 5.1/5.2.
ALLOWLIST: Tuple[GroundChannel, ...] = (
    GroundChannel("ham-2m-calling", "Amateur 2 m calling", "Amateur 2 m", 145.500, "NFM",
                  "Lowest risk: licensed amateurs, plain language required"),
    GroundChannel("ham-70cm-calling", "Amateur 70 cm calling", "Amateur 70 cm", 433.500, "NFM",
                  "Lowest risk: licensed amateurs, plain language required"),
    GroundChannel("cb-ch9", "CB channel 9", "CB 27 MHz", 27.065, "AM",
                  "Low risk: open public channel, licence-exempt"),
    GroundChannel("marine-ch16", "Marine VHF channel 16", "Marine VHF", 156.800, "NFM",
                  "Defensible: distress and calling, meant to be heard by all stations"),
    GroundChannel("air-121-5", "Aeronautical emergency 121.5", "Airband", 121.500, "AM",
                  "Defensible: international aeronautical emergency frequency"),
) + tuple(
    GroundChannel(f"pmr446-ch{n}", f"PMR446 channel {n}", "PMR446", f, "NFM",
                  "Licence-exempt public-use channel, receive-only R&D")
    for n, f in enumerate(PMR446_MHZ, start=1)
)

# Allowed bands (MHz) a channel frequency must sit inside.
ALLOWED_BANDS: Tuple[Tuple[float, float, str], ...] = (
    (144.0, 146.0, "Amateur 2 m"),
    (430.0, 440.0, "Amateur 70 cm"),
    (26.965, 27.405, "CB 27 MHz"),
    (156.800, 156.800, "Marine VHF"),  # ch16 only; other marine channels are Art. 17 secret
    (121.500, 121.500, "Airband"),     # emergency only; routine ATC is not on the list
    (446.00625, 446.09375, "PMR446"),  # licence-exempt channels 1-8
)

# Never receivable, whatever config says.
FORBIDDEN_RANGES: Tuple[Tuple[float, float, str], ...] = (
    (380.0, 400.0, "TETRA emergency services"),
    (1880.0, 1900.0, "DECT"),
    (698.0, 6000.0, "Mobile phones / cellular"),
)


class NotAllowed(ValueError):
    pass


def check_frequency(freq_mhz: float) -> None:
    for lo, hi, label in FORBIDDEN_RANGES:
        if lo <= freq_mhz <= hi:
            raise NotAllowed(f"{freq_mhz} MHz is {label}: off-limits")
    for lo, hi, _ in ALLOWED_BANDS:
        if abs(freq_mhz - lo) < 1e-6 or lo <= freq_mhz <= hi:
            return
    raise NotAllowed(f"{freq_mhz} MHz is not on the Malta allowlist")


for _ch in ALLOWLIST:  # the allowlist itself must pass its own rule
    check_frequency(_ch.frequency_mhz)

CHANNELS: Dict[str, GroundChannel] = {c.id: c for c in ALLOWLIST}


def get_channel(channel_id: str) -> GroundChannel:
    ch = CHANNELS.get(channel_id)
    if ch is None:
        raise NotAllowed(f"{channel_id!r} is not an allowlisted channel")
    return ch


# -------------------------------------------------------------- private model
def _host_allowed(host: str) -> bool:
    """Sources must be our own machines: loopback or the Tailscale range."""
    if host in {"localhost"} or host.endswith(".ts.net"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip in ipaddress.ip_network("100.64.0.0/10")


def validate_source_url(url: str) -> str:
    p = urlparse(url)
    if p.scheme not in {"http", "https"} or not p.hostname:
        raise NotAllowed("source must be an http(s) audio stream")
    if not _host_allowed(p.hostname):
        raise NotAllowed("source must be on our own receiver (loopback or tailnet)")
    return url


def load_private_sources(path: Optional[str] = None) -> Dict[str, str]:
    """{channel_id: stream_url}. Unknown channels and bad URLs are dropped."""
    path = path if path is not None else os.environ.get("WICHITA_GROUND_VOICE_SOURCES", "")
    if not path or not Path(path).is_file():
        return {}
    try:
        raw = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}
    out: Dict[str, str] = {}
    for cid, url in (raw or {}).items():
        try:
            get_channel(cid)
            out[cid] = validate_source_url(str(url))
        except NotAllowed:
            continue
    return out


def legally_cleared() -> bool:
    return os.environ.get("WICHITA_GROUND_VOICE_CLEARED", "").lower() in {"1", "true", "yes"}


# ------------------------------------------------------------- listener cap
class ListenerLimit(Exception):
    pass


class ListenerLimiter:
    def __init__(self, per_channel: int, total: int):
        self.per_channel = per_channel
        self.total = total
        self._counts: Dict[str, int] = {}
        self._lock = threading.Lock()

    def acquire(self, channel_id: str) -> None:
        with self._lock:
            if sum(self._counts.values()) >= self.total:
                raise ListenerLimit("overall")
            if self._counts.get(channel_id, 0) >= self.per_channel:
                raise ListenerLimit("channel")
            self._counts[channel_id] = self._counts.get(channel_id, 0) + 1

    def release(self, channel_id: str) -> None:
        with self._lock:
            n = self._counts.get(channel_id, 0) - 1
            if n > 0:
                self._counts[channel_id] = n
            else:
                self._counts.pop(channel_id, None)

    def count(self, channel_id: Optional[str] = None) -> int:
        with self._lock:
            return self._counts.get(channel_id, 0) if channel_id else sum(self._counts.values())


LIMITER = ListenerLimiter(
    per_channel=int(os.environ.get("WICHITA_GROUND_VOICE_MAX_PER_CHANNEL", "3")),
    total=int(os.environ.get("WICHITA_GROUND_VOICE_MAX_TOTAL", "6")),
)


# ------------------------------------------------------- one-time listen tickets
# <audio> cannot send a bearer header, so a signed-in fetch mints a short ticket.
class Tickets:
    def __init__(self, ttl_sec: float = 30.0):
        self.ttl = ttl_sec
        self._t: Dict[str, Tuple[str, float]] = {}
        self._lock = threading.Lock()

    def mint(self, channel_id: str) -> str:
        tok = secrets.token_urlsafe(24)
        with self._lock:
            now = time.time()
            self._t = {k: v for k, v in self._t.items() if v[1] > now}
            self._t[tok] = (channel_id, now + self.ttl)
        return tok

    def redeem(self, tok: str, channel_id: str) -> bool:
        with self._lock:
            v = self._t.pop(tok, None)
        return bool(v and v[0] == channel_id and v[1] > time.time())


TICKETS = Tickets()


# ------------------------------------------------------------ public status
def channel_status(sources: Dict[str, str], limiter: ListenerLimiter = LIMITER,
                   cleared: Optional[bool] = None,
                   reachable: Optional[Iterable[str]] = None) -> List[dict]:
    cleared = legally_cleared() if cleared is None else cleared
    out = []
    for ch in ALLOWLIST:
        if not cleared:
            state, reason = "idle", "Waiting for the MCA and IDPC opinions; no audio is received yet."
        elif ch.id not in sources:
            state, reason = "idle", "No receiver is tuned to this channel."
        elif reachable is not None and ch.id not in set(reachable):
            state, reason = "idle", "Receiver not answering."
        elif limiter.count(ch.id) >= limiter.per_channel or limiter.count() >= limiter.total:
            state, reason = "limit", "Listener limit reached."
        else:
            state, reason = "live", "Receiving from our antenna."
        d = asdict(ch)
        d.update(state=state, reason=reason, listeners=limiter.count(ch.id),
                 max_listeners=limiter.per_channel)
        out.append(d)
    return out


# ---------------------------------------------------- sentiment/stress hook
DISTRESS_THRESHOLD = 70
RETENTION_SEC = 72 * 3600


def _events_dir() -> Path:
    return Path(os.environ.get("WICHITA_GROUND_VOICE_DIR", "data/ground_voice"))


def submit_segment(channel_id: str, wav_path: str, started_at: float,
                   scorer: Optional[Callable[[str, float], object]] = None,
                   base: Optional[Path] = None) -> dict:
    """Input point for the stress pipeline. Keeps metadata + scores; keeps the
    clip only when flagged as distress. The caller's wav is always deleted."""
    ch = get_channel(channel_id)
    base = base or _events_dir()
    base.mkdir(parents=True, exist_ok=True)
    if scorer is None:
        from stress_scorer import score_stress as scorer  # placeholder model
    res = scorer(wav_path, ch.frequency_mhz * 1e6)
    score = int(getattr(res, "score", res if isinstance(res, (int, float)) else 0))
    flagged = score >= DISTRESS_THRESHOLD
    ev = {"channel_id": ch.id, "frequency_mhz": ch.frequency_mhz, "started_at": started_at,
          "stress_score": score, "model": "stress_scorer (placeholder)", "flagged": flagged,
          "clip": None}
    if flagged:
        clips = base / "clips"
        clips.mkdir(exist_ok=True)
        dest = clips / f"{ch.id}-{int(started_at)}.wav"
        shutil.copyfile(wav_path, dest)
        ev["clip"] = dest.name
        ev["clip_expires_at"] = time.time() + RETENTION_SEC
    try:
        os.remove(wav_path)
    except OSError:
        pass
    with (base / "events.jsonl").open("a") as f:
        f.write(json.dumps(ev) + "\n")
    purge_expired(base)
    return ev


def purge_expired(base: Optional[Path] = None, now: Optional[float] = None) -> int:
    base = base or _events_dir()
    clips = base / "clips"
    if not clips.is_dir():
        return 0
    now = now or time.time()
    n = 0
    for p in clips.glob("*.wav"):
        if now - p.stat().st_mtime > RETENTION_SEC:
            p.unlink()
            n += 1
    return n
