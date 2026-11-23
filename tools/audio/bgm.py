"""Original lo-fi BGM for POKÉVAULT — seamless loops, rendered offline."""
import numpy as np, subprocess, os
from scipy import signal
SR = 44100
OUT = '/home/claude/blend/audio/out/'
os.makedirs(OUT, exist_ok=True)

def hz(m): return 440.0 * 2 ** ((m - 69) / 12)
def lp(x, f, o=2): b, a = signal.butter(o, f, 'low', fs=SR); return signal.lfilter(b, a, x, axis=0)
def hp(x, f, o=2): b, a = signal.butter(o, f, 'high', fs=SR); return signal.lfilter(b, a, x, axis=0)
def bp(x, lo, hi, o=2): b, a = signal.butter(o, [lo, hi], 'band', fs=SR); return signal.lfilter(b, a, x, axis=0)

def rhodes(f, dur, vel=1.0, rng=None):
    n = int(dur * SR); t = np.arange(n) / SR
    idx = 1.8 * np.exp(-t * 5) * vel + 0.25
    mod = np.sin(2 * np.pi * f * t) * idx
    car = np.sin(2 * np.pi * f * t + mod)
    tine = np.sin(2 * np.pi * f * 7.0 * t) * np.exp(-t * 18) * 0.12 * vel
    e = np.exp(-t * 0.9) * np.clip(t / 0.004, 0, 1) * np.clip((dur - t) / 0.08, 0, 1)
    return (car + tine) * e * vel

def bass(f, dur, vel=1.0):
    n = int(dur * SR); t = np.arange(n) / SR
    x = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t)
    x = np.tanh(x * 1.4)
    return x * np.clip(t / 0.01, 0, 1) * np.exp(-t * 1.2) * np.clip((dur - t) / 0.05, 0, 1) * vel

def kick(rng):
    n = int(0.35 * SR); t = np.arange(n) / SR
    return np.sin(2 * np.pi * np.cumsum(48 + 90 * np.exp(-t * 30)) / SR) * np.exp(-t * 9) + lp(rng.standard_normal(n), 900) * np.exp(-t * 60) * 0.2

def snare(rng):
    n = int(0.3 * SR); t = np.arange(n) / SR
    return bp(rng.standard_normal(n), 900, 6000) * np.exp(-t * 18) * 0.55 + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25) * 0.35

def hat(rng, open_=False):
    n = int((0.25 if open_ else 0.06) * SR); t = np.arange(n) / SR
    return hp(rng.standard_normal(n), 7000) * np.exp(-t * (14 if open_ else 70)) * 0.25

def bell(f, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 3 * t) * np.exp(-t * 6)) * np.exp(-t * 2.2) * np.clip(t / 0.005, 0, 1)

def reverb(x, sec=2.2, mix=0.22, seed=3):
    r = np.random.default_rng(seed); n = int(sec * SR)
    ir = r.standard_normal((n, 2)) * np.exp(-np.arange(n) / SR * 6.9 / sec)[:, None]
    ir = lp(ir, 4500); ir /= np.sqrt((ir ** 2).sum(0))
    wet = np.stack([signal.fftconvolve(x[:, c], ir[:, c]) for c in range(2)], 1)
    out = np.zeros_like(wet); out[:len(x)] = x * (1 - mix); out += wet * mix * 1.3
    return out

def render(name, bpm, chords, bass_roots, melody, seed):
    rng = np.random.default_rng(seed)
    beat = 60 / bpm; bar = beat * 4; bars = len(chords)
    L = int(bars * bar * SR); tail = int(4 * SR)
    mix = np.zeros((L + tail, 2)); keys = np.zeros((L + tail, 2)); drums = np.zeros(L + tail)
    def add(buf, sig, t, pan=0.0, g=1.0):
        i = max(0, int(t * SR)); j = min(len(buf), i + len(sig))
        if buf.ndim == 2:
            l, r = np.cos((pan + 1) * np.pi / 4) * 1.41, np.sin((pan + 1) * np.pi / 4) * 1.41
            buf[i:j, 0] += sig[:j - i] * g * l; buf[i:j, 1] += sig[:j - i] * g * r
        else: buf[i:j] += sig[:j - i] * g
    swing = beat / 2 * 0.16
    for b, ch in enumerate(chords):
        t0 = b * bar
        # chord: strum slightly, play on 1 and the "and" of 2 (lazy comping)
        for hit, dur, v in ((0.0, beat * 1.6, 1.0), (beat * 1.5 + swing, beat * 2.4, 0.7)):
            for k, m in enumerate(ch):
                add(keys, rhodes(hz(m), dur, v * rng.uniform(0.75, 0.95)), t0 + hit + k * 0.012 + rng.uniform(0, 0.006), pan=-0.35 + 0.7 * k / max(1, len(ch) - 1), g=0.09)
        r = bass_roots[b]
        add(mix, bass(hz(r), beat * 1.4), t0, 0, 0.22)
        add(mix, bass(hz(r), beat * 0.6, 0.8), t0 + beat * 2.5 + swing, 0, 0.2)
        add(mix, bass(hz(r + 7 if b % 2 else r + 12), beat * 0.9, 0.7), t0 + beat * 3, 0, 0.16)
        # drums (boom-bap with swing), skip drums on the first bar for a soft loop entry
        for s in range(8):
            ts = t0 + s * beat / 2 + (swing if s % 2 else 0)
            add(drums, hat(rng, open_=(s == 7 and b % 4 == 3)), ts + rng.uniform(-0.004, 0.004), g=rng.uniform(0.5, 0.9))
        add(drums, kick(rng), t0, g=0.9); add(drums, kick(rng), t0 + beat * 2.5 + swing, g=0.7)
        if b % 2: add(drums, kick(rng), t0 + beat * 3.5 + swing, g=0.45)
        add(drums, snare(rng), t0 + beat, g=0.55); add(drums, snare(rng), t0 + beat * 3, g=0.6)
    for (bar_i, beat_i, m, d) in melody:
        add(keys, bell(hz(m), beat * d * 1.8), bar_i * bar + beat_i * beat + (swing if (beat_i * 2) % 2 else 0), pan=0.25, g=0.07)
    # sidechain feel: duck keys + bass slightly on kicks
    env = np.ones(L + tail); kt = []
    for b in range(bars):
        kt += [b * bar, b * bar + beat * 2.5 + swing]
    t = np.arange(L + tail) / SR
    for k in kt:
        i = int(k * SR); n = int(0.25 * SR); j = min(len(env), i + n)
        env[i:j] = np.minimum(env[i:j], 1 - 0.35 * np.exp(-np.arange(j - i) / SR * 14))
    # tape wow on keys
    wow = 1 + 0.0009 * np.sin(2 * np.pi * 0.6 * t) + 0.0004 * np.sin(2 * np.pi * 3.1 * t)
    idx = np.clip(np.cumsum(wow) - 1, 0, len(keys) - 1)
    keys = np.stack([np.interp(idx, np.arange(len(keys)), keys[:, c]) for c in range(2)], 1)
    keys = reverb(lp(keys, 5200), mix=0.28)[:L + tail]
    mix = mix + keys
    mix *= env[:, None]
    drums_f = lp(hp(drums, 40), 7500)
    mix[:, 0] += drums_f * 0.32; mix[:, 1] += drums_f * 0.32
    # vinyl crackle + hiss
    cr = (rng.random(L + tail) < 0.0006) * rng.uniform(-1, 1, L + tail)
    vin = hp(cr, 1500) * 0.15 + lp(rng.standard_normal(L + tail), 3500) * 0.004
    mix += np.stack([vin, np.roll(vin, 37)], 1)
    # seamless loop: fold the tail back onto the start
    out = mix[:L].copy(); out[:tail] += mix[L:L + tail]
    out = lp(out, 9500)
    out = np.tanh(out * 1.6) / 1.6
    out = out / np.abs(out).max() * 0.6
    P = int(0.1 * SR)
    ext = np.concatenate([out[-P:], out, out[:P]])
    print('LOOP', name, 'start', P / SR, 'len_samples', L, 'len_sec', L / SR)
    raw = OUT + name + '.f32'; ext.astype('<f4').tofile(raw)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', raw,
                    '-c:a', 'libmp3lame', '-b:a', '112k', OUT + name + '.mp3'], check=True)
    os.remove(raw); print(name, round(L / SR, 1), 's')

# Track 1 — "Vault Night": Fmaj9 Em7 Dm9 G13 (x4 with turnaround)
C1 = [[53, 57, 60, 64, 67], [52, 55, 59, 62], [50, 53, 57, 60, 64], [55, 59, 64, 65]] * 3 + \
     [[53, 57, 60, 64, 67], [52, 55, 59, 62], [50, 53, 57, 60, 64], [55, 58, 61, 65]]
B1 = [41, 40, 38, 43] * 4
M1 = []
mot = [(0, 76), (1, 74), (1.5, 72), (2.5, 69)], [(0, 74), (1, 72), (2, 71)], [(0, 72), (0.5, 74), (1.5, 76), (2.5, 77)], [(0, 76), (1.5, 74)]
for rep in (1, 3):
    for bi, m in enumerate(mot):
        for (bt, note) in m: M1.append((rep * 4 + bi, bt, note, 1))

# Track 2 — "Card Shop Afternoon": Am9 D9 Gmaj7 Cmaj7 F#m7b5 B7 Em9 Em9
C2 = [[57, 60, 64, 67, 71], [54, 57, 60, 64], [55, 59, 62, 66], [52, 55, 59, 64],
      [54, 57, 60, 64], [51, 54, 57, 63], [52, 55, 59, 62, 66], [52, 55, 59, 62, 67]] * 2
B2 = [45, 38, 43, 36, 42, 35, 40, 40] * 2
M2 = []
mot2 = [[(0, 76), (1, 79), (2, 76)], [(0, 74), (1.5, 72)], [(0, 71), (1, 74), (2, 78)], [(0, 76)],
        [(0, 72), (1, 76), (2, 79)], [(0, 78), (1.5, 75)], [(0, 74), (1, 71), (2, 67)], [(0, 71)]]
for bi, m in enumerate(mot2):
    for (bt, note) in m: M2.append((8 + bi, bt, note, 1.2))

if __name__ == '__main__':
    render('bgm_vault_night', 78, C1, B1, M1, 11)
    render('bgm_card_shop', 84, C2, B2, M2, 12)
