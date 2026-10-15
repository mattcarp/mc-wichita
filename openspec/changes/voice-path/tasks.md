# Voice path: tasks

Each task is one slice, verified with real audio. No mocks for hardware-touching code.

- [ ] 1. **Fixture.** Find or record real voice transmissions: at least one airband (AM) and one
      marine VHF (narrow FM) clip with speech. The three 2025 captures are 5 s each and may be
      carrier only; check them by ear first.
- [ ] 2. **Record contract.** One evidence record schema: clip path, sidecar, UTC observed and
      ingested times, frequency, mode, transcript, language and confidence, scores, trigger.
      Unknown fields stay explicitly unknown. Persist to disk.
- [ ] 3. **Speech finder.** Voice activity on a demodulated file: speech segments in, silence out.
      Test: the fixture yields segments; a carrier-only capture yields none.
- [ ] 4. **Transcribe by language.** Language ID, Maltese to the Vuċi model, others to large-v3.
      Test on a real Maltese clip and a real English one.
- [ ] 5. **Score.** Stress, implicit distress, keywords on each segment; optional Jev text check
      behind a flag.
- [ ] 6. **`voice_path.py`.** File in, evidence records out, stages 2 to 5 chained. Then live mode:
      SDR in, same records out, on the receiver machine.
- [ ] 7. **Review queue.** Records appear in the existing dashboard with playable audio; browser
      test, no console errors.
- [ ] 8. **SSB demodulation** for HF aviation and marine voice (needs an HF antenna).
