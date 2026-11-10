# The measure: fun per minute

Mattie's definition of fun for an outdoor listening hour, settled 9 November 2026, and the rule
that follows from it. It applies to every future field session, not just this one.

> **Fun is usable signal × usable information, per minute out there, minus the attention it takes.**
> **Value is that rate times what the hour still leaves behind when you walk home.**

The unit is *meaningful signal received per minute*. Front-loading is the same rule applied to the
clock: the highest rate goes at the start, while the hour still has room, and the low-rate items fill
the tail or stay home.

## How the ranking is scored

Each item is scored on four things, and the fourth divides the other three:

| Term | Meaning |
|---|---|
| Signal | Does it hear anything here, on this antenna, at this spot |
| Information | Can that signal be turned into something usable: a name, a position, a voice, a timestamp |
| Attention | Hands, apps, cables, heat, or swapping an antenna mid-hour |
| What it leaves behind | Audio, NMEA, raw JSON, or nothing |

A burst you cannot decode is noise with a shape. An item that costs an antenna swap costs two items.
An item that flattens the battery at minute 40 costs the whole tail.

## The order this produced for 10 Nov

1. **AIS on the RTL-SDR** — very high signal, very high information, almost no attention. The spine.
2. **Marine voice on CH16 in SDR++** — high signal, high information, some attention. The prize.
3. **UV-K5 airband in the hand** — high signal, low information, no setup. Free while the other two run.
4. **PortaPack sweep** — high signal, low information unless decoding, high attention and heat. One
   ten-minute slot, not continuous.
5. **SMA–BNC pigtail and adapters** — no signal of their own. They unlock 1 and 2, so they rank by what
   they enable rather than by rate.
6. **Flipper on 433.92** — low signal at a quay, low information, low attention. The walk back.
7. **Mesh tracker on 869.525** — usually zero on both. Comes because it costs nothing.

## Front-loading, applied

- Minutes 5–30 are the two highest-rate items and nothing else. No device fiddling in the best light.
- Minutes 30–40 are the single high-attention item, bounded, while the recorder keeps running.
- Minutes 40–50 are the pocket toys, walked rather than sat over.
- The hour is not saved for "something better later". Anything not started by minute 40 does not run.

## Why it is written down

Because the temptation at the steps is to do the five interesting things at once, and at once is how
you get a bag of half-finished captures and no usable voice. The measure is also the tie-break for
what to buy, build, or bring next: an item that lifts information per minute without lifting attention
beats one that only lifts novelty.
