"""Relief v2: ground relief only. Trees go to web/trees.json and buildings are cut out; the viewer builds both as real 3D objects.
Inputs: AI depth (depth.py), tree crowns (trees.py, DeepForest), footprints (buildings.py, SAM 2.1)."""
import json, numpy as np, cv2, pandas as pd
from scipy import ndimage as ndi
W, H = 2016, 1512; M = 0.208                                   # work grid, metres per px
im = cv2.resize(cv2.imread("web/tex_hd.jpg"), (W, H), interpolation=cv2.INTER_AREA)
d = cv2.resize(np.load("work/d0995.npy").astype(np.float32), (W, H))
ground = cv2.GaussianBlur(cv2.erode(d, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (61, 61))), (0, 0), 40)
obj = cv2.GaussianBlur(np.clip(d - ground, 0, None), (0, 0), 1.6); obj /= np.percentile(obj, 99.7)
b, g, r = [c.astype(np.float32) for c in cv2.split(im)]
exg = cv2.GaussianBlur((2 * g - r - b) / (r + g + b + 1), (0, 0), 1.5)
veg = cv2.morphologyEx((exg > 0.035).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
B = np.zeros((H, W), np.uint8)
for bd in json.load(open("web/buildings.json"))["buildings"]:
    cv2.fillPoly(B, [np.int32(np.array(bd["poly"]) / 2)], 1)
Bd = cv2.dilate(B, np.ones((9, 9), np.uint8))

# 1) crowns DeepForest found
crowns = []                                                     # cx, cy, rx, ry (px)
covered = np.zeros((H, W), np.uint8)
for t in pd.read_csv("work/trees.csv").itertuples():
    cx, cy, rx, ry = (t.xmin + t.xmax) / 4, (t.ymin + t.ymax) / 4, (t.xmax - t.xmin) / 4, (t.ymax - t.ymin) / 4
    if t.score < 0.2 or not 0.6 < rx / ry < 1.7 or not 0.8 < min(rx, ry) * M < 14: continue
    m = np.zeros((H, W), np.uint8); cv2.ellipse(m, (int(cx), int(cy)), (int(rx), int(ry)), 0, 0, 360, 1, -1)
    if veg[m > 0].mean() < 0.55 or Bd[m > 0].mean() > 0.2: continue
    crowns.append((cx, cy, rx, ry)); covered |= m
n_df = len(crowns)
# 2) the rest of the tall vegetation (plantation blocks, clumps): one crown per bright canopy peak
tall = (veg > 0) & (obj > 0.10) & (Bd == 0)
tall = cv2.morphologyEx(tall.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
lum = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2LAB)[..., 0].astype(np.float32), (0, 0), 3.5) + 40 * cv2.GaussianBlur(obj, (0, 0), 3)
pk = (lum == ndi.maximum_filter(lum, size=19)) & (tall > 0) & (covered == 0)
ys, xs = np.where(pk); dt = cv2.distanceTransform(tall, cv2.DIST_L2, 5)
from scipy.spatial import cKDTree
P = np.c_[xs, ys].astype(np.float32); nn = cKDTree(P).query(P, k=2)[0][:, 1]
for (x, y), dn in zip(P, nn):
    rad = float(np.clip(min(0.62 * dn, dt[int(y), int(x)] + 5), 6, 24))
    crowns.append((x, y, rad, rad))
print(n_df, "DeepForest crowns +", len(crowns) - n_df, "canopy-peak crowns")

# 3) a height per crown: AI depth inside it, blended with crown width (wider tree = taller). The viewer builds the 3D crowns.
out = []; tmask = np.zeros((H, W), np.uint8)
for cx, cy, rx, ry in crowns:
    x0, x1, y0, y1 = int(max(cx - rx - 1, 0)), int(min(cx + rx + 2, W)), int(max(cy - ry - 1, 0)), int(min(cy + ry + 2, H))
    if x1 - x0 < 3 or y1 - y0 < 3: continue
    yy, xx = np.mgrid[y0:y1, x0:x1]; q = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
    hd = np.percentile(obj[y0:y1, x0:x1][q < 1], 85) if (q < 1).any() else 0
    ht = float(np.clip(0.55 * hd + 0.45 * 0.085 * (rx + ry) * M * 1.15, 0.15, 1.15))
    out.append([round(float(v), 1) for v in (cx * 2, cy * 2, rx * 2, ry * 2)] + [round(ht, 3)])      # drone px at 4032, relative height
    cv2.ellipse(tmask, (int(cx), int(cy)), (int(rx), int(ry)), 0, 0, 360, 1, -1)
json.dump(dict(size=[4032, 3024], trees=out), open("web/trees.json", "w"), separators=(",", ":"))
# 4) everything else: low crops keep a little texture, bare ground/shadows go flat, buildings cut out
low = cv2.GaussianBlur(obj * veg, (0, 0), 2) * 0.35 + cv2.GaussianBlur(obj * (1 - veg), (0, 0), 4) * 0.12
h = np.minimum(low, 0.25) * (1 - Bd) * (1 - 0.75 * cv2.GaussianBlur(tmask.astype(np.float32), (0, 0), 2))   # flat under the 3D trees
h = cv2.GaussianBlur(h, (0, 0), 0.8)
h = h + 0.08 * (ground - ground.min()) / (np.ptp(ground) + 1e-6)
np.save("work/h2.npy", h); print("max", h.max())
def pack(a, size, path):
    a = cv2.resize(a, size, interpolation=cv2.INTER_AREA); v = np.clip(a / 1.3 * 65535, 0, 65535).astype(np.uint16)
    rg = np.zeros((*v.shape, 3), np.uint8); rg[..., 2] = v >> 8; rg[..., 1] = v & 255      # BGR order: R = high byte, G = low byte
    cv2.imwrite(path, rg, [cv2.IMWRITE_PNG_COMPRESSION, 9])
pack(h, (1008, 756), "web/height_hd.png"); pack(h, (504, 378), "web/height_sd.png")
vis = cv2.applyColorMap(np.clip(h / h.max() * 255, 0, 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
cv2.imwrite("work/h2_vis.jpg", np.hstack([cv2.resize(im, (1008, 756)), cv2.resize(vis, (1008, 756))]), [1, 85])
