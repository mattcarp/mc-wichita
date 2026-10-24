# Mobile-Whip HF antenna for Wichita

Status: plan only. Nothing bought, nothing on the live chain changed. Checked 24 Oct 2026.

## What it is

- **Source:** https://github.com/skuep/Mobile-Whip (author `skuep`, created 18 Nov 2025, last push 8 Jan 2026, 110 stars).
- **Licence:** CERN-OHL-P-2.0 (permissive open hardware).
- **Article:** https://www.rtl-sdr.com/mobile-whip-a-compact-battery-powered-mini-whip-style-active-hf-antenna-for-handhelds-and-sdrs/
- **What it does:** receive-only active antenna, 100 kHz to 30 MHz (the author says it also hears FM and 2 m). It's a PA0RDT Mini-Whip redesign around an LTC6268 op-amp, about 20 mA, on a 200 × 22 mm PCB.
- **Power options:**
  - one 18650 cell, with an onboard TP4054 USB-C charger;
  - a 4.0 V RTL-SDR V4 bias tee (the README says 4.0 V; the article says 4.5 V);
  - a 12-15 V Mini-Whip bias tee.
- **Output:** an edge-mount **SMA male**, so it plugs straight into an SMA female port.
- **Repo files:** KiCad project, schematic PDF, LTspice sims, and JLCPCB-ready `GERBER-mobile-whip.zip`, `BOM-mobile-whip.csv` and `CPL-mobile-whip.csv` in `kicad/mobile-whip/jlcpcb/production_files/`.

### Known issues (from the repo, issue #2)

- It's a first-revision preview, and Rev B is planned.
- Noise is higher than an original Mini-Whip, and the signal level is higher too.
  - Lowering the op-amp gain from 2 to 1 is posted in issue #2.
  - One builder reports that change gives cleaner LW/MW/SW but weaker FM.
- It sometimes self-oscillates around 250 kHz, possibly only with a bias tee or long coax.
- There's no reverse-TX protection. Wichita never transmits, so this doesn't matter here.

## Can you buy one ready-made?

**No.** No Mobile-Whip kit or assembled board turned up on Tindie (its search is behind a Cloudflare challenge, so that check isn't conclusive), AliExpress, eBay, or anything the author links to. The author links only a Ko-fi tip page. The only route is a JLCPCB assembly order.

**Nearest ready-made alternative:** the classic PA0RDT-style Mini-Whip kit on eBay, https://www.ebay.nl/itm/127923983839, from seller ok2zi_ham in Czechia.
- EUR 20.00 plus EUR 4.50 shipping to the Netherlands. Shipping to Malta wasn't shown.
- The listing shows "last one".
- It's a J310/2N5109 design that needs a **12-15 V** bias-tee injector. The RSPdx's 4.7 V bias tee can't power it, so the Mobile-Whip fits Wichita better.

## Build route: JLCPCB with assembly

Follow the steps in the repo README:
1. Upload `GERBER-mobile-whip.zip` to jlcpcb.com. Choose 1.6 mm board thickness and lead-free HASL.
2. Tick PCB Assembly. Choose Economic, Top Side, with tooling holes added by customer.
3. Upload the BOM and CPL files and make sure every listed part is ticked.
4. Ignore the warning "won't be assembled: C3, D4, C4, D6, J1, H1, H2, BT1". Those parts are not fitted, or you solder them yourself.

The minimum order is 5 boards. The author's figure is **about EUR 25 each**. That's his estimate and wasn't re-quoted today.

**Supply problem, verified 24 Oct 2026:**
- The BOM's op-amp is U1, LTC6268IS6#TRPBF (LCSC C689166). LCSC shows **0 in stock** at about $19.14 each.
- DigiKey also shows 0 in stock, with 500 expected 22 Apr 2027.
- ADI still lists the part as production with a roughly 30-week lead time. A builder said on 2 Oct 2026 that it's out of stock everywhere.
- LCSC does have the same die in the same TSOT-23-6 package:
  - C580981 LTC6268IS6#TRMPBF: 1 in stock.
  - C580980 LTC6268HS6#TRMPBF: 5 in stock. This is the -40 to 125 °C grade.
- Swapping U1's LCSC number to one of those should work. That's my reading of the part numbers; the author hasn't confirmed it.
- **Do not** use the LTC6268**-10**. The author says it's unsuitable.

### BOM (from `BOM-mobile-whip.csv`)

| Part | Ref | LCSC |
| --- | --- | --- |
| LTC6268IS6 op-amp | U1 | C689166 (out of stock, see above) |
| TP4054 Li-ion charger | U2 | C668215 |
| LP2985-3.3 LDO | U3 | C95414 |
| TLV431 (battery protection) | U4 | C56765 |
| SI2301CDS P-MOSFET | Q1, Q2 | C10487 |
| 1SMA4744A 15 V zener | D3 | C19077482 |
| B5819W Schottky | D5 | C8598 |
| Red / green side LEDs | D2 / D1 | C965874 / C965877 |
| MK-12C02 slide switch | SW1 | C136659 |
| USB-C receptacle | J2 | C2988369 |
| 470 µH 1812 inductor (FHW1812IF471KST) | L2 | C394141 |
| BLM18PG121 ferrite beads | FB1, FB2 | C14709 |
| 0R (0805) | L1 | C17477 |
| 10 µF/6V3 | C1, C2, C6, C9 | C15850 |
| 100 nF | C5, C11 | C28233 |
| 10 nF | C7, C8, C10 | C1710 |
| 1 MΩ | R1-R4 | C17514 |
| 220 kΩ | R16 | C17556 |
| 100 kΩ | R18, R19 | C149504 |
| 5.1 kΩ | R13, R14, R17, R20 | C27834 |
| 2 kΩ | R5, R6, R12 | C17604 |
| 1 kΩ | R7 | C17513 |
| 220 Ω | R10, R11 | C17557 |
| 51 Ω | R9 | C17738 |
| 1 Ω | R15 | C25271 |
| **Hand-fit:** SMA male edge mount | J1 | none |
| **Hand-fit:** 18650 holder BHC-18650-1P | BT1 | none |
| Not fitted | C3, C4, D4, D6 | none |

Also needed: one protected 18650 cell, and a short coax run.

## Connecting it to the RSPdx-R2

Ports, from the SDRplay RSPdx-R2 datasheet (https://www.sdrplay.com/wp-content/uploads/2026/06/RSPdxR2_Datasheet.pdf):

| Port | Range | Connector | Bias-T |
| --- | --- | --- | --- |
| Antenna A | 1 kHz-2 GHz | SMA female | none |
| Antenna B | 1 kHz-2 GHz | SMA female | software-selectable 4.7 V @ 100 mA (the only port with one) |
| Antenna C | 1 kHz-200 MHz | BNC female | none |

**Does 4.7 V suit it?** Yes, as far as the schematic shows.
- The bias-tee feed runs through L2, then the D5 Schottky (about 0.3 V drop), then the LP2985-3.3 LDO. The LDO is rated up to 16 V, and D3 clamps the input at 15 V.
- So 4.7 V gives about 4.4 V at the regulator, enough for a clean 3.3 V at about 20 mA.
- That sits between the 4.0 V (RTL-SDR V4) and 12-15 V inputs the author lists.
- This is my reading of the schematic, not tested.

**Recommended: battery power.** Power it from its own 18650 (USB-C to charge) and connect it to **Antenna C** with an SMA female to BNC male adapter. Antenna C is the RSPdx's HF port.
- The live AIS supervisor (`ops/live/wichita_ais_supervisor.py`) runs the RSPdx on Antenna A with `biasT_ctrl=false`. It kills AIS-catcher if Bias-T ever reads true.
- Leaving Bias-T off keeps that guard intact.
- Battery power also keeps the antenna's ground separate from the Mac's USB noise.

**Bias-T option:** Antenna B, with `biasT_ctrl=true`. The SMA male plugs straight in. Using it means changing the live guard, so it needs Mattie's okay first.

**One tuner:** the RSPdx has a single tuner. Moving it to HF means pausing AIS on it.
- That's a change to the live chain, so it needs Mattie's okay.
- **Option that leaves AIS alone:** the idle RTL-SDR Blog V4 on the Mac Mini has HF coverage and a 4.5 V bias tee. The repo README shows the Mobile-Whip plugged straight into an RTL-SDR.

**Siting:**
- A Mini-Whip works poorly underground or indoors next to electronics.
- Mount it clear above the roof, for example on the 47 Archbishop roof or the water-tank mast in `docs/ROOFTOP_ARCHITECTURE.md`.
- Feed it with coax: SMA female-to-SMA male extension, or SMA to BNC for Antenna C.
- Battery power on the roof means no DC has to go up the coax.

## HF voice targets from Valletta (verified)

| Target | Frequency, mode | Source |
| --- | --- | --- |
| Malta Radio (9HD) and international maritime distress/calling | 2182 kHz USB. Malta Radio takes medical-advice calls here and announces weather and nav warnings here first. | ITU List IV notes for Malta, updated 2 Oct 2025: https://www.itu.int/mmsapp/coastnote/download?adm=MLT&cga=MLT |
| GMDSS HF voice distress | 4125, 6215, 8291, 12290, 16420 kHz USB | ITU RR Appendix 15, via https://gmdsstesters.com/radio-survey/general/frequencies-for-the-global-maritime-distress-and-safety-system-gmdss.html |
| Shannon VOLMET (aviation weather, continuous, English) | 3413 (night), 5505, 8957, 13264 kHz USB | https://dxinfocentre.com/volmet.htm and https://www.shortwave.live/freq?band=&hour=&language=&minute=&station=Shannon+Volmet&target= |
| RAF VOLMET "Military One" (continuous) | 5450 kHz USB | https://dxinfocentre.com/volmet.htm |
| USAF HFGCS (24 h) | 8992, 11175 kHz USB | https://priyom.org/military-stations/united-states/hfgcs |

- **Not verified:** Malta Radio's own MF/HF working frequencies after the 2182 kHz announcement. They're not in the ITU notes, so they're left out.
- **Easy, unlisted:** the 40 m ham band (around 7.05-7.2 MHz LSB) always has voice. It's a good first test that the antenna works.

## Next step

Decide how to get one: order 5 assembled boards from JLCPCB with U1 swapped to C580980 or C580981, or wait for stock. Nothing has been ordered.
