# Rooftop reception architecture

Site: 50 Archbishop Street, Valletta. Half-ownership of the building; the roof
itself belongs to a friend, who has agreed to an antenna on the water tank. One
unit sits below street level. Mains power exists indoors a few metres down the
leg; roof-side mains is not assumed.

Status: design record, researched 2026-09. Nothing here is installed. Figures
marked "typical" come from vendor or community sources and must be confirmed
against the actual datasheet before purchase.

## The opportunity

Valletta is a good place to listen. Line of sight to the harbour and to the sea,
roughly 15 minutes from Malta International, and dense maritime, aviation and
terrestrial traffic in every direction. A rooftop antenna on an unobstructed
plastic water tank is a materially better site than anything achievable at desk
level, including from a sub-ground-floor unit.

## Interfaces between antenna and network

Three topologies. They are not exclusive; the recommendation is to run the
conduit once with both Cat6 and a coax pull in it.

| | A. Passive coax | B. PoE receiver node | C. Masthead LNA |
| --- | --- | --- | --- |
| Roof hardware | antenna only | antenna + SDR + small host | antenna + LNA + filter |
| Roof power needed | no | no (PoE from indoors) | no (DC up the coax) |
| Cable | coax | Cat6 | coax |
| Cable loss impact | full, worst at 1090 MHz | none, the SDR is at the antenna | recovered by the LNA |
| Bands per cable | one per run, or a splitter (each leg costs ~3.5 dB) | all, limited only by the SDRs in the box | one |
| Failure surface | lowest | box, host, HAT | LNA |
| Remote retune | yes, if the SDR is on the network | yes, natively | yes |

**B is the answer to the power question.** Power over Ethernet carries power up
the same cable that carries data down, and the injector sits indoors where mains
is plentiful. A roof-side mains outlet is never required. This is the standard
pattern for roof- and mast-mounted receivers, and it is the reason the design
does not depend on the friend's electricity.

A is the honest fallback. If the box is unwanted, one coax and one SDR indoors
still works well at VHF and acceptably at 156 MHz; it degrades badly at 1090 MHz
over a long run.

C is worth knowing because it is the only way to get roof-grade performance
without any roof electronics: a masthead LNA amplifies before the loss, fed by a
bias tee indoors. In a city with strong FM broadcast it needs a band-stop filter
at the LNA, or the receiver front end will be swamped.

### Interface B, concretely

```
ROOF                                          INDOOR
antenna                                       mains
  | N-type                                    |
  |  short jumper (LMR-240 class)             PoE+ injector
  v                                             |
[ SDR ]--USB(shielded, ferrite)--[ small host ]|
                                     |          |
                                  PoE HAT       |
                                     |          |
                                     +--- Cat6 --+
                                     (power up, data down)
                                                |
                                        switch / Omarchy host
                                                |
                                          Wichita API
```

Power budget: 802.3af guarantees 12.95 W at the powered device, 802.3at ("PoE+")
25.5 W. A Pi-class host plus a USB SDR fits 802.3at comfortably and is marginal
on 802.3af. Use a PoE+ injector and check the HAT's USB current budget: the SDR
is powered from that budget.

## Cable specification

The instinct to over-specify the outdoor run is correct. Rooftop Valletta is
salt air, summer UV and heat.

- **23 AWG solid bare copper.** Copper-clad aluminium (CCA) is not compliant with
  TIA/EIA 568.2-D for category cable and has markedly higher DC resistance, which
  is exactly what PoE cannot afford.
- **Shielded** (FTP/SFTP). The PoE switching supply and the host's own clock hash
  are the two things most likely to land in the receiver's noise floor.
- **Outdoor/UV-rated jacket**, HDPE or PE, CMX or equivalent. PVC jackets go
  brittle in sun. Gel-filled if the conduit cannot be trusted to stay dry.
- **Terminate properly**: IP68 gland or a weatherproof boot at the enclosure, and
  a drip loop below the entry so water runs off rather than into the box.
- Pull a **spare pull cord** and, at the same time, a length of coax for a future
  dedicated antenna. Digging the route twice is the expensive mistake.

Coaxial loss, typical figures for LMR-400 class: on the order of 2 dB per 100 ft
at 150 MHz and 5 dB per 100 ft at 1090 MHz. At 1090 MHz the run length matters
more than the connector choice. Verify against the manufacturer datasheet before
committing a length; use LMR-600 or Heliax beyond roughly 30 m.

## Grounding and protection

Not optional, and not a DIY judgement call on a shared 600-year-old building.

- Coax shield bonded to earth at the **building entry**, not at the mast.
- A coaxial lightning arrestor at the entry, close to ground level.
- An Ethernet surge protector on the Cat6 at the entry as well.
- A ground rod near the mast where the building permits.
- Engage an installer who knows Maltese practice. The roof is not the owner's
  alone, and a lightning path into a shared structure is a liability question
  before it is an engineering one.

## Antenna choice

| Antenna | Covers | Use |
| --- | --- | --- |
| Discone (25–1300 MHz, e.g. D3000N class) | everything, low gain | first purchase; survey and discovery |
| Marine VHF vertical | 156–162 MHz | maritime voice and AIS |
| ADS-B collinear, ~8 dBi | 1090 MHz | aircraft tracking |
| Aviation VHF | 118–137 MHz | airband voice (AM) |

**Buy one discone first.** Until a single antenna has heard something, three
antennas are three unknowns. Add dedicated antennas only for bands actually being
hunted.

Mounting: clamp a short stainless mast to the tank plinth or the parapet and keep
the radiating element clear above the tank top. The plastic tank is the right
choice — it is non-conductive, so it neither detunes the antenna nor corrodes the
mount, and it is RF-transparent. It is not, however, a load-bearing mast, and an
element strapped flat against the tank wall sits in the water mass it is trying
to see past. Plastic is why this does not obstruct anyone's view; keep it that
way and the neighbourly question stays answered.

## Bands

| Service | Frequency |
| --- | --- |
| Maritime VHF CH16 | 156.800 MHz |
| Maritime VHF CH09 | 156.450 MHz |
| AIS 1 / AIS 2 | 161.975 / 162.025 MHz |
| Aviation voice AM | 118–137 MHz |
| ADS-B | 1090 MHz |
| FM broadcast (control signal) | 88–108 MHz |

## Software layers

Three layers, and only the bottom one is new work.

1. **Roof node** — SoapySDR or the native driver, plus optionally local decode.
2. **Host** — the receiver services:
   - **OpenWebRX+** (the luarvique fork of Marat Fayzullin's server): browser UI,
     multi-user by design, background and scheduled decoding, decoders for AIS,
     ADS-B, DSC, NAVTEX, ACARS, VDL2 and more, JavaScript plugins, MQTT reporting
     *and* MQTT input, HTTPS, Docker and apt packages, systemd unit `openwebrx`.
     Its MQTT surface is the clean hook into Wichita's API.
   - **ka9q-radio** — Phil Karn's multichannel daemon. Fast-convolution overlap-save
     filter bank, IP multicast I/O, no GUI. A single Pi 4 can demodulate every
     narrowband FM channel on a VHF/UHF band in real time. This is the right tool
     for "monitor every voice channel at once", which is close to Wichita's actual
     mission. Steep learning curve, generated FFTW wisdom, systemd-managed.
   - **readsb + tar1090** for ADS-B, **AIS-catcher** for AIS. tar1090 can overlay
     an AIS-catcher feed.
   - **SigMF** for capture metadata (current spec v1.2.6). IQ data plus JSON
     describing hardware, sample rate, frequency, time and author. This is the
     standard answer to the open "genuine record with provenance" milestone.
3. **Wichita** — capture pipeline, stress scoring, evidence model, dashboard.

## Host choice

The bunker is the wrong place to worry about RF and the right place to put
compute: rock is thermally stable and quiet. Condensation is the real risk, not
signal.

The Omarchy machine is a good candidate for the *analysis* host, with one caveat:
Omarchy is an opinionated Arch desktop built around Hyprland. For a service host,
run Arch headless on it and let it boot into the receiver services, not a
compositor. The roof node itself should be a cheap PoE-native single-board
computer that can be sealed in a box and replaced without ceremony.

## Web or native shell

Short answer: **web, and it already is.** A native shell earns its place only when
a named task needs it.

- The receiver/control plane is a browser problem, and OpenWebRX+ solves it today
  as a multi-user web server. Nothing is gained by wrapping a waterfall.
- The operator console in `dashboard/` plus the FastAPI server is already web.
- A desktop shell becomes justified for large local IQ file handling, multiple
  low-latency audio streams, OS notifications and tray presence, or offline
  operation at a site without a browser.

If that day comes, the shell is **Tauri 2, not Electron**: roughly 3–10 MB bundles
against 120–200 MB, on the order of 40–80 MB idle against 150–400 MB, sub-200 ms
startup, and a Rust backend — which is the same language the DSP side would
choose anyway. Electron remains the safer pick only where identical rendering
across platforms and ecosystem maturity dominate, which is not this project.

## Known pitfalls

- **SBCs are noisy.** Raspberry Pi boards radiate badly enough that they have a
  documented history of ruining SDR noise floors. Mitigate: metal enclosure,
  short shielded USB, a ferrite with the cable wound through it three or four
  turns (community reports put this in the region of 15 dB of noise floor), a
  USB isolator if a ground loop appears, and physical separation between host and
  SDR.
- **SDRplay and USB hubs.** SDRplay devices use USB isochronous transfer, and
  most machines share one controller across several ports, so typically only one
  can run per controller. Avoid hubs; if unavoidable, test it deliberately.
- **SDRplay gain.** Wrong `lna-state` and gain reduction produce a receiver that
  looks alive and hears nothing. Gain reduction below about 30 does not help and
  invites A/D overload.
- **Strong FM broadcast** in a city will overload a wideband front end. Filter it,
  and filter *before* any LNA.
- **Do not equate silence with a broken receiver.** A quiet channel is not a
  failed pipeline; that distinction is already an open finding in the evidence
  review and it survives into hardware.

## Open questions

- Written permission for the tank mount, and who owns the bonding work.
- Whether the tank plinth or the parapet is the better structural anchor.
- Which unit the cable enters; the transcript named a unit that has not been
  confirmed.
- Whether the friend's roof has any usable mains after all, which would simplify
  the roof node.
