#!/home/piyushmishra/trst01-eudr/.venv/bin/python
"""Snap rough centre lines (roads_px.py) onto bright linear tracks in the photo composite."""
import numpy as np, json
from scipy.ndimage import map_coordinates, median_filter
from skimage import morphology, color
from roads_px import ROADS
X0, Y0 = -60, 20                     # composite origin in p05 px
o = np.load("/tmp/claude-1000/-home-piyushmishra/a35a57fc-21d5-4116-a1e5-b9d1e23c3518/scratchpad/comp.npy")
L = color.rgb2lab(o)[..., 0].astype(np.float32)
score = morphology.white_tophat(L, morphology.disk(12))
def dens(pts, step=10):
    out = []
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        n = max(1, int(np.hypot(x2 - x1, y2 - y1) // step))
        out += [(x1 + (x2 - x1) * t / n, y1 + (y2 - y1) * t / n) for t in range(n)]
    return np.array(out + [pts[-1]], float)
snapped = {}
for name, (w, pts) in ROADS.items():
    p = dens(pts); d = np.gradient(p, axis=0); d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    r = 14 if name == "north road" else 8
    offs = np.arange(-r, r + 1)
    best = []
    for (x, y), nv in zip(p, nrm):
        prof = []
        for o_ in offs:
            # mean score across the road width, centred at this offset
            ks = np.arange(-w // 2, w // 2 + 1)
            xs = x + nv[0] * (o_ + ks) - X0; ys = y + nv[1] * (o_ + ks) - Y0
            prof.append(map_coordinates(score, [ys, xs], order=1, mode="nearest").mean())
        best.append(offs[int(np.argmax(prof))])
    best = median_filter(np.array(best, float), size=9, mode="nearest")
    best = np.convolve(np.pad(best, 6, mode="edge"), np.ones(13) / 13, mode="valid")
    q = p + nrm * best[:, None]
    snapped[name] = [w, q.round(1).tolist(), float(np.abs(best).mean())]
    print(f"{name:22s} mean shift {np.abs(best).mean() * 0.5:.1f} m, max {np.abs(best).max() * 0.5:.1f} m")
json.dump(snapped, open("roads_snapped.json", "w"))
