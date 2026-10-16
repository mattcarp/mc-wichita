import unittest

from scan_config import load_scan_config


class ScanConfigTest(unittest.TestCase):
    def test_scan_config_loads_and_contains_requested_bands(self) -> None:
        cfg = load_scan_config()
        entries = cfg["bands"]

        lookup = {
            (entry["name"], round(entry["frequency_mhz"], 5)): entry for entry in entries
        }

        required = [
            ("EPIRB 406", 406.028, "nfm"),
            ("AIS 1", 161.975, "nfm"),
            ("AIS 2", 162.025, "nfm"),
            ("Marine CH16", 156.800, "nfm"),
            ("Marine CH09", 156.450, "nfm"),
            ("Marine CH13", 156.650, "nfm"),
            ("Marine CH22A", 157.100, "nfm"),
            # Malta follows the IARU Region 1 (European) amateur band plan.
            ("Amateur 6m Calling", 51.510, "nfm"),
            ("Amateur 2m Packet", 144.800, "nfm"),
            ("Amateur 2m Calling", 145.500, "nfm"),
            ("Amateur 70cm Calling", 433.500, "nfm"),
            # Ground-level voice: CB's emergency channel (AM, as in wichita_ground_voice).
            ("CB CH9 Emergency", 27.065, "am"),
        ]

        for name, freq_mhz, mode in required:
            key = (name, round(freq_mhz, 5))
            self.assertIn(key, lookup, f"missing band: {name} @ {freq_mhz} MHz")
            self.assertEqual(lookup[key]["demod_mode"], mode)

    def test_no_us_band_plan_frequencies(self) -> None:
        # These are US calling frequencies (and 1.25 m is not an amateur band in Europe).
        # In Malta 446.000 MHz is PMR446, not 70 cm amateur calling.
        freqs = {round(e["frequency_mhz"], 3) for e in load_scan_config()["bands"]}
        names = {e["name"] for e in load_scan_config()["bands"]}
        for us in (52.525, 146.520, 223.500):
            self.assertNotIn(us, freqs)
        self.assertNotIn("Amateur 1.25m Calling", names)
        for e in load_scan_config()["bands"]:
            if e["name"].startswith("Amateur 70cm"):
                self.assertTrue(430.0 <= e["frequency_mhz"] <= 440.0, e)

    def test_no_refused_bands(self) -> None:
        # TETRA, DECT and phones are refused by the ground-voice allowlist.
        from wichita_ground_voice import FORBIDDEN_RANGES
        for e in load_scan_config()["bands"]:
            for lo, hi, label in FORBIDDEN_RANGES:
                self.assertFalse(lo <= e["frequency_mhz"] <= hi, f"{e['name']} is in {label}")


if __name__ == "__main__":
    unittest.main()
