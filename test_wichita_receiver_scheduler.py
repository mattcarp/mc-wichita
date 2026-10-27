from __future__ import annotations

import json
from pathlib import Path

import pytest

from wichita_receiver_scheduler import (
    AssignmentPlan,
    FakeClock,
    FakeReceiverDriver,
    FrequencyNotAllowed,
    JobSchedule,
    JobScheduleKind,
    JobSpec,
    MARINE_CH16_HZ,
    MARINE_CH70_DSC_HZ,
    PRIORITY_DISTRESS,
    PRIORITY_NORMAL,
    ReceiverSpec,
    SchedulerConfigError,
    assign_jobs,
    check_frequency_hz,
    default_malta_jobs,
    default_valletta_receivers,
    load_scheduler_config,
    plan_next_tune,
    plan_to_public_dict,
    run_receiver_slice,
)


def test_forbidden_tetra_rejected() -> None:
    with pytest.raises(FrequencyNotAllowed):
        check_frequency_hz(390_000_000)


def test_forbidden_lte_rejected() -> None:
    with pytest.raises(FrequencyNotAllowed):
        check_frequency_hz(2_150_000_000)


def test_adsb_1090_allowed() -> None:
    check_frequency_hz(1_090_000_000)


def test_assign_distress_jobs_share_receiver_when_bandwidth_allows() -> None:
    receivers = default_valletta_receivers()
    jobs = [j for j in default_malta_jobs() if j.id in ("marine-ch16", "marine-ch70-dsc", "ais")]
    plan = assign_jobs(receivers, jobs)
    rspdx = plan.receivers["rspdx-r2"]
    assert rspdx.groups
    distress_ids = {jid for g in rspdx.groups for jid in g.job_ids}
    assert "marine-ch16" in distress_ids
    assert "marine-ch70-dsc" in distress_ids


def test_distress_preempts_lower_priority_on_same_receiver() -> None:
    receivers = [
        ReceiverSpec(
            id="rx1",
            label="test",
            min_freq_hz=100_000_000,
            max_freq_hz=200_000_000,
            max_bandwidth_hz=10_000_000,
        )
    ]
    distress = JobSpec(
        id="marine-ch16",
        label="CH16",
        center_freq_hz=MARINE_CH16_HZ,
        bandwidth_hz=25_000,
        dwell_sec=1.0,
        priority=PRIORITY_DISTRESS,
        schedule=JobSchedule(JobScheduleKind.CONTINUOUS),
    )
    background = JobSpec(
        id="fm",
        label="FM",
        center_freq_hz=100_000_000,
        bandwidth_hz=200_000,
        dwell_sec=0.5,
        priority=PRIORITY_NORMAL,
        schedule=JobSchedule(JobScheduleKind.CONTINUOUS),
    )
    plan = assign_jobs(receivers, [distress, background])
    clock = FakeClock(0.0)
    tune = plan_next_tune(plan, "rx1", clock, slice_index=0, last_run={})
    assert tune is not None
    assert tune.preempted is True
    assert "marine-ch16" in tune.job_ids
    assert "fm" not in tune.job_ids


def test_periodic_job_not_due_returns_none_without_distress() -> None:
    receivers = default_valletta_receivers()
    jobs = [j for j in default_malta_jobs() if j.id == "meshtastic-869"]
    plan = assign_jobs(receivers, jobs)
    rx_id = next(rid for rid, rp in plan.receivers.items() if rp.groups)
    clock = FakeClock(0.0)
    assert (
        plan_next_tune(plan, rx_id, clock, slice_index=0, last_run={"meshtastic-869": 0.0})
        is None
    )
    clock.advance(61.0)
    tune = plan_next_tune(plan, rx_id, clock, slice_index=0, last_run={"meshtastic-869": 0.0})
    assert tune is not None
    assert "meshtastic-869" in tune.job_ids


def test_fake_receiver_driver_is_receive_only_surface() -> None:
    spec = ReceiverSpec("rx", "rx", 50_000_000, 500_000_000, 2_000_000)
    driver = FakeReceiverDriver(spec)
    assert not hasattr(driver, "transmit")
    driver.tune(156_800_000, 25_000)
    assert driver.tune_history == [(156_800_000, 25_000)]


def test_run_receiver_slice_advances_clock() -> None:
    spec = ReceiverSpec("rx", "rx", 50_000_000, 500_000_000, 2_000_000)
    driver = FakeReceiverDriver(spec)
    clock = FakeClock(0.0)
    from wichita_receiver_scheduler import TuneInstruction

    inst = TuneInstruction("rx", MARINE_CH16_HZ, 25_000, ("marine-ch16",), 2.5)
    run_receiver_slice(driver, inst, clock)
    assert clock.now() == 2.5
    assert driver.dwell_history == [2.5]


def test_load_example_config(tmp_path: Path) -> None:
    example = Path("config/receiver_scheduler.example.json")
    receivers, jobs = load_scheduler_config(example)
    assert len(receivers) == 3
    assert any(j.id == "marine-ch70-dsc" for j in jobs)
    plan = assign_jobs(receivers, jobs)
    assert isinstance(plan, AssignmentPlan)
    public = plan_to_public_dict(plan)
    assert public["receive_only"] is True


def test_unassignable_job_raises() -> None:
    receivers = [
        ReceiverSpec("narrow", "narrow", 156_000_000, 157_000_000, 50_000),
    ]
    jobs = [
        JobSpec(
            id="adsb",
            label="ADS-B",
            center_freq_hz=1_090_000_000,
            bandwidth_hz=1_000_000,
            dwell_sec=1.0,
            priority=PRIORITY_NORMAL,
            schedule=JobSchedule(JobScheduleKind.CONTINUOUS),
        )
    ]
    with pytest.raises(SchedulerConfigError):
        assign_jobs(receivers, jobs)


def test_ch16_and_ch70_distress_frequencies() -> None:
    assert MARINE_CH16_HZ == 156_800_000
    assert MARINE_CH70_DSC_HZ == 156_525_000
