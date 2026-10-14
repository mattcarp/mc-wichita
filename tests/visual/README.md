# Wichita live visual suite

Runs against the live site with one shared Clerk sign-in (saved to `.auth/state.json`, reused until it expires).

```
cd tests/visual && npm i
WICHITA_EMAIL=you@example.com CHROME_PATH=/usr/bin/google-chrome npx playwright test
# while setup waits, put the emailed code (or sign-in link) in .auth/code.txt, or pass WICHITA_CODE
npx playwright test --update-snapshots   # refresh baselines after an intended design change
```

Covers: (a) baselines of the top of the page and every panel header, desktop and phone (live regions masked; full tab shots saved as artifacts), (b) identical tab-button and panel-heading styles, (c) no overlapping map labels, (d) no user name when signed out, (e) map draws in under 1 s, (f) no console errors or horizontal overflow, (g) 'More details' cue and aria-expanded on every expandable row, (h) forbidden strings (Voice Lab, Kansas, mayday, "I've been everywhere")., (i) ground voice shows only the 5 Malta channels with real state and no source URLs, (j) ground-voice API and audio proxy refuse signed-out callers.
