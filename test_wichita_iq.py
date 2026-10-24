from pathlib import Path

from wichita_iq import read_sdriq

FIX = Path(__file__).resolve().parent / "fixtures" / "distress"


def test_sdriq_header_matches_sdrangel_issue_recording():
    cap = read_sdriq(FIX / "selective_individual_call_2.2023-06-03T19_21_59_833.sdriq")
    assert cap.sample_rate_hz == 2_500_000
    assert cap.center_freq_hz == 156_525_000
    assert len(cap.samples) > 1_000_000
