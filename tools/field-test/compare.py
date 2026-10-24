#!/usr/bin/env python3
"""Compare two Wichita capture folders (receive-only field tests).

usage: compare.py BASELINE_DIR NEW_DIR [--out FILE]

Channel/LoRa numbers come from the folder's SUMMARY.md or BASELINE.md (written with the
same chan.py/lora.py method). If a folder has no summary but has .cs8 files, the channel
table is computed here with the baseline method (needs numpy). Sweep peaks are always
recomputed from sweep_*.csv (pure Python). Writes COMPARE.md into NEW_DIR.
"""
import csv, glob, os, re, statistics as st, sys, collections

CH_RE = re.compile(r'^(\S+)\s+([\d.]+) MHz\s+peak SNR\s+(-?[\d.]+) dB\s+median\s+(-?[\d.]+) dB\s+active\s+(\d+)%')
LORA_RE = re.compile(r'^(.+?)\s+bursts\s+(\d+)\s+time active\s+([\d.]+)%\s+peak \+?(-?[\d.]+) dB')

def summary_text(d):
    for n in ('SUMMARY.md', 'BASELINE.md'):
        p = os.path.join(d, n)
        if os.path.exists(p):
            return open(p).read(), n
    return '', None

def compute_channels(d):
    try:
        import numpy as np
    except ImportError:
        return {}
    fs = 2e6; N = 4096; out = {}
    for f in sorted(glob.glob(d + '/*.cs8')):
        m = re.search(r'_([A-Za-z0-9.]+)_(\d+)Hz(?:_ctr(\d+))?', f)
        if not m or m.group(3) is None: continue   # LORA/ISM centred exactly: centre-bin SNR meaningless
        name, fr, ctr = m.group(1), int(m.group(2)), int(m.group(3)); off = fr - ctr
        x = np.fromfile(f, dtype=np.int8, count=2 * N * 600)
        if x.size < 2 * N * 10: continue
        z = (x[0::2] + 1j * x[1::2]).astype(np.complex64)[:N * (x.size // (2 * N))].reshape(-1, N)
        p = np.abs(np.fft.fftshift(np.fft.fft(z * np.hanning(N), axis=1), axes=1)) ** 2
        fb = np.fft.fftshift(np.fft.fftfreq(N, 1 / fs))
        ch = np.abs(fb - off) < 8e3; nz = (np.abs(fb - off) > 30e3) & (np.abs(fb - off) < 150e3)
        snr = 10 * np.log10(p[:, ch].mean(1)) - 10 * np.log10(np.median(p[:, nz]))
        out[name] = dict(mhz=fr / 1e6, peak=float(snr.max()), med=float(np.median(snr)), act=float(100 * (snr > 6).mean()))
    return out

def channels(d):
    txt, src = summary_text(d)
    out = {}
    for line in txt.splitlines():
        m = CH_RE.match(line.strip())
        if m:
            out[m.group(1)] = dict(mhz=float(m.group(2)), peak=float(m.group(3)), med=float(m.group(4)), act=float(m.group(5)))
    if not out:
        out = compute_channels(d); src = 'computed from .cs8' if out else None
    return out, src

def lora(d):
    txt, _ = summary_text(d); out = {}
    for line in txt.splitlines():
        m = LORA_RE.match(line.strip())
        if m: out[m.group(1).strip()] = dict(bursts=int(m.group(2)), act=float(m.group(3)), peak=float(m.group(4)))
    return out

def sweep(f):
    acc = collections.defaultdict(list)
    for row in csv.reader(open(f)):
        try:
            lo = int(row[2]); w = float(row[4]); vals = [float(v) for v in row[6:]]
        except Exception:
            continue
        for i, v in enumerate(vals):
            acc[round((lo + w * (i + 0.5)) / 1e3)].append(v)
    if not acc: return None
    m = {k: max(v) for k, v in acc.items()}
    return dict(bins=m, floor=st.median(m.values()))

def nearest(bins, k, tol=15):
    if k in bins: return bins[k]
    best = None
    for dk in range(1, tol + 1):
        for kk in (k - dk, k + dk):
            if kk in bins: return bins[kk]
    return best

def fmt(v, nd=1, sign=False):
    if v is None: return '-'
    return ('%+.*f' if sign else '%.*f') % (nd, v)

def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if len(a) != 2: print(__doc__); sys.exit(2)
    base, new = [os.path.abspath(os.path.expanduser(x)) for x in a]
    outp = os.path.join(new, 'COMPARE.md')
    if '--out' in sys.argv: outp = sys.argv[sys.argv.index('--out') + 1]
    L = []
    L.append('# Compare: %s vs baseline %s' % (os.path.basename(new), os.path.basename(base)))
    L.append('')
    L.append('Same settings and method (2 Msps, LNA 32, VGA 20, amp off, +250 kHz offset). Positive delta = stronger / busier than the baseline.')

    bc, bsrc = channels(base); nc, nsrc = channels(new)
    L.append('')
    L.append('## Channels')
    L.append('Sources: baseline = %s, new = %s' % (bsrc or 'none', nsrc or 'none'))
    L.append('')
    L.append('| Channel | MHz | Peak SNR base | Peak SNR new | Δ peak dB | Median Δ dB | Active base | Active new | Δ active pts |')
    L.append('|---|---|---|---|---|---|---|---|---|')
    order = [k for k in bc if k in nc] + [k for k in nc if k not in bc] + [k for k in bc if k not in nc]
    moves = []
    for k in order:
        b, n = bc.get(k), nc.get(k)
        mhz = (n or b)['mhz']
        dp = (n['peak'] - b['peak']) if b and n else None
        dm = (n['med'] - b['med']) if b and n else None
        da = (n['act'] - b['act']) if b and n else None
        if dp is not None: moves.append((abs(dp), k, dp, da))
        L.append('| %s | %.4f | %s | %s | %s | %s | %s | %s | %s |' % (
            k, mhz, fmt(b and b['peak']), fmt(n and n['peak']), fmt(dp, sign=True), fmt(dm, sign=True),
            ('%d%%' % b['act']) if b else '-', ('%d%%' % n['act']) if n else 'not recorded' if b else '-',
            fmt(da, 0, sign=True)))
    if moves:
        L.append('')
        L.append('Biggest channel changes: ' + '; '.join('%s %s dB (active %s pts)' % (k, fmt(dp, sign=True), fmt(da, 0, sign=True))
                                                     for _, k, dp, da in sorted(moves, reverse=True)[:6]))

    bl, nl = lora(base), lora(new)
    if bl or nl:
        L.append('')
        L.append('## LoRa 868')
        L.append('')
        L.append('| Band | Bursts base | Bursts new | Active base | Active new | Peak base dB | Peak new dB |')
        L.append('|---|---|---|---|---|---|---|')
        for k in list(bl) + [k for k in nl if k not in bl]:
            b, n = bl.get(k), nl.get(k)
            L.append('| %s | %s | %s | %s | %s | %s | %s |' % (k, b['bursts'] if b else '-', n['bursts'] if n else '-',
                     fmt(b and b['act']), fmt(n and n['act']), fmt(b and b['peak']), fmt(n and n['peak'])))

    L.append('')
    L.append('## Sweeps')
    for f in sorted(glob.glob(base + '/sweep_*.csv')):
        name = os.path.basename(f); g = os.path.join(new, name)
        sb = sweep(f); sn = sweep(g) if os.path.exists(g) else None
        L.append('')
        if not sb or not sn:
            L.append('### %s: %s' % (name, 'missing in new run' if not sn else 'empty baseline')); continue
        L.append('### %s' % name)
        L.append('Noise floor: base %.1f dB, new %.1f dB (Δ %+.1f dB)' % (sb['floor'], sn['floor'], sn['floor'] - sb['floor']))
        L.append('')
        rel = []
        for k, v in sn['bins'].items():
            nv = v - sn['floor']; bv = nearest(sb['bins'], k)
            bvr = (bv - sb['floor']) if bv is not None else None
            rel.append((k, nv, bvr))
        topn = sorted(rel, key=lambda r: -r[1])[:8]
        L.append('| New top peaks MHz | New dB over floor | Same freq in baseline | Δ dB |')
        L.append('|---|---|---|---|')
        for k, nv, bvr in topn:
            L.append('| %.3f | +%.0f | %s | %s |' % (k / 1e3, nv, fmt(bvr, 0, sign=True), fmt(nv - bvr if bvr is not None else None, 0, sign=True)))
        appeared = sorted([r for r in rel if r[2] is not None and r[1] - r[2] >= 8 and r[1] >= 8], key=lambda r: -(r[1] - r[2]))[:8]
        gone = []
        for k, v in sb['bins'].items():
            bvr = v - sb['floor']; nv = nearest(sn['bins'], k)
            if nv is not None and bvr >= 8 and bvr - (nv - sn['floor']) >= 8:
                gone.append((k, bvr, nv - sn['floor']))
        gone = sorted(gone, key=lambda r: -(r[1] - r[2]))[:8]
        L.append('')
        L.append('Appeared (≥8 dB stronger than baseline): ' + (', '.join('%.3f MHz %+.0f' % (k / 1e3, nv - bvr) for k, nv, bvr in appeared) or 'none'))
        L.append('Faded (≥8 dB weaker than baseline): ' + (', '.join('%.3f MHz %+.0f' % (k / 1e3, nv - bvr) for k, bvr, nv in gone) or 'none'))

    txt = '\n'.join(L) + '\n'
    open(outp, 'w').write(txt)
    print(txt)

if __name__ == '__main__':
    main()
