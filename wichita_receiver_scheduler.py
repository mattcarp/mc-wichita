"""Receive-only multi-receiver job scheduler (pure logic).

Time-shares physical SDRs across monitoring jobs (AIS, ADS-B, marine distress,
airband, sensors, etc.). Drivers sit behind a small protocol so unit tests use a
fake clock and fake receivers. Nothing here can transmit.

Forbidden bands (TETRA, cellular, DECT) are rejected at config parse time.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple

logger = logging.getLogger(__name__)

# MHz ranges that must never be scheduled for tune (job center frequency).
# Deliberately narrower than the ground-voice blanket block: ADS-B 1090, ISM 433/868, etc. stay valid.
FORBIDDEN_RANGES_MHZ: Tuple[Tuple[float, float, str], ...] = (
    (380.0, 400.0, "TETRA emergency services"),
    (1880.0, 1900.0, "DECT"),
    (703.0, 748.0, "LTE 700"),
    (791.0, 862.0, "LTE 800"),
    (880.0, 915.0, "GSM uplink"),
    (925.0, 960.0, "GSM downlink"),
    (1710.0, 1785.0, "LTE/UMTS uplink"),
    (1805.0, 1880.0, "LTE/UMTS downlink"),
    (1920.0, 1980.0, "LTE uplink"),
    (2110.0, 2170.0, "LTE downlink"),
    (2500.0, 2570.0, "LTE TDD"),
    (2620.0, 2690.0, "LTE FDD"),
    (3400.0, 3800.0, "5G NR"),
)

PRIORITY_DISTRESS = 1000
PRIORITY_HIGH = 500
PRIORITY_NORMAL = 100
PRIORITY_BACKGROUND = 10

MARINE_CH16_HZ = 156_800_000
MARINE_CH70_DSC_HZ = 156_525_000

DISTRESS_JOB_IDS = frozenset({"marine-ch16", "marine-ch70-dsc"})


class FrequencyNotAllowed(ValueError):
    pass


class SchedulerConfigError(ValueError):
    pass


def check_frequency_hz(freq_hz: int) -> None:
    mhz = freq_hz / 1_000_000.0
    for lo, hi, label in FORBIDDEN_RANGES_MHZ:
        if lo <= mhz <= hi:
            raise FrequencyNotAllowed(f"{mhz:.6f} MHz is {label}: off-limits")


class JobScheduleKind(str, Enum):
    CONTINUOUS = "continuous"
    PERIODIC = "periodic"


@dataclass(frozen=True)
class JobSchedule:
    kind: JobScheduleKind
    period_sec: Optional[float] = None

    def validate(self) -> None:
        if self.kind == JobScheduleKind.PERIODIC:
            if self.period_sec is None or self.period_sec <= 0:
                raise SchedulerConfigError("periodic jobs require period_sec > 0")


@dataclass(frozen=True)
class ReceiverSpec:
    id: str
    label: str
    min_freq_hz: int
    max_freq_hz: int
    max_bandwidth_hz: int

    def validate(self) -> None:
        if self.min_freq_hz <= 0 or self.max_freq_hz <= self.min_freq_hz:
            raise SchedulerConfigError(f"receiver {self.id}: invalid frequency range")
        if self.max_bandwidth_hz <= 0:
            raise SchedulerConfigError(f"receiver {self.id}: max_bandwidth_hz must be positive")


@dataclass(frozen=True)
class JobSpec:
    id: str
    label: str
    center_freq_hz: int
    bandwidth_hz: int
    dwell_sec: float
    priority: int
    schedule: JobSchedule
    preferred_receiver_id: Optional[str] = None

    def validate(self) -> None:
        if self.bandwidth_hz <= 0:
            raise SchedulerConfigError(f"job {self.id}: bandwidth_hz must be positive")
        if self.dwell_sec <= 0:
            raise SchedulerConfigError(f"job {self.id}: dwell_sec must be positive")
        self.schedule.validate()
        check_frequency_hz(self.center_freq_hz)

    @property
    def is_distress(self) -> bool:
        return self.id in DISTRESS_JOB_IDS or self.priority >= PRIORITY_DISTRESS


@dataclass(frozen=True)
class TuneGroup:
    """Jobs captured together in one wideband tune."""

    center_freq_hz: int
    bandwidth_hz: int
    jobs: Tuple[JobSpec, ...]
    dwell_sec: float

    @property
    def job_ids(self) -> Tuple[str, ...]:
        return tuple(j.id for j in self.jobs)


@dataclass
class ReceiverPlan:
    receiver_id: str
    groups: List[TuneGroup] = field(default_factory=list)


@dataclass
class AssignmentPlan:
    receivers: Dict[str, ReceiverPlan]

    def groups_for(self, receiver_id: str) -> List[TuneGroup]:
        plan = self.receivers.get(receiver_id)
        return list(plan.groups) if plan else []


@dataclass
class TuneInstruction:
    receiver_id: str
    center_freq_hz: int
    bandwidth_hz: int
    job_ids: Tuple[str, ...]
    dwell_sec: float
    preempted: bool = False


class Clock(Protocol):
    def now(self) -> float:
        """Monotonic or wall time in seconds."""


class FakeClock:
    def __init__(self, t: float = 0.0) -> None:
        self._t = t

    def now(self) -> float:
        return self._t

    def advance(self, dt: float) -> None:
        self._t += dt


class ReceiverDriver(Protocol):
    """Receive-only hardware facade. Implementations must not expose transmit."""

    receiver_id: str

    def tune(self, center_freq_hz: int, bandwidth_hz: int) -> None:
        ...

    def receive_dwell(self, dwell_sec: float) -> None:
        ...


class FakeReceiverDriver:
    """In-memory driver for tests."""

    def __init__(self, spec: ReceiverSpec) -> None:
        self.spec = spec
        self.receiver_id = spec.id
        self.tune_history: List[Tuple[int, int]] = []
        self.dwell_history: List[float] = []

    def tune(self, center_freq_hz: int, bandwidth_hz: int) -> None:
        if not (self.spec.min_freq_hz <= center_freq_hz <= self.spec.max_freq_hz):
            raise ValueError("center frequency outside receiver range")
        if bandwidth_hz > self.spec.max_bandwidth_hz:
            raise ValueError("bandwidth exceeds receiver capability")
        check_frequency_hz(center_freq_hz)
        self.tune_history.append((center_freq_hz, bandwidth_hz))

    def receive_dwell(self, dwell_sec: float) -> None:
        self.dwell_history.append(dwell_sec)


def _job_span_hz(job: JobSpec) -> Tuple[int, int]:
    half = job.bandwidth_hz // 2
    return job.center_freq_hz - half, job.center_freq_hz + half


def _group_span_and_bw(jobs: Sequence[JobSpec]) -> Tuple[int, int, int]:
    low = min(_job_span_hz(j)[0] for j in jobs)
    high = max(_job_span_hz(j)[1] for j in jobs)
    center = (low + high) // 2
    bandwidth = high - low
    if bandwidth <= 0:
        bandwidth = max(j.bandwidth_hz for j in jobs)
    return center, bandwidth, high - low


def _jobs_fit_receiver(jobs: Sequence[JobSpec], receiver: ReceiverSpec) -> bool:
    for job in jobs:
        if not (receiver.min_freq_hz <= job.center_freq_hz <= receiver.max_freq_hz):
            return False
    center, need_bw, _ = _group_span_and_bw(jobs)
    if not (receiver.min_freq_hz <= center <= receiver.max_freq_hz):
        return False
    return need_bw <= receiver.max_bandwidth_hz


def _make_tune_group(jobs: Sequence[JobSpec]) -> TuneGroup:
    center, need_bw, _ = _group_span_and_bw(jobs)
    dwell = max(j.dwell_sec for j in jobs)
    return TuneGroup(
        center_freq_hz=center,
        bandwidth_hz=need_bw,
        jobs=tuple(jobs),
        dwell_sec=dwell,
    )


def pack_jobs_on_receiver(jobs: Sequence[JobSpec], receiver: ReceiverSpec) -> List[TuneGroup]:
    """Partition jobs into sequential tune groups that each fit the receiver BW."""
    remaining = sorted(jobs, key=lambda j: (-j.priority, j.id))
    groups: List[TuneGroup] = []
    while remaining:
        seed = remaining.pop(0)
        bundle: List[JobSpec] = [seed]
        i = 0
        while i < len(remaining):
            candidate = remaining[i]
            trial = bundle + [candidate]
            if _jobs_fit_receiver(trial, receiver):
                bundle.append(candidate)
                remaining.pop(i)
            else:
                i += 1
        groups.append(_make_tune_group(bundle))
    return groups


def assign_jobs(
    receivers: Sequence[ReceiverSpec],
    jobs: Sequence[JobSpec],
) -> AssignmentPlan:
    """Assign each job to a receiver and build per-receiver tune groups."""
    rx_by_id = {r.id: r for r in receivers}
    for r in receivers:
        r.validate()
    for j in jobs:
        j.validate()

    buckets: Dict[str, List[JobSpec]] = {r.id: [] for r in receivers}
    unassigned: List[JobSpec] = []

    ordered_jobs = sorted(jobs, key=lambda j: (-j.priority, j.id))
    for job in ordered_jobs:
        candidates: List[ReceiverSpec] = []
        if job.preferred_receiver_id:
            pref = rx_by_id.get(job.preferred_receiver_id)
            if pref is None:
                raise SchedulerConfigError(f"job {job.id}: unknown preferred_receiver_id")
            candidates = [pref]
        else:
            candidates = list(receivers)

        placed = False
        for rx in candidates:
            if job.center_freq_hz < rx.min_freq_hz or job.center_freq_hz > rx.max_freq_hz:
                continue
            if job.bandwidth_hz > rx.max_bandwidth_hz:
                continue
            buckets[rx.id].append(job)
            placed = True
            break
        if not placed:
            unassigned.append(job)

    if unassigned:
        ids = ", ".join(j.id for j in unassigned)
        raise SchedulerConfigError(f"no receiver can host jobs: {ids}")

    plan: Dict[str, ReceiverPlan] = {}
    for rx in receivers:
        job_list = buckets[rx.id]
        if not job_list:
            plan[rx.id] = ReceiverPlan(receiver_id=rx.id, groups=[])
            continue
        groups = pack_jobs_on_receiver(job_list, rx)
        distress_groups = [g for g in groups if any(j.is_distress for j in g.jobs)]
        other_groups = [g for g in groups if not any(j.is_distress for j in g.jobs)]
        groups = distress_groups + other_groups
        plan[rx.id] = ReceiverPlan(receiver_id=rx.id, groups=groups)
    return AssignmentPlan(receivers=plan)


def _continuous_distress_groups(groups: Sequence[TuneGroup]) -> List[TuneGroup]:
    out: List[TuneGroup] = []
    for g in groups:
        if any(j.is_distress and j.schedule.kind == JobScheduleKind.CONTINUOUS for j in g.jobs):
            out.append(g)
    return out


def plan_next_tune(
    assignment: AssignmentPlan,
    receiver_id: str,
    clock: Clock,
    *,
    slice_index: int,
    last_run: Mapping[str, float],
) -> Optional[TuneInstruction]:
    """Pick the next tune for one receiver at ``clock.now()``."""
    groups = assignment.groups_for(receiver_id)
    if not groups:
        return None

    now = clock.now()
    distress = _continuous_distress_groups(groups)
    if distress:
        g = distress[slice_index % len(distress)]
        return TuneInstruction(
            receiver_id=receiver_id,
            center_freq_hz=g.center_freq_hz,
            bandwidth_hz=g.bandwidth_hz,
            job_ids=g.job_ids,
            dwell_sec=g.dwell_sec,
            preempted=True,
        )

    eligible: List[TuneGroup] = []
    for g in groups:
        due = False
        for job in g.jobs:
            if job.schedule.kind == JobScheduleKind.CONTINUOUS:
                due = True
                break
            period = job.schedule.period_sec or 0.0
            last = last_run.get(job.id, 0.0)
            if now - last >= period:
                due = True
                break
        if due:
            eligible.append(g)

    if not eligible:
        return None

    g = eligible[slice_index % len(eligible)]
    return TuneInstruction(
        receiver_id=receiver_id,
        center_freq_hz=g.center_freq_hz,
        bandwidth_hz=g.bandwidth_hz,
        job_ids=g.job_ids,
        dwell_sec=g.dwell_sec,
        preempted=False,
    )


def run_receiver_slice(
    driver: ReceiverDriver,
    instruction: TuneInstruction,
    clock: FakeClock,
) -> None:
    """Apply one tune instruction (used by tests and dry-run runners)."""
    driver.tune(instruction.center_freq_hz, instruction.bandwidth_hz)
    driver.receive_dwell(instruction.dwell_sec)
    if isinstance(clock, FakeClock):
        clock.advance(instruction.dwell_sec)


def _parse_schedule(raw: Mapping[str, Any]) -> JobSchedule:
    kind = JobScheduleKind(str(raw.get("kind", "continuous")).lower())
    period = raw.get("period_sec")
    return JobSchedule(kind=kind, period_sec=float(period) if period is not None else None)


def load_scheduler_config(path: Path) -> Tuple[List[ReceiverSpec], List[JobSpec]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    receivers = [
        ReceiverSpec(
            id=str(r["id"]),
            label=str(r.get("label", r["id"])),
            min_freq_hz=int(r["min_freq_hz"]),
            max_freq_hz=int(r["max_freq_hz"]),
            max_bandwidth_hz=int(r["max_bandwidth_hz"]),
        )
        for r in data.get("receivers", [])
    ]
    jobs = [
        JobSpec(
            id=str(j["id"]),
            label=str(j.get("label", j["id"])),
            center_freq_hz=int(j["center_freq_hz"]),
            bandwidth_hz=int(j["bandwidth_hz"]),
            dwell_sec=float(j["dwell_sec"]),
            priority=int(j.get("priority", PRIORITY_NORMAL)),
            schedule=_parse_schedule(j.get("schedule", {})),
            preferred_receiver_id=j.get("preferred_receiver_id"),
        )
        for j in data.get("jobs", [])
    ]
    if not receivers:
        raise SchedulerConfigError("config must declare at least one receiver")
    return receivers, jobs


def default_config_path() -> Path:
    raw = os.environ.get("WICHITA_RECEIVER_SCHEDULER_CONFIG", "config/receiver_scheduler.json").strip()
    return Path(raw).expanduser()


def scheduler_enabled() -> bool:
    return os.environ.get("WICHITA_RECEIVER_SCHEDULER_ENABLED", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def build_plan_from_env() -> Optional[AssignmentPlan]:
    if not scheduler_enabled():
        return None
    path = default_config_path()
    if not path.is_file():
        logger.warning("receiver scheduler enabled but config missing: %s", path)
        return None
    receivers, jobs = load_scheduler_config(path)
    return assign_jobs(receivers, jobs)


def plan_to_public_dict(plan: AssignmentPlan) -> Dict[str, Any]:
    out: Dict[str, Any] = {"receive_only": True, "receivers": {}}
    for rx_id, rx_plan in plan.receivers.items():
        out["receivers"][rx_id] = {
            "groups": [
                {
                    "center_freq_hz": g.center_freq_hz,
                    "center_freq_mhz": round(g.center_freq_hz / 1e6, 6),
                    "bandwidth_hz": g.bandwidth_hz,
                    "dwell_sec": g.dwell_sec,
                    "job_ids": list(g.job_ids),
                    "distress": any(j.is_distress for j in g.jobs),
                }
                for g in rx_plan.groups
            ]
        }
    return out


def default_malta_jobs() -> List[JobSpec]:
    """Reference job set for docs/tests (not loaded unless config says so)."""
    return [
        JobSpec(
            id="marine-ch16",
            label="Marine VHF CH16 distress/calling",
            center_freq_hz=MARINE_CH16_HZ,
            bandwidth_hz=25_000,
            dwell_sec=1.0,
            priority=PRIORITY_DISTRESS,
            schedule=JobSchedule(JobScheduleKind.CONTINUOUS),
        ),
        JobSpec(
            id="marine-ch70-dsc",
            label="Marine VHF CH70 DSC",
            center_freq_hz=MARINE_CH70_DSC_HZ,
            bandwidth_hz=25_000,
            dwell_sec=1.0,
            priority=PRIORITY_DISTRESS,
            schedule=JobSchedule(JobScheduleKind.CONTINUOUS),
        ),
        JobSpec(
            id="ais",
            label="AIS 161.975 / 162.025",
            center_freq_hz=161_975_000,
            bandwidth_hz=200_000,
            dwell_sec=2.0,
            priority=PRIORITY_HIGH,
            schedule=JobSchedule(JobScheduleKind.CONTINUOUS),
            preferred_receiver_id="rspdx-r2",
        ),
        JobSpec(
            id="adsb-1090",
            label="ADS-B 1090 MHz",
            center_freq_hz=1_090_000_000,
            bandwidth_hz=2_000_000,
            dwell_sec=2.0,
            priority=PRIORITY_HIGH,
            schedule=JobSchedule(JobScheduleKind.CONTINUOUS),
            preferred_receiver_id="rtl-sdr",
        ),
        JobSpec(
            id="airband",
            label="Airband 118-137 scan anchor",
            center_freq_hz=127_500_000,
            bandwidth_hz=2_000_000,
            dwell_sec=0.5,
            priority=PRIORITY_NORMAL,
            schedule=JobSchedule(JobScheduleKind.PERIODIC, period_sec=30.0),
        ),
        JobSpec(
            id="meshtastic-869",
            label="LoRa / Meshtastic 869.525 MHz",
            center_freq_hz=869_525_000,
            bandwidth_hz=250_000,
            dwell_sec=1.0,
            priority=PRIORITY_BACKGROUND,
            schedule=JobSchedule(JobScheduleKind.PERIODIC, period_sec=60.0),
        ),
    ]


def default_valletta_receivers() -> List[ReceiverSpec]:
    return [
        ReceiverSpec(
            id="rspdx-r2",
            label="SDRplay RSPdx-R2",
            min_freq_hz=1_000_000,
            max_freq_hz=2_000_000_000,
            max_bandwidth_hz=10_000_000,
        ),
        ReceiverSpec(
            id="rtl-sdr",
            label="RTL-SDR",
            min_freq_hz=24_000_000,
            max_freq_hz=1_766_000_000,
            max_bandwidth_hz=2_400_000,
        ),
        ReceiverSpec(
            id="hackrf",
            label="HackRF One",
            min_freq_hz=1_000_000,
            max_freq_hz=6_000_000_000,
            max_bandwidth_hz=20_000_000,
        ),
    ]
