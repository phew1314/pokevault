"""POKÉVAULT draw SFX — synthesized, frame-synced to the Blender clips (24 fps)."""
import numpy as np, os, subprocess
from scipy import signal

SR = 44100
OUT = '/home/claude/blend/audio/out/'
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(7)

def T(sec): return int(sec * SR)
def F(frame): return (frame - 1) / 24.0
def noise(n): return rng.standard_normal(n)
def bp(x, lo, hi, order=2): b, a = signal.butter(order, [lo, hi], 'band', fs=SR); return signal.lfilter(b, a, x)
def lp(x, hi, order=2): b, a = signal.butter(order, hi, 'low', fs=SR); return signal.lfilter(b, a, x)
def hp(x, lo, order=2): b, a = signal.butter(order, lo, 'high', fs=SR); return signal.lfilter(b, a, x)
def env_ad(n, a, d=None):
    t = np.arange(n) / SR; d = d if d is not None else (n / SR - a)
    e = np.where(t < a, t / max(a, 1e-4), np.exp(-(t - a) / max(d, 1e-4) * 4)); return e
def bell(n):  # 0..1..0 smooth
    return np.sin(np.linspace(0, np.pi, n)) ** 2

def track(sec): return np.zeros((T(sec), 2))
def place(tr, sig, t, gain=1.0, pan=0.0):
    i = T(t); sig = sig * gain
    if sig.ndim == 1:
        l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        sig = np.stack([sig * l * 1.41, sig * r * 1.41], 1)
    j = min(len(tr), i + len(sig))
    if j > i: tr[i:j] += sig[:j - i]

def reverb(x, sec=1.6, mix=0.25, damp=5000):
    n = T(sec); ir = np.stack([noise(n), noise(n)], 1) * np.exp(-np.arange(n) / SR * 6.5 / sec)[:, None]
    ir[:, 0] = lp(ir[:, 0], damp); ir[:, 1] = lp(ir[:, 1], damp); ir /= np.sqrt((ir ** 2).sum(0))
    wet = np.stack([signal.fftconvolve(x[:, c], ir[:, c])[:len(x)] for c in range(2)], 1)
    return x * (1 - mix) + wet * mix * 1.4

# ---------------------------------------------------------------- sound atoms
def room(sec): return lp(noise(T(sec)), 400) * 0.012

def crinkle(sec, density=900):
    n = T(sec); x = np.zeros(n)
    k = int(density * sec); pos = rng.integers(0, n - 400, k)
    for p in pos:
        L = rng.integers(40, 300); x[p:p + L] += noise(L) * np.exp(-np.arange(L) / (L / 4)) * rng.uniform(0.2, 1)
    return bp(x, 1800, 9000) * bell(n) * 0.25

def tear(sec=0.42):
    n = T(sec); t = np.arange(n) / SR
    am = np.abs(lp(noise(n), 90)) * 6 + 0.2                       # ragged fibre tearing
    grains = (rng.random(n) < 0.02) * rng.uniform(0.5, 1.5, n)
    x = bp(noise(n) * am + bp(grains, 2000, 8000) * 3, 700, 7000)
    e = np.clip(t / 0.03, 0, 1) * np.where(t > sec - 0.06, np.clip((sec - t) / 0.06, 0, 1), 1) * (0.6 + 0.6 * t / sec)
    body = bp(noise(n), 200, 800) * e * 0.4
    return (x * e + body) * 0.35

def slide(sec, bright=6000):
    n = T(sec); am = 0.6 + 0.4 * np.abs(lp(noise(n), 18)) * 3
    return bp(noise(n), 900, bright) * am * bell(n) * 0.05

def tap(gain=1.0):
    n = T(0.18); t = np.arange(n) / SR
    thump = np.sin(2 * np.pi * (140 - 60 * t / 0.18) * t) * np.exp(-t * 38)
    click = bp(noise(n), 1500, 6000) * np.exp(-t * 160)
    return (thump * 0.6 + click * 0.35) * gain

def tick(): n = T(0.03); return bp(noise(n), 3000, 9000) * np.exp(-np.arange(n) / SR * 250) * 0.15

def shimmer(sec, count=24, lo=2200, hi=7000, decay=0.6):
    n = T(sec); x = np.zeros((n, 2))
    for i in range(count):
        f = rng.uniform(lo, hi); st = rng.integers(0, max(1, n - T(decay))); L = min(T(decay * 1.5), n - st)
        t = np.arange(L) / SR
        s = (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * f * 2.0 * t)) * np.exp(-t / decay * 4) * np.clip(t / 0.004, 0, 1)
        p = rng.uniform(-0.9, 0.9)
        x[st:st + L, 0] += s * (1 - p) / 2; x[st:st + L, 1] += s * (1 + p) / 2
    return x * 0.06

def riser(sec, f0=70, f1=320):
    n = T(sec); t = np.arange(n) / SR; k = t / sec
    f = f0 * (f1 / f0) ** k; ph = 2 * np.pi * np.cumsum(f) / SR
    tone = (np.sin(ph) + 0.5 * np.sin(2 * ph + 0.3) + 0.25 * np.sin(3.01 * ph)) * (0.3 + 0.7 * k ** 2)
    trem = 1 - 0.35 * (0.5 + 0.5 * np.sin(2 * np.pi * (2 + 14 * k ** 2) * t))
    nz = np.zeros(n); seg = 2048
    for i in range(0, n, seg):   # sweeping noise band
        c = 300 + 6000 * k[i] ** 2
        nz[i:i + seg] = bp(noise(min(seg, n - i) + 512), c * 0.6, min(c * 1.6, 18000))[512:] if min(seg, n - i) > 0 else 0
    return (tone * trem * 0.14 + nz * k ** 2 * 0.12) * np.clip(t / 0.3, 0, 1)

def boom(sec=3.0):
    n = T(sec); t = np.arange(n) / SR
    sub = np.sin(2 * np.pi * np.cumsum(40 + 50 * np.exp(-t * 6)) / SR) * np.exp(-t * 1.6)
    crack = lp(noise(n), 2500) * np.exp(-t * 14)
    air = bp(noise(n), 3000, 12000) * np.exp(-t * 3) * 0.3
    return (sub * 0.8 + crack * 0.5 + air * 0.25) * 0.8

def pad(sec, freqs, gain=0.05):
    n = T(sec); t = np.arange(n) / SR; x = np.zeros((n, 2))
    for i, f in enumerate(freqs):
        for d, c in ((-0.25, 0), (0.25, 1)):
            x[:, c] += np.sin(2 * np.pi * (f * (1 + d / 100)) * t + i)
    e = np.clip(t / 0.4, 0, 1) * np.clip((sec - t) / 1.2, 0, 1)
    return x * e[:, None] * gain / len(freqs)

def whoosh(sec, lo=300, hi=3000):
    n = T(sec); x = np.zeros(n); seg = 1024
    for i in range(0, n, seg):
        k = i / n; c = lo + (hi - lo) * np.sin(np.pi * k)
        L = min(seg, n - i); x[i:i + L] = bp(noise(L + 512), c * 0.7, c * 1.4)[512:]
    return x * bell(n) * 0.35

def hum(sec):
    n = T(sec); t = np.arange(n) / SR
    saw = signal.sawtooth(2 * np.pi * 120 * t) * 0.5 + signal.sawtooth(2 * np.pi * 60 * t) * 0.3
    return lp(saw, 1800) * 0.05 + bp(noise(n), 4000, 9000) * 0.008

def relay():
    n = T(0.06); t = np.arange(n) / SR
    return (hp(noise(n), 1500) * np.exp(-t * 220) * 0.4 + np.sin(2 * np.pi * 90 * t) * np.exp(-t * 60) * 0.3)

def bellnote(f, sec=1.2, gain=0.15):
    n = T(sec); t = np.arange(n) / SR
    s = sum(a * np.sin(2 * np.pi * f * m * t) * np.exp(-t * (3 + m)) for m, a in ((1, 1), (2.0, 0.4), (3.01, 0.2), (4.2, 0.1)))
    return s * np.clip(t / 0.003, 0, 1) * gain

def brass(freqs, sec, gain=0.08):
    n = T(sec); t = np.arange(n) / SR; x = np.zeros(n)
    for f in freqs:
        for d in (-0.15, 0.15):
            x += signal.sawtooth(2 * np.pi * f * (1 + d / 100) * t + rng.uniform(0, 6))
    cut = 600 + 3200 * np.clip(t / 0.12, 0, 1) * np.exp(-t * 0.6)
    y = np.zeros(n); seg = 512
    for i in range(0, n, seg):
        L = min(seg, n - i); y[i:i + L] = lp(x[max(0, i - 1024):i + L], cut[i])[-L:]
    e = np.clip(t / 0.05, 0, 1) * np.clip((sec - t) / 0.4, 0, 1)
    return y * e * gain / len(freqs)

# ---------------------------------------------------------------- mixing / export
def finish(tr, name, rev=0.22, sec=None):
    tr = reverb(tr, mix=rev)
    peak = np.abs(tr).max(); tr = tr / max(peak, 1e-6) * 0.89
    raw = OUT + name + '.f32'
    tr.astype('<f4').tofile(raw)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', raw,
                    '-c:a', 'libmp3lame', '-b:a', '128k', OUT + name + '.mp3'], check=True)
    os.remove(raw); print(name, round(len(tr) / SR, 2), 's')

def intro_base(tr, big=False):
    place(tr, room(len(tr) / SR), 0, 1.0)
    place(tr, shimmer(1.2, count=8, decay=0.9), F(12), 0.6)           # light sweep glint on the foil
    place(tr, crinkle(0.45, 500), F(33), 1.0, -0.2)                   # fingers on the paper / peel starts
    place(tr, tear(0.42), F(40), 1.0, 0.25)                           # the rip
    for k in range(5): place(tr, tick(), F(50 + k * 3 + rng.integers(0, 3)), rng.uniform(0.5, 1.0), rng.uniform(-0.6, 0.6))
    place(tr, slide(F(87) - F(52)), F(52), 1.0, 0.0)                  # card sliding out of the envelope
    place(tr, slide(F(97) - F(70), 3500), F(70), 0.6, -0.3)           # envelope pulled away
    place(tr, tap(0.9), F(88), 1.0)                                   # card lands on the felt

def make_intro():
    tr = track(F(108) + 1.2); intro_base(tr); finish(tr, 'sfx_intro')

def make_bigA():
    tr = track(F(124) + 3.0); intro_base(tr, True)
    place(tr, crinkle(F(80) - F(44), 1400), F(44), 0.9, 0.1)          # envelope rattling
    place(tr, riser(F(88) - F(42)), F(42), 1.0)
    place(tr, shimmer(F(100) - F(44), count=70, decay=0.5), F(44), 1.0)
    place(tr, pad(F(124) - F(60) + 2.5, [261.6, 329.6, 392.0, 493.9, 587.3], 0.10), F(60), 1.0)
    place(tr, boom(3.0), F(88), 1.0)
    place(tr, shimmer(2.5, count=40, lo=1500, hi=6000, decay=1.0), F(88), 1.2)
    finish(tr, 'sfx_bigA', rev=0.3)

def make_rev():
    tr = track(F(112) + 3.0)
    place(tr, boom(1.2) * 0.5, 0, 0.6)                                # power cut thunk
    place(tr, lp(noise(T(F(46))), 120) * 0.05, 0, 1.0)                # dark drone
    on = {9: .5, 10: 0, 12: .8, 13: .1, 15: 1, 16: 0, 19: .6, 20: 0, 24: .3, 26: 0, 29: .9, 30: .05, 33: .4, 34: 0}
    prev = 0
    for f in sorted(on):
        lvl = on[f]
        if (lvl > 0.2) != (prev > 0.2): place(tr, relay(), F(f), 0.9, rng.uniform(-0.3, 0.3))
        if lvl > 0.05: place(tr, hum(1 / 24 * 2), F(f), lvl * 1.2)
        prev = lvl
    place(tr, riser(F(88) - F(44), 55, 280), F(44), 1.1)
    place(tr, pad(F(112) - F(46) + 2.5, [220.0, 277.2, 329.6, 415.3], 0.08), F(46), 1.0)
    # card spinning down: whooshes slowing as it lands
    t = F(50)
    for i in range(7):
        d = 0.16 + i * 0.05
        place(tr, whoosh(d, 400, 2500 - i * 200), t, 0.5 + 0.08 * i, 0.4 if i % 2 else -0.4); t += d * 0.8
    place(tr, boom(3.0), F(88), 1.0)
    place(tr, tap(1.0), F(88), 0.8)
    place(tr, shimmer(2.5, count=45, lo=1500, hi=6500, decay=1.0), F(88), 1.2)
    finish(tr, 'sfx_rev', rev=0.3)

# ---------------------------------------------------------------- site-side stingers
def make_flip():
    tr = track(0.7); place(tr, whoosh(0.35, 500, 3500), 0, 1.0); place(tr, tap(0.5), 0.3, 0.6); finish(tr, 'sfx_flip', 0.12)

def make_reveal_normal():
    tr = track(1.8)
    for i, f in enumerate([659.3, 987.8]): place(tr, bellnote(f, 1.4, 0.18), i * 0.09, 1.0, -0.2 + 0.4 * i)
    finish(tr, 'sfx_reveal', 0.3)

def make_reveal_rare():
    tr = track(2.4)
    for i, f in enumerate([523.3, 659.3, 784.0, 1046.5, 1318.5]): place(tr, bellnote(f, 1.6, 0.16), i * 0.07, 1.0, -0.5 + 0.25 * i)
    place(tr, shimmer(1.5, count=20, decay=0.8), 0.3, 1.0)
    finish(tr, 'sfx_reveal_rare', 0.35)

def make_reveal_big():
    tr = track(4.5)
    place(tr, boom(2.5), 0, 0.7)
    place(tr, brass([261.6, 329.6, 392.0], 0.35, 0.16), 0.05)
    place(tr, brass([293.7, 370.0, 440.0], 0.35, 0.16), 0.42)
    place(tr, brass([329.6, 415.3, 493.9, 659.3], 2.6, 0.2), 0.8)
    for i, f in enumerate([1318.5, 1568.0, 1975.5, 2637.0]): place(tr, bellnote(f, 2.0, 0.1), 0.8 + i * 0.06, 1.0, -0.5 + 0.33 * i)
    place(tr, shimmer(3.0, count=60, decay=1.1), 0.8, 1.3)
    finish(tr, 'sfx_reveal_big', 0.35)

def make_glitch():
    n = T(1.2); t = np.arange(n) / SR
    x = signal.sawtooth(2 * np.pi * (220 * np.exp(-t * 1.5)) * t) * 0.3 + bp(noise(n), 500, 6000) * 0.5
    gate = (np.sin(2 * np.pi * (8 + 30 * t) * t) > 0).astype(float)
    x = np.round(x * gate * 6) / 6                                   # crushed
    x *= np.clip((1.2 - t) / 0.2, 0, 1) * np.clip(t / 0.02, 0, 1)
    tr = track(1.6); place(tr, x * 0.5, 0); place(tr, boom(1.0) * 0.4, 0.85); finish(tr, 'sfx_glitch', 0.15)


# ================================================================ HYPE MUSIC LAYER (original, GB-chiptune + orchestral)
import chip as C
BEAT = F(88) / 9.0          # 149 BPM: tear lands on beat 4, card lands on beat 9
def B(b): return b * BEAT

def groove(tr, b0, b1, root=45, lead=True, vol=1.0):
    """driving chiptune groove: kick/hat, 8th-note wave bass, short pulse stabs"""
    b = b0
    while b < b1:
        C.place(tr, C.nz_drum('k', 0.9), B(b), 0.55 * vol)
        C.place(tr, C.nz_drum('h', 0.8), B(b + 0.5), 0.5 * vol, 0.3)
        if int(b) % 2 == 1: C.place(tr, C.nz_drum('s', 0.7), B(b), 0.35 * vol, -0.1)
        for h in (0, 0.5):
            C.place(tr, C.wave_bass(C.hz(root if h == 0 else root + 12), BEAT * 0.45), B(b + h), 0.16 * vol)
        b += 1
    if lead:
        for i, (bb, m) in enumerate([(b0, 69), (b0 + 0.75, 72), (b0 + 1.5, 76), (b0 + 2.5, 75), (b0 + 3, 76)]):
            if bb < b1: C.place(tr, C.pulse(C.hz(m), BEAT * 0.4, 0.25), B(bb), 0.07 * vol, 0.2)

def build(tr, b0, b1, chords, vol=1.0, rate=22):
    """accelerating snare roll + rising arps through a chord sequence + string riser"""
    dur = B(b1) - B(b0)
    C.place(tr, C.drumroll(dur, 149, 4, 32), B(b0), 0.6 * vol)
    seg = dur / len(chords)
    for i, ch in enumerate(chords):
        C.place(tr, C.arp_run(ch, seg, rate + i * 4, 2, 0.125 if i % 2 else 0.25), B(b0) + i * seg, (0.05 + 0.025 * i) * vol, 0.25 if i % 2 else -0.25)
        C.place(tr, C.saw_stack([C.hz(m - 12) for m in ch[:3]], seg + 0.05, 1.0, 0.05, 1500 + 800 * i), B(b0) + i * seg, (0.18 + 0.06 * i) * vol)
        C.place(tr, C.wave_bass(C.hz(ch[0] - 24), seg), B(b0) + i * seg, 0.2 * vol)

def hero_lead(tr, b0, bars_beats, vol=1.0):
    """original heroic chiptune lead + harmony over driving drums"""
    mel = [(0, 69, 0.5), (0.5, 73, 0.5), (1, 76, 1), (2, 81, 0.75), (2.75, 80, 0.25), (3, 78, 0.5), (3.5, 76, 0.5),
           (4, 78, 1.5), (5.5, 81, 0.5), (6, 85, 2)]
    for bb, m, d in mel:
        if bb >= bars_beats: break
        C.place(tr, C.pulse(C.hz(m), BEAT * d * 0.95, 0.5, 1.0, vib=0.006), B(b0 + bb), 0.075 * vol, 0.15)
        C.place(tr, C.pulse(C.hz(m - 4 if m % 2 else m - 3), BEAT * d * 0.95, 0.125, 1.0), B(b0 + bb), 0.04 * vol, -0.3)
    b = 0
    roots = [45, 45, 50, 50, 52, 52, 45, 45]
    while b < bars_beats:
        C.place(tr, C.nz_drum('k'), B(b0 + b), 0.5 * vol)
        C.place(tr, C.nz_drum('s'), B(b0 + b + 0.5), 0.3 * vol)
        C.place(tr, C.nz_drum('h'), B(b0 + b + 0.25), 0.35 * vol, 0.3); C.place(tr, C.nz_drum('h'), B(b0 + b + 0.75), 0.35 * vol, 0.3)
        r = roots[int(b) % len(roots)]
        for h in (0, 0.5): C.place(tr, C.wave_bass(C.hz(r + (12 if h else 0)), BEAT * 0.45), B(b0 + b + h), 0.17 * vol)
        b += 1

AM, F_, G_, E_ = [57, 60, 64], [53, 57, 60], [55, 59, 62], [52, 56, 59]
A_MAJ = [57, 61, 64, 69]

def music_intro(tr):
    groove(tr, 0, 4)
    C.place(tr, C.stab([57, 60, 64, 69], 0.8), B(4), 0.5)                        # the tear
    build(tr, 4, 9, [F_, G_, [57, 60, 64], E_])
    C.place(tr, C.stab([57, 61, 64, 69, 73], 1.0, 0.7), B(9), 0.75)              # card lands — bright A major
    C.place(tr, C.saw_stack([C.hz(m) for m in [57, 62, 64, 69]], 1.6, 1.0, 0.2, 2500), B(9) + 0.3, 0.16)  # sus4: hang for the flip

def music_bigA(tr):
    groove(tr, 0, 4)
    C.place(tr, C.stab([57, 60, 64, 69], 0.9), B(4), 0.55)
    build(tr, 4, 9, [F_, G_, [59, 62, 66], [61, 64, 68]], vol=1.25, rate=26)   # keeps climbing
    C.place(tr, C.stab([57, 61, 64, 69, 73], 1.0, 0.9), B(9), 0.95)
    hero_lead(tr, 9.5, 6.5, 1.1)
    C.place(tr, C.saw_stack([C.hz(m) for m in [57, 64, 69, 73]], 1.8, 1.0, 0.3, 3000), F(124) - 0.4, 0.18)

def music_rev(tr):
    C.heartbeat(F(12), tr, beats=4, bpm=95, vol=0.9)                             # in the dark
    b0 = F(45) / BEAT
    build(tr, b0, 9, [[50, 53, 57], [52, 55, 59], [53, 57, 60], [56, 59, 63]], vol=1.3, rate=28)
    C.place(tr, C.stab([57, 61, 64, 69, 73], 1.1, 0.9), B(9), 1.0)
    hero_lead(tr, 9.5, 5, 1.1)

def add_music(tr, fn, gain):
    m = np.zeros_like(tr); fn(m)
    m = m / max(np.abs(m).max(), 1e-6)
    tr += m * gain

# rebuild clip tracks with music under the SFX
_old_intro, _old_bigA, _old_rev = make_intro, make_bigA, make_rev
def make_intro():
    tr = track(F(108) + 1.8); intro_base(tr); add_music(tr, music_intro, 0.75); finish(tr, 'sfx_intro', rev=0.18)
def make_bigA():
    tr = track(F(124) + 3.0); intro_base(tr, True)
    place(tr, crinkle(F(80) - F(44), 1400), F(44), 0.9, 0.1)
    place(tr, riser(F(88) - F(42)), F(42), 0.8)
    place(tr, shimmer(F(100) - F(44), count=70, decay=0.5), F(44), 1.0)
    place(tr, boom(3.0), F(88), 1.0)
    place(tr, shimmer(2.5, count=40, lo=1500, hi=6000, decay=1.0), F(88), 1.2)
    add_music(tr, music_bigA, 0.8); finish(tr, 'sfx_bigA', rev=0.22)
def make_rev():
    tr = track(F(112) + 3.0)
    place(tr, boom(1.2) * 0.5, 0, 0.6)
    place(tr, lp(noise(T(F(46))), 120) * 0.05, 0, 1.0)
    on = {9: .5, 10: 0, 12: .8, 13: .1, 15: 1, 16: 0, 19: .6, 20: 0, 24: .3, 26: 0, 29: .9, 30: .05, 33: .4, 34: 0}
    prev = 0
    for f in sorted(on):
        lvl = on[f]
        if (lvl > 0.2) != (prev > 0.2): place(tr, relay(), F(f), 0.9, rng.uniform(-0.3, 0.3))
        if lvl > 0.05: place(tr, hum(1 / 24 * 2), F(f), lvl * 1.2)
        prev = lvl
    place(tr, riser(F(88) - F(44), 55, 280), F(44), 0.9)
    t = F(50)
    for i in range(7):
        d = 0.16 + i * 0.05
        place(tr, whoosh(d, 400, 2500 - i * 200), t, 0.5 + 0.08 * i, 0.4 if i % 2 else -0.4); t += d * 0.8
    place(tr, boom(3.0), F(88), 1.0); place(tr, tap(1.0), F(88), 0.8)
    place(tr, shimmer(2.5, count=45, lo=1500, hi=6500, decay=1.0), F(88), 1.2)
    add_music(tr, music_rev, 0.85); finish(tr, 'sfx_rev', rev=0.22)

def make_reveal_normal():
    tr = track(1.6)   # short original "you got it!" chiptune jingle
    for i, (dt, m, d) in enumerate([(0, 76, .09), (.09, 79, .09), (.18, 83, .09), (.27, 88, .5)]):
        C.place(tr, C.pulse(C.hz(m), d, 0.5, 1.0, decay=2), dt, 0.18, 0.1)
        C.place(tr, C.pulse(C.hz(m - 7), d, 0.25, 1.0, decay=2), dt, 0.09, -0.2)
    C.place(tr, C.wave_bass(C.hz(52), 0.5), 0.27, 0.25)
    place(tr, shimmer(1.0, count=10, decay=0.6), 0.27, 0.8)
    finish(tr, 'sfx_reveal', 0.2)

def make_reveal_rare():
    tr = track(2.6)
    seq = [(0, 72), (.08, 76), (.16, 79), (.24, 84), (.36, 83), (.44, 84), (.52, 88)]
    for dt, m in seq: C.place(tr, C.pulse(C.hz(m), .11 if m != 88 else .8, 0.5, 1.0, vib=.006), dt, 0.16, 0.1)
    C.place(tr, C.stab([60, 64, 67, 72], 0.8, 0.6), 0.52, 0.5)
    C.place(tr, C.arp_run([72, 76, 79], 0.9, 28, 2, 0.125), 0.6, 0.06, -0.3)
    place(tr, shimmer(1.8, count=25, decay=0.8), 0.5, 1.0)
    finish(tr, 'sfx_reveal_rare', 0.25)

def make_reveal_big():
    tr = track(5.0)
    C.place(tr, C.stab([57, 61, 64, 69, 73], 1.0, 0.5), 0, 0.8)
    place(tr, boom(2.5), 0, 0.6)
    fan = [(0.5, 69, .18), (0.68, 69, .18), (0.86, 69, .18), (1.04, 69, .5), (1.54, 65, .5), (2.04, 67, .5), (2.54, 69, .3), (2.9, 67, .15), (3.05, 69, 1.4)]
    for dt, m, d in fan:
        C.place(tr, C.saw_stack([C.hz(m), C.hz(m + 4 if m != 65 else m + 4), C.hz(m + 7)], d, 1.0, 0.01, 4200), dt, 0.55, 0.0)
        C.place(tr, C.pulse(C.hz(m + 12), d * 0.95, 0.5, 1.0, vib=0.007), dt, 0.06, 0.2)
    for dt in (0.5, 1.04, 1.54, 2.04, 2.54, 3.05):
        C.place(tr, C.timpani(55, 0.8), dt, 0.5)
    C.place(tr, C.stab([57, 61, 64, 69, 73, 76], 1.0, 1.3), 3.05, 0.7)
    C.place(tr, C.arp_run([69, 73, 76], 1.3, 30, 2, 0.125), 3.1, 0.06, -0.3)
    place(tr, shimmer(3.0, count=70, decay=1.1), 0.5, 1.3)
    finish(tr, 'sfx_reveal_big', 0.3)

if __name__ == '__main__':
    make_intro(); make_bigA(); make_rev(); make_flip(); make_reveal_normal(); make_reveal_rare(); make_reveal_big(); make_glitch()
