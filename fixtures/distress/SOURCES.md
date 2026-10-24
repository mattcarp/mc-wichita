# Distress decoder test fixtures (real recordings only)

| File | Source | Verified decode |
| --- | --- | --- |
| `routine_call.wav` | [SDRangel issue #1707](https://github.com/f4exb/sdrangel/issues/1707#issuecomment-1573399070) attachment `routine_call.zip` (VHF Ch 70 selective individual call, contributor tttonyyy) | Yes — MMSI 233333334 / 201444555 |
| `selective_individual_call_2.2023-06-03T19_21_59_833.sdriq` | [SDRangel issue #1707](https://github.com/f4exb/sdrangel/issues/1707#issuecomment-1575310120) (24-bit IQ, 2.5 MS/s, centre 156.525 MHz) | **Not yet** — IQ FM/FSK chain does not recover a valid DSC message in CI (see `test_wichita_distress.py`) |
| `sarsat_selftest_beacon.wav` | [HTCommander](https://github.com/ylianst/HTCommander/blob/main/src/test/sarsat_samples/sarsat_selftest_beacon.wav) (Apache-2.0; real 406 MHz self-test recording) | Yes — hex `1C72091A2B3FDFF`, France (227), ELT(DT), 42.954° N 1.364° E |

Zip archives in this folder are kept only as download receipts; tests use the extracted files above.
