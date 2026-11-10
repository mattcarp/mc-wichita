# RF software wants — standing list

Things to add, why, and what they cost. Nothing here is installed unless the status says so.
Value order is judged by the session measure: usable signal and usable information per minute,
minus the attention it takes.

## 1. SDR# Studio (Airspy), build 1.0.0.1919 — *wanted 9 Nov 2026*
- **What:** SDRSharp. Airspy's receiver front end, RTL-SDR-USB as the source. Mattie's note:
  "it looks very well done", and what he likes is that it **chirps as it steps and looks across
  frequencies** — an audible scan, not a silent one.
- **Cost:** free download, no account. Builds at airspy.com/download (`sdrsharp-x86.zip` /
  `sdrsharp-x64.zip`; the `-next` zips are the .NET 9 previews).
- **Platform truth:** Windows only, .NET. There is no macOS build.
- **Routes on the Air, neither tested here:**
  1. Wine — `brew install --cask wine-stable`, then `winetricks dotnet48`, then run it, and
     install the RTL-SDR driver with Zadig (WinUSB) inside the prefix. Fragile: the dongle has
     to enumerate through Wine, which is the part that usually breaks.
  2. A Windows VM (UTM is free) with USB passthrough. Heavier, but the driver situation is normal
     Windows rather than emulated Windows.
  3. A Windows machine, if one ever appears. Least work of all.
- **Today's stand-in:** SDR++ already ships a **Scanner** module on the Air. It steps through a
  Frequency Manager list with a set dwell, so the signal chops in and out audibly as it goes —
  close to the thing he liked. Worth using tomorrow rather than losing the behaviour.
- **Status:** on the list, not installed.

## 2. Decoders, from the spectrum card (section E)
1. **dsd-fme** — DMR, dPMR, NXDN. The busiest closed band in a working harbour. Highest value.
2. **SatDump** — weather satellite passes. High novelty, wants a circular antenna, so it waits.
3. **multimon-ng** — POCSAG paging, and a general burst tool. Not in Homebrew core.
4. **tetra-rx** — TETRA, emergency services. Hardest to get working of the four.
5. **welle.io** or **rtl-dab** — DAB+.

## 3. Already installed for the 10 Nov run
`ais-catcher` (built from source, v0.70), `rtl_433`, `dump1090`, `SDR++`, `Gqrx`, `SDRconnect`,
`hackrf`, `librtlsdr`, `sox`, `ffmpeg`.
