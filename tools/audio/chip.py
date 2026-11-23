"""Chiptune / hype music building blocks (original material, GB-era style)."""
import numpy as np
from scipy import signal
SR = 44100

def hz(m): return 440.0 * 2 ** ((m - 69) / 12)
def lp(x, f, o=2): b, a = signal.butter(o, f, 'low', fs=SR); return signal.lfilter(b, a, x, axis=0)
def hp(x, f, o=2): b, a = signal.butter(o, f, 'high', fs=SR); return signal.lfilter(b, a, x, axis=0)
def bp(x, lo, hi, o=2): b, a = signal.butter(o, [lo, hi], 'band', fs=SR); return signal.lfilter(b, a, x, axis=0)
R = np.random.default_rng(5)

def pulse(f, dur, duty=0.25, vol=1.0, vib=0.0, decay=0.0, slide_to=None):
    n = int(dur * SR); t = np.arange(n) / SR
    ff = np.full(n, f) if slide_to is None else f * (slide_to / f) ** np.clip(t / dur, 0, 1)
    if vib: ff = ff * (1 + vib * np.sin(2 * np.pi * 5.5 * t) * np.clip((t - 0.12) / 0.1, 0, 1))
    ph = np.cumsum(ff) / SR
    x = np.where((ph % 1) < duty, 1.0, -1.0)
    e = np.clip((dur - t) / 0.012, 0, 1) * np.clip(t / 0.002, 0, 1)
    if decay: e *= np.exp(-t * decay)
    return x * e * vol

def wave_bass(f, dur, vol=1.0):  # 4-bit triangle like the GB wave channel
    n = int(dur * SR); t = np.arange(n) / SR
    tri = 2 * np.abs(2 * ((f * t) % 1) - 1) - 1
    tri = np.round(tri * 7.5) / 7.5
    return tri * np.clip((dur - t) / 0.01, 0, 1) * vol

def nz_drum(kind, vol=1.0):
    if kind == 'k':
        n = int(0.16 * SR); t = np.arange(n) / SR
        return (np.sin(2 * np.pi * np.cumsum(55 + 160 * np.exp(-t * 40)) / SR) * np.exp(-t * 20)) * vol
    if kind == 's':
        n = int(0.14 * SR); t = np.arange(n) / SR
        x = np.sign(R.standard_normal(n)) * (np.arange(n) % 3 == 0)
        x = np.repeat(np.sign(R.standard_normal(n // 6 + 1)), 6)[:n]   # GB-style stepped noise
        return x * np.exp(-t * 22) * 0.6 * vol
    n = int(0.05 * SR); t = np.arange(n) / SR
    return hp(R.standard_normal(n), 6000) * np.exp(-t * 90) * 0.35 * vol

def place(buf, sig, t, g=1.0, pan=0.0):
    i = max(0, int(t * SR)); j = min(len(buf), i + len(sig))
    if j <= i: return
    if buf.ndim == 2:
        l, r = np.cos((pan + 1) * np.pi / 4) * 1.41, np.sin((pan + 1) * np.pi / 4) * 1.41
        buf[i:j, 0] += sig[:j - i] * g * l; buf[i:j, 1] += sig[:j - i] * g * r
    else:
        buf[i:j] += sig[:j - i] * g

# ---------------------------------------------------------------- orchestral hype elements
def saw_stack(freqs, dur, vol=1.0, attack=0.02, cutoff=3500):
    n = int(dur * SR); t = np.arange(n) / SR; x = np.zeros(n)
    for f in freqs:
        for d in (-0.2, 0.0, 0.2):
            x += signal.sawtooth(2 * np.pi * f * (1 + d / 100) * t + R.uniform(0, 6))
    x = lp(x, cutoff)
    e = np.clip(t / attack, 0, 1) * np.clip((dur - t) / 0.15, 0, 1)
    return x * e * vol / (3 * len(freqs))

def timpani(f=65, vol=1.0):
    n = int(1.4 * SR); t = np.arange(n) / SR
    body = np.sin(2 * np.pi * np.cumsum(f * (1 + 0.15 * np.exp(-t * 25))) / SR) * np.exp(-t * 3.2)
    return (body + lp(R.standard_normal(n), 800) * np.exp(-t * 30) * 0.5) * vol

def stab(chord_midi, vol=1.0, dur=0.55):
    """orchestra hit: brass/strings stack + timpani + cymbal"""
    n = int(max(dur, 1.6) * SR); out = np.zeros(n)
    s = saw_stack([hz(m) for m in chord_midi], dur, 1.0, 0.006, 5000)
    out[:len(s)] += s * 1.4
    tp = timpani(hz(chord_midi[0] - 12), 0.9); out[:len(tp)] += tp
    t = np.arange(n) / SR
    out += hp(R.standard_normal(n), 5000) * np.exp(-t * 2.5) * 0.18
    return out * vol

def drumroll(dur, bpm=150, start_div=4, end_div=16, vol=1.0):
    """snare roll that accelerates and swells"""
    out = np.zeros(int(dur * SR) + SR // 4); t = 0.0; beat = 60 / bpm
    while t < dur:
        k = t / dur
        div = start_div * (end_div / start_div) ** k
        sn = nz_drum('s', 0.35 + 0.75 * k ** 1.5)
        place(out, sn, t)
        t += beat * 4 / div   # div = hits per bar (4 = quarters ... 32 = 32nds)
    return out[:int(dur * SR) + SR // 4] * vol

def arp_run(chord_midi, dur, rate=24, octaves=2, duty=0.25, vol=1.0):
    """fast rising chiptune arpeggio"""
    out = np.zeros(int(dur * SR) + 2000)
    notes = [m + 12 * o for o in range(octaves) for m in chord_midi]
    step = 1 / rate; i = 0; t = 0.0
    while t < dur:
        m = notes[i % len(notes)]
        place(out, pulse(hz(m), step * 0.9, duty, 1.0), t)
        i += 1; t += step
    return out * vol

def heartbeat(t0, buf, beats=4, bpm=80, vol=1.0):
    for b in range(beats):
        tt = t0 + b * 60 / bpm
        place(buf, timpani(48, 0.6) * 0.8, tt, vol); place(buf, timpani(44, 0.4) * 0.6, tt + 0.16, vol)
