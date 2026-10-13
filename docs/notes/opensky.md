# OpenSky Network and Wichita: research notes

_Written 13 Oct 2026. Covers OpenSky as an air data source, a model for a crowdsourced network, and a guide to which ground voice channels are lawful._

Source email: "14th OpenSky Symposium Call for Participation", from hello-noreply@opensky-network.org, received 13 Oct 2026 at 16:10 Malta time. It went to mattcarp1@gmail.com because the account holder already has an OpenSky account. Whether that account has a feeder registered still needs checking.

## 1. What OpenSky is
- A non-profit association based in Switzerland, running since 2013. It collects air-traffic surveillance data (ADS-B, Mode S and others) from volunteer receivers and makes it open for research. The email cites more than 7,000 sensors and more than 90,000 users. https://opensky-network.org
- **Feeder model:** anyone can run a receiver and send its raw data to OpenSky. The easy route is a Pi with an RTL-SDR, using the multi-feeder image at https://adsb.im. Sending modified or made-up data is forbidden. Feeder page: https://opensky-network.org/feed
- **What feeders get:**
  - The API allowance doubles from 4,000 to **8,000 credits a day** for each endpoint (states, flights and tracks), as long as one of your receivers has been online for more than 30% of the current month.
  - `/states/own`, the data from your own receiver, is **free and unlimited**.
  - Tiers: anonymous 400 a day, standard 4,000, active feeder 8,000, licensed 14,400 an hour. Docs: https://openskynetwork.github.io/opensky-api/rest.html
  - Login is OAuth2 client credentials only.
- **Full historical dataset (Trino):** free for research institutions, authorities and government. Non-profits are decided case by case. Private individuals and commercial users normally don't get it. https://opensky-network.org/about/faq
- **Licence terms:** https://opensky-network.org/about/terms-of-use
  - The data is for non-profit research and education only.
  - Any for-profit entity needs a written licence.
  - **Using the REST API in any live product, service or automated system needs a written licence, even for non-profits.**
  - Publications must cite the OpenSky paper.
  - The docs also warn that they may block AWS and other large cloud providers' IP addresses. Our Hetzner server could be affected, so test it.

## 2. The 14th Symposium (email and https://symposium.opensky-network.org)
- **Dates and place:** 29–30 Oct 2026 at the CRIDA campus (Kudos Innovation Campus Las Mercedes, Calle Campezo 1, Madrid), with the EUROCONTROL PRC Data Challenge.
- **Fees:** €400 in person, €200 for academics, **€30 online**.
- **Deadlines:**

  | Item | Date |
  |---|---|
  | Abstracts (1–2 pages, JOAS template, via EasyChair) | July 31, extended to **7 Aug 2026**. CLOSED. |
  | Notifications | 31 Aug |
  | Programme online | 1 Oct |
  | Full papers (14 pages) and poster short papers (4 pages, A0 printed poster) | 22 Oct, for accepted authors only |

- New this year: talks from industry and community contributors are allowed without a full paper, but they still had to meet the abstract deadline.
- **Topics:** almost entirely ADS-B trajectory and ML work, fuel and emissions, conflict resolution, ADS-B security and spoofing, and multilateration. There is **no voice or VHF audio work** in the programme. The most relevant items:
  - the poster "Operating a Volunteer OpenSky Node in Brazil… Local Regulations"
  - "Before 7700: Detecting Persistent Trajectory Precursors" (squawk 7700 is the emergency code)
  - the ADS-B spoofing and jamming intrusion-detection poster, which is relevant to spotting bad actors
- Accepted papers are published in the Journal of Open Aviation Science (JOAS), under open data and reproducibility rules.

## 3. What this means for Wichita

### 3.1 Feeding OpenSky from the RTL-SDR V4
- **Needs:**
  - a 1090 MHz antenna, ideally a 1090 MHz filter as well;
  - a decoder (readsb) running on the Mini, which can serve the V4 locally instead of through rtl_tcp;
  - the OpenSky feeder, or the adsb.im image, which can also feed adsb.lol, adsb.fi and others at the same time.
- **Gains:**
  - Our own aircraft data straight from readsb, with no licence needed because it's our receiver. This is the real source of air context on the Wichita map.
  - Free unlimited `/states/own`, plus 8,000 credits a day for research and testing.
  - Malta coverage that helps the network, and goodwill with the OpenSky community.
- **Caveat:** pulling OpenSky's *network* data (other people's receivers) into wichitawire.com as a live feature counts as "operational use" and needs a written licence. Use our own readsb output on the live site, and use the OpenSky API only for research. If Wichita becomes a company, it needs a commercial licence.
- **Effort:** an antenna (about €30–60, or the Gzira shop) plus an hour's setup. The rtl_tcp loop has to stop, because only one thing can use the dongle at a time.

### 3.2 The crowdsourced multi-receiver story for Wichita
OpenSky shows that cheap volunteer receivers can add up to research-grade infrastructure, with open data for academics and paid licences for commercial use. Comparable projects:
- AIS: AISHub (https://www.aishub.net), a data-swap co-op. You feed it and get the combined data back. AIS-catcher can already feed it.
- ACARS and VDL2 aircraft text messages: Airframes.io (https://app.airframes.io).
- Live ATC voice audio: LiveATC.net (https://www.liveatc.net). Its feeders stream audio, and the ATC audio rules vary by country.
- Public-safety scanner audio: Broadcastify (https://www.broadcastify.com), mostly in the US.
- Remote receivers: KiwiSDR (http://kiwisdr.com) and WebSDR (http://websdr.org). Shared receivers that anyone can tune.

The pitch is "OpenSky for the human voice": Wichita nodes that pair positional beacons (ADS-B, AIS) with the voice channels people use when they're in trouble.

**Legal and privacy limits. This is the hard part, and none of the above is legal advice:**
- **Malta, Security Service Act (Cap. 391), art. 15:** intentionally intercepting a communication sent by radio is an offence, punishable by up to 2 years or a €11,646.87 fine. The exceptions are a ministerial warrant, consent, or service provision. https://legislation.mt/eli/cap/391/eng/pdf
  - The Electronic Communications (Regulation) Act (Cap. 399) says explicitly that a radio authorisation does not authorise interception. https://legislation.mt/eli/cap/399/eng/pdf
  - Whether listening to open marine and air-band VHF counts as "interception" is untested. A Malta lawyer or the MCA should give an opinion before Wichita records or analyses any voice.
- **ITU Radio Regulations, Article 17 (secrecy of correspondence):** administrations must prevent unauthorised interception and disclosure of radiocommunications not meant for general reception. Marine ch16 and air-band ATC are not "public broadcasts". Distress calls are the most defensible case.
- **GDPR:** recorded voice is personal data. If it's used to identify a person, it's biometric data (Art. 9).
  - Sentiment and stress analysis needs a lawful basis, which would be vital interests or public interest for distress cases.
  - It also needs a DPIA, minimisation (analyse live, keep only flagged clips for a short time), and no public replay of identifiable voices.
- **EU AI Act:** emotion-recognition systems carry transparency duties and are classed as high-risk (Annex III). They're banned in workplaces and education (Art. 5(1)(f)). Stress detection on a pilot's or crew member's voice could count as their workplace. Check this carefully.
- **Design rule:**
  - Keep only metadata and scores by default.
  - Keep audio only around flagged events, and only for a short time.
  - Never stream voice to the public as LiveATC does.
  - Present Wichita as a tool for rescue services (RCC Malta, AFM), not public surveillance.

### 3.3 Symposium
- **Not attending the 2026 symposium** (Madrid, 29–30 Oct).
- **Low-priority option:** answer the 2027 call (abstract around early Aug 2027) with a community talk or poster, if the multi-node voice work produces something worth showing. It isn't planned.

## 4. Bringing OpenSky data into Wichita's Sky tab
API docs: https://openskynetwork.github.io/opensky-api/rest.html. It uses OAuth2 client credentials.

| Endpoint | Use for Wichita | Credit cost |
|---|---|---|
| `GET /states/all?lamin=&lomin=&lamax=&lomax=` | Live aircraft in a bounding box. A box round Malta of about lat 34–38, lon 12–16 is 16 sq°, which costs 2 credits a call. Other people's data has 5-second resolution. | 1–4 credits a call, by box size |
| `GET /states/own` | Live data from **our own** receivers only | **Free, unlimited** |
| `GET /tracks/all?icao24=&time=` | The track for one aircraft, which is experimental. Use it when someone opens an aircraft's details. | By the number of days covered |
| `GET /flights/all`, `/flights/aircraft`, `/flights/arrival` and `/flights/departure` (airport=LMML) | Flights in and out of Malta International Airport (LMML). Note that the "flights" endpoints work per airport or per aircraft. There is **no** flights-by-area endpoint; for an area, use `/states/all` with a bounding box. | By the number of days covered |

**Rate limits:** each endpoint group gets its own credits per day:

| Account | Credits |
|---|---|
| Anonymous | 400 a day |
| Signed in | 4,000 a day |
| Active feeder (receiver online more than 30% of the month) | 8,000 a day |
| Licensed | 14,400 an hour |

At 2 credits a call, a Malta box polled every 30 s uses about 5,760 credits a day. That fits the feeder tier but **not** the plain 4,000. Every 60 s uses 2,880, which fits either.

**Filling the Sky tab:**
- **Now:** OpenSky's network data from other receivers covers the Malta area wherever volunteers are within range, but Sicily and Malta coverage is patchy, so check it on https://opensky-network.org/network/explorer. It would be fine for a research or demo build. On the **live wichitawire.com it counts as "operational use"**, which needs a written licence (https://opensky-network.org/about/terms-of-use). Also, Hetzner IP addresses may be blocked, so test that first.
- **Once our RTL-SDR feeds:**
  - Take aircraft live from our own readsb `aircraft.json` on the Mini and push it to Hetzner, the same way AIS goes now. No licence is needed and the delay is about 1 second.
  - Use `/states/own` as a cross-check.
  - Ask OpenSky for a licence (or a non-profit exemption) to add `/states/all` beyond our horizon and `/flights/*` for LMML context.
- Label each source honestly on the map ("our receiver" or "OpenSky network"), which was already in the earlier proposal.

## 5. Ground (land-mobile) voice: TOP PRIORITY

### 5.1 Which channels are lawful in Malta and the EU
Throughout, "lawful" assumes open, unencrypted voice heard on general-coverage receivers. Malta's art. 15 of Cap. 391 (interception) has no general exemption for hobby listening, so treat every row as a **risk rating, not a clearance**. The table covers the 4 voice service types Mattie listed (PMR446, CB, amateur, marine VHF from shore, airband ATC) plus the other land-mobile channels.

| Service | Frequency | Nature | Receive and analyse? |
|---|---|---|---|
| **Amateur (ham)** | 144–146 MHz, 430–440 MHz, and HF | Licensed operators. Plain-language talk is required and encryption is banned by ITU RR Art. 25. Content is meant for anyone in the service. | **Lowest risk.** These are the best open voice channels. Malta's operators are licensed by the MCA, and the Malta Amateur Radio League runs repeaters. Get consent (an opt-in message on the repeaters) for voice-stress analysis under GDPR. |
| **CB** | 26.965–27.405 MHz (40 channels, FM/AM/SSB) | Open to the public, licence-exempt (ECC Decision (11)03) | **Low risk.** It's an open channel among the public, so a stronger case than "private". But it's personal data: no public replay, keep it only briefly. Little use in Malta today. |
| **PMR446** | 446.0–446.2 MHz (16 analogue + digital dPMR/DMR Tier 1) | Licence-exempt walkie-talkies (ERC Decision (98)25 / ECC) | **Medium.** It's open air, but the conversations are private (families, building sites, events). Analysis is only defensible for distress detection, keeping metadata only. Don't keep the content. |
| **Marine VHF from shore** | 156–162 MHz (Ch16 distress, Ch13, port working channels) | The Ch16 safety service is meant to be heard by everyone | **Ch16 distress: defensible.** Distress traffic is meant to be heard by all stations. Ship-to-ship and port channels are restricted by ITU RR Art. 17 secrecy. Listening isn't a licensed service; a receive-only shore station has no MCA licence for it. |
| **Airband ATC** | 118–137 MHz AM (LMML Tower 135.1, Malta Approach/Control; 121.5 emergency) | Aeronautical; LiveATC streams it in many countries | **Medium.** 121.5 MHz emergency is defensible. Routine ATC is covered by RR Art. 17. Countries differ: the UK forbids it, and many EU countries tolerate it. No clear Maltese position, so ask the MCA. Pilot stress analysis touches the AI Act "workplace" rule. |
| **TETRA (emergency services)** | 380–400 MHz | Encrypted. Malta's network has been TETRA for the Civil Protection Department since 2001 (https://en.wikipedia.org/wiki/TETRA) | **OFF-LIMITS.** Decrypting or listening is interception under Cap. 391 art. 15. Don't even try to decode it. |
| **Business PMR / DMR, taxis, security firms, ports, utilities** | Various VHF/UHF | Licensed private systems | **Off-limits** for content: private correspondence under RR Art. 17 and Cap. 391. Metadata such as "activity on frequency" could be OK. |
| Mobile phones, DECT, anything else | — | Private and encrypted | **Off-limits.** |

**Rule for analysing any voice:**
- Analyse on the device or in real time.
- Keep **scores and metadata, not audio**, by default.
- Keep a clip only when a distress score passes a threshold, keep it for 72 hours or less, and send it only to a rescue service (RCC Malta / AFM, CPD 112).
- Do a DPIA, and stay away from identifying people by voice.
- Before going live, ask the MCA (https://www.mca.org.mt) and a Malta data-protection lawyer (the regulator is the IDPC, https://idpc.org.mt) for an opinion.

### 5.2 Hardware fit
- The SDRplay RSPdx-R2 covers all of the above. It's currently busy with AIS on 162 MHz.
- With 2 MHz or so of bandwidth, it can only watch one band at a time. A second SDR (an RTL-SDR at about €35) on 144–146 or 156–162 MHz, running the open-source rtl_airband or a voice-activity detector, would let one node watch several channels.
- Candidate first channels in Malta:
  - marine Ch16 (156.800)
  - the 2 m amateur calling frequency (145.500) and local repeaters
  - 121.5 MHz
  - PMR446 ch1–8
  - CB ch9 (27.065, the emergency channel)

### 5.3 A multi-receiver network for ground voice, modelled on OpenSky
- **Node:** a Pi plus SDR plus a Wichita agent. It does voice-activity detection and sentiment/stress analysis **on the device**, and sends only events upstream: time, frequency, signal strength, scores, a rough position from the node, and optionally a short encrypted clip for distress events.
  - This is the opposite of LiveATC and Broadcastify, which stream raw audio. Keeping voice on the device is both the privacy design and the legal defence.
- **Several nodes hearing the same voice:**
  - Signal strength and time differences across nodes (as in OpenSky's multilateration session) could roughly locate the source. That supports both "where is the person in trouble" and spotting bad actors, such as fake Mayday calls or jamming.
  - It's realistic for FM voice with GPS-timed nodes. It's a research problem, so it suits a symposium.
- **Matching with beacons:** link a Ch16 voice event to nearby AIS ships, and a 121.5 event to ADS-B aircraft squawking 7700 nearby. That's where OpenSky and AISHub data add value.
- **Running the network:** volunteers feed, and in return they get access to their own node's events plus the combined dashboard. Research access would be free and operational or commercial use licensed, which is OpenSky's own model. Licensed radio amateurs and their club, the Malta Amateur Radio League, are the most natural early adopters.
- **Existing projects to learn from:**
  - KiwiSDR/WebSDR: shared receivers.
  - rtl_airband plus LiveATC: multi-channel AM/FM receivers.
  - Broadcastify Calls: trunked voice per call. Its approach to the law is US-specific and not portable to the EU.

### 5.4 Ground-voice recommendations
1. **Start with ham 2 m/70 cm, CB ch9 and marine Ch16 from the balcony,** with a second €35 SDR. Run voice-activity detection plus on-device scoring, keep metadata only, and don't keep audio.
2. **Ask the MCA and the IDPC in writing** for an opinion on receiving and analysing these channels. Never touch TETRA or private PMR/DMR content.
3. **Design the node and event schema now,** with no raw audio leaving the node and GPS time-stamping for future location-finding. Recruit 2–3 Maltese radio amateurs as nodes 2–4, for example in Gozo and Dingli.

## Top recommendations (overall)
1. **Ground voice first (see 5.4).**
   - Listen on amateur 2 m/70 cm, CB ch9 and marine Ch16 from the balcony with a second SDR.
   - Score speech on the device, keep metadata only, and keep no audio by default.
   - Get MCA, IDPC and lawyer opinions in writing before going live.
2. **Feed OpenSky from the RTL-SDR.** Fit a 1090 antenna and run readsb plus the feeder. Show our own readsb data on the live site, which needs no licence. OpenSky network data needs the written licence below.
3. **Apply for the OpenSky operational licence** to add coverage beyond our horizon and LMML flight context.

## OpenSky licence for operational display: process
- **Who:** email **contact@opensky-network.org**. The terms of use say: "To obtain a license, contact contact[at]opensky-network.org." https://opensky-network.org/about/terms-of-use
- **Form:** there is no public licence form. The only form is the **My OpenSky → "Request Data Access"** application (after registering and verifying your email), and that's for research and full-data (Trino) access, not a commercial licence. https://openskynetwork.github.io/opensky-api/trino.html
- **What they ask for:**
  - FAQ: "a brief description of how you will use the data and what data you need"
  - Use an institutional email address if you have one.
  - They may refuse access they consider unethical.

  https://opensky-network.org/about/faq
- **What's covered:** any operational use (a live product, service or automated system) needs a written licence, "regardless of the entity's non-profit status". Government bodies can get an exemption at OpenSky's discretion.
- **Cost:** **no price is published**, so it's negotiated case by case. The only fee mentioned anywhere is a possible "extraction fee" for bulk historical downloads (Trino docs).
- **Notes:**
  - OpenSky says it gets too many requests to answer personal ones, and the API docs say "Do not contact us because you want your AI dashboard whitelisted". So the email has to be a real, specific, mission-led request: rescue-services context, a Malta-area bounding box, polling rate, data shown, attribution, and that we feed our own receiver.
  - Registering more than one account gets every account banned for life, so use one account only.
  - The licence is governed by Swiss law. OpenSky is a Swiss association based in Burgdorf.

## To-do
- [ ] Get the **written OpenSky licence** for operational display of network data on wichitawire.com. Email contact@opensky-network.org using the process above. Draft it and have it approved before sending.
- [ ] Fit a **1090 MHz antenna** to the RTL-SDR V4 and set up **readsb plus the OpenSky feeder** on the Mac Mini, replacing the rtl_tcp loop.
- [ ] **Register one OpenSky account and the feeder** (check the existing account first) and confirm the 8,000-credit active-feeder tier through `X-Rate-Limit-Remaining`.
- [ ] **Test OpenSky API access from Hetzner.** OpenSky may block cloud provider IP addresses. Test with OAuth2 client credentials on `/states/own` and a Malta-box `/states/all`.
- [ ] Buy a **second RTL-SDR** (about €35) plus an antenna for ground voice: 2 m/70 cm, CB 27 MHz and marine VHF.
- [ ] Get **written opinions** from the MCA, the IDPC and a Maltese lawyer on receiving and analysing amateur, CB, PMR446, marine Ch16, 121.5 MHz and ATC channels, covering Cap. 391 art. 15, GDPR and the AI Act.
- [ ] **Check the frequencies and rules not yet confirmed against a source:**
  - the LMML tower and approach frequencies (135.1 etc., against Malta's official aeronautical publication, the AIP)
  - the exact CB range and the ch9 emergency use in Malta
  - the PMR446 range and its digital channels
  - the decision numbers ECC (11)03 and ERC (98)25
  - the Malta TETRA operator and its current status
