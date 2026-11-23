"""Original GB-era-style chiptune BGM loops for POKÉVAULT (no existing game melodies)."""
import numpy as np, subprocess, os
from scipy import signal
import chip as C
SR = 44100
OUT = '/home/claude/blend/audio/out/'

def chord_notes(name):
    roots = {'C': 60, 'D': 62, 'E': 64, 'F': 65, 'G': 67, 'A': 69}
    minor = name.endswith('m'); r = roots[name[0]]
    return [r, r + (3 if minor else 4), r + 7]

def render(name, bpm, chords, melody, drums='full', vol_lead=0.11):
    beat = 60 / bpm; bars = len(chords)
    L = int(bars * 4 * beat * SR); tail = int(2.5 * SR)
    buf = np.zeros((L + tail, 2))
    def B(bar, b): return (bar * 4 + b) * beat
    for bi, ch in enumerate(chords):
        notes = chord_notes(ch)
        # pulse 2: 16th-note broken chord, low octave, thin duty (classic handheld texture)
        pat = [0, 1, 2, 1] * 4
        for s, k in enumerate(pat):
            C.place(buf, C.pulse(C.hz(notes[k] - 12), beat / 4 * 0.85, 0.125, 1.0, decay=3), B(bi, s / 4), 0.035, -0.35)
        # wave bass: root / octave / fifth bounce
        r = notes[0] - 24
        for s, iv in enumerate([0, 12, 7, 12, 0, 12, 7, 12]):
            C.place(buf, C.wave_bass(C.hz(r + iv), beat / 2 * 0.8), B(bi, s / 2), 0.11)
        # noise drums
        for b in range(4):
            if drums == 'full':
                if b in (0, 2): C.place(buf, C.nz_drum('k'), B(bi, b), 0.35)
                if b in (1, 3): C.place(buf, C.nz_drum('s'), B(bi, b), 0.22, 0.1)
                C.place(buf, C.nz_drum('h'), B(bi, b + 0.5), 0.25, 0.35)
            else:
                if b == 0: C.place(buf, C.nz_drum('k'), B(bi, b), 0.25)
                C.place(buf, C.nz_drum('h'), B(bi, b + 0.5), 0.15, 0.35)
    # pulse 1: lead (50% duty + light vibrato) with a quiet echo channel
    for bi, bar in enumerate(melody):
        for (b, m, d) in bar:
            t = B(bi, b)
            C.place(buf, C.pulse(C.hz(m), beat * d * 0.92, 0.5, 1.0, vib=0.005 if d >= 1 else 0), t, vol_lead, 0.12)
            C.place(buf, C.pulse(C.hz(m), beat * d * 0.85, 0.25, 1.0, decay=4), t + beat * 0.75, vol_lead * 0.25, -0.5)
    # light room + gentle top roll-off
    n = int(1.2 * SR); rr = np.random.default_rng(1)
    ir = rr.standard_normal((n, 2)) * np.exp(-np.arange(n) / SR * 5.5)[:, None]; ir = C.lp(ir, 5000); ir /= np.sqrt((ir ** 2).sum(0))
    wet = np.stack([signal.fftconvolve(buf[:, c], ir[:, c])[:len(buf)] for c in range(2)], 1)
    buf = buf * 0.85 + wet * 0.18
    buf = C.lp(buf, 11000)
    out = buf[:L].copy(); out[:tail] += buf[L:L + tail]       # seamless wrap
    out = out / np.abs(out).max() * 0.6
    P = int(0.1 * SR); ext = np.concatenate([out[-P:], out, out[:P]])
    print('LOOP', name, 'len_samples', L, 'sec', round(L / SR, 2))
    raw = OUT + name + '.f32'; ext.astype('<f4').tofile(raw)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', raw,
                    '-c:a', 'libmp3lame', '-b:a', '112k', OUT + name + '.mp3'], check=True)
    os.remove(raw)

# ---- Track 1: "Adventure Road" — upbeat route theme, G major, 136 BPM
ADV_CH = ['G', 'D', 'Em', 'C', 'G', 'D', 'C', 'D', 'Em', 'C', 'G', 'D', 'C', 'D', 'G', 'G']
ADV = [
    [(0, 67, .5), (.5, 71, .5), (1, 74, 1), (2, 79, 1), (3, 78, .5), (3.5, 76, .5)],
    [(0, 74, 1.5), (1.5, 73, .5), (2, 74, .5), (2.5, 76, .5), (3, 78, 1)],
    [(0, 79, .5), (.5, 78, .5), (1, 76, 1), (2, 71, 1), (3, 74, 1)],
    [(0, 72, 1.5), (1.5, 71, .5), (2, 72, .5), (2.5, 74, .5), (3, 76, 1)],
    [(0, 74, .5), (.5, 79, .5), (1, 83, 1.5), (2.5, 81, .5), (3, 79, 1)],
    [(0, 78, 1), (1, 76, .5), (1.5, 74, .5), (2, 76, 1), (3, 78, 1)],
    [(0, 79, .5), (.5, 76, .5), (1, 72, 1), (2, 74, .5), (2.5, 76, .5), (3, 72, 1)],
    [(0, 74, 3), (3, 66, .5), (3.5, 69, .5)],
    [(0, 71, 1), (1, 74, .5), (1.5, 76, .5), (2, 79, 1.5), (3.5, 78, .5)],
    [(0, 76, 1), (1, 72, 1), (2, 67, 1), (3, 72, 1)],
    [(0, 74, 1.5), (1.5, 71, .5), (2, 67, 1), (3, 71, 1)],
    [(0, 69, 1), (1, 73, 1), (2, 76, 1), (3, 81, 1)],
    [(0, 79, 1.5), (1.5, 76, .5), (2, 72, 1), (3, 76, 1)],
    [(0, 78, 1.5), (1.5, 74, .5), (2, 69, 1), (3, 78, 1)],
    [(0, 79, 1), (1, 83, 1), (2, 86, 2)],
    [(0, 83, .5), (.5, 79, .5), (1, 74, 1), (2, 71, 1), (3, 74, .5), (3.5, 78, .5)],
]

# ---- Track 2: "Cozy Town" — gentle town theme, C major, 104 BPM
TOWN_CH = ['C', 'Am', 'F', 'G', 'C', 'Am', 'D', 'G', 'Em', 'Am', 'F', 'G', 'F', 'G', 'C', 'C']
TOWN = [
    [(0, 76, 1), (1, 79, 1), (2, 84, 1.5), (3.5, 83, .5)],
    [(0, 81, 2), (2, 79, 1), (3, 76, 1)],
    [(0, 77, 1), (1, 81, 1), (2, 79, 1), (3, 77, 1)],
    [(0, 76, 1.5), (1.5, 74, .5), (2, 71, 2)],
    [(0, 72, 1), (1, 76, 1), (2, 79, 1), (3, 84, 1)],
    [(0, 81, 1.5), (1.5, 79, .5), (2, 76, 2)],
    [(0, 78, 1), (1, 76, 1), (2, 74, 1), (3, 78, 1)],
    [(0, 79, 3), (3, 74, 1)],
    [(0, 79, 1), (1, 83, 1), (2, 79, 1), (3, 76, 1)],
    [(0, 81, 2), (2, 76, 1), (3, 72, 1)],
    [(0, 77, 1), (1, 81, 1), (2, 84, 1), (3, 81, 1)],
    [(0, 79, 2), (2, 74, 1), (3, 77, 1)],
    [(0, 77, 1), (1, 76, 1), (2, 74, 1), (3, 72, 1)],
    [(0, 74, 1), (1, 77, 1), (2, 79, 2)],
    [(0, 76, 1), (1, 79, 1), (2, 84, 2)],
    [(0, 72, 2), (2, 67, 1), (3, 71, 1)],
]

if __name__ == '__main__':
    render('bgm_adventure_road', 136, ADV_CH, ADV, 'full')
    render('bgm_cozy_town', 104, TOWN_CH, TOWN, 'light', 0.1)
