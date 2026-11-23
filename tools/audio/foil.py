"""Booster-pack foil SFX (metallised plastic crinkle / tear), synthesized."""
import numpy as np
from sfx import *   # helpers: noise, bp, hp, lp, track, place, finish, T, rng, bell, slide, tap, shimmer

def foil_grains(n, density, lo=2500, hi=14000, loud=(0.2, 1.0), Lr=(20, 180)):
    x = np.zeros(n)
    for p in rng.integers(0, max(1, n - 400), int(density * n / SR)):
        L = rng.integers(*Lr); g = rng.uniform(*loud)
        x[p:p + L] += noise(L) * np.exp(-np.arange(L) / (L / 5)) * g
    # plastic "tick" resonances
    for p in rng.integers(0, max(1, n - 800), int(density * 0.05 * n / SR)):
        f = rng.uniform(3000, 7000); L = 600; t = np.arange(L) / SR
        x[p:p + L] += np.sin(2 * np.pi * f * t) * np.exp(-t * 900) * rng.uniform(0.3, 0.8)
    return bp(x, lo, hi)

def foil_loop(sec=2.0):
    n = T(sec); x = foil_grains(n + T(0.3), 2600) * 0.5
    x += bp(noise(n + T(0.3)), 1500, 9000) * (0.25 + np.abs(lp(noise(n + T(0.3)), 30)) * 2) * 0.12
    # seamless: crossfade the extra 0.3 s back onto the start
    fade = T(0.3); body = x[:n].copy(); w = np.linspace(0, 1, fade)
    body[:fade] = body[:fade] * w + x[n:n + fade] * (1 - w)
    tr = np.stack([body, np.roll(body, 211)], 1)
    return tr

def make():
    tr = foil_loop(); tr = tr / np.abs(tr).max() * 0.8
    import subprocess
    raw = OUT + 'sfx_foil_loop.f32'; tr.astype('<f4').tofile(raw)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', raw, '-c:a', 'libmp3lame', '-b:a', '128k', OUT + 'sfx_foil_loop.mp3'], check=True)
    os.remove(raw); print('sfx_foil_loop')

    tr = track(0.7); place(tr, foil_grains(T(0.55), 1800) * bell(T(0.55)), 0.0, 0.6); finish(tr, 'sfx_foil_grab', 0.12)

    tr = track(0.9)  # final rip: accelerating tear then snap
    n = T(0.35); k = np.linspace(0, 1, n)
    place(tr, foil_grains(n, 5000, loud=(0.4, 1.2)) * (0.4 + k) * 0.7, 0.0)
    place(tr, hp(noise(T(0.05)), 2000) * np.exp(-np.arange(T(0.05)) / SR * 120) * 0.9, 0.33)   # snap
    place(tr, foil_grains(T(0.4), 900) * np.exp(-np.arange(T(0.4)) / SR * 8) * 0.4, 0.36, 1.0, 0.5)  # strip flutters away
    finish(tr, 'sfx_foil_rip', 0.15)

    tr = track(1.6)  # pack opens: plastic pop, cards slide out, settle
    place(tr, lp(noise(T(0.08)), 1800) * np.exp(-np.arange(T(0.08)) / SR * 60) * 0.8, 0.0)
    place(tr, foil_grains(T(0.3), 1500) * bell(T(0.3)) * 0.5, 0.02)
    place(tr, slide(0.55, 7000) * 6, 0.15)
    place(tr, tap(0.6), 0.72)
    finish(tr, 'sfx_pack_open', 0.2)

    for i, (b, lo) in enumerate(((6500, 1100), (5200, 900))):
        tr = track(0.5); place(tr, slide(0.22, b) * 9, 0.0, 1.0, -0.2 + 0.4 * i)
        place(tr, hp(noise(T(0.02)), 3000) * np.exp(-np.arange(T(0.02)) / SR * 300) * 0.4, 0.2)
        finish(tr, f'sfx_card_slide{i}', 0.1)

    tr = track(0.9)  # fan spread: quick riffle
    for j in range(9): place(tr, slide(0.07, 7000) * 7 + 0, 0.05 + j * 0.05, rng.uniform(0.6, 1.0), rng.uniform(-0.5, 0.5))
    finish(tr, 'sfx_shuffle', 0.12)

if __name__ == '__main__':
    make()
