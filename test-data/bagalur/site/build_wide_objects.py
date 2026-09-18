"""Structures and trees on the ground only the 500 m photo sees (outside the 350 m photo). Roofs by colour and shape, straightened to rectangles; trees as dark green round blobs.
Writes work/wide_structures.json and work/wide_trees.json (world metres); build_flora.py merges them. Overlay for checking: work/wide_objects.jpg"""
import json, cv2, numpy as np
from build_site_geo import photo_px, DW, DH
WJ = json.load(open("work/wide.json")); im = cv2.imread("work/wide_enh.png"); valid = cv2.imread("work/wide_valid.png", 0); k = 0.5; mp = WJ["m_per_px"] / k
im = cv2.resize(im, None, fx=k, fy=k, interpolation=cv2.INTER_AREA); valid = cv2.resize(valid, (im.shape[1], im.shape[0])) == 255; H, W = im.shape[:2]
to_w = lambda x, y: (WJ["x0"] + x * mp, WJ["z0"] + y * mp)
inner = np.zeros((H, W), np.uint8)                                                         # ground the main photo already covers (its buildings and trees come from there)
cv2.fillPoly(inner, [np.int32([[(wx - WJ["x0"]) / mp, (wz - WJ["z0"]) / mp] for wx, wz in [__import__("build_site_geo").world_px(*q) for q in [(60, 60), (DW - 60, 60), (DW - 60, DH - 60), (60, DH - 60)]]])], 1)
f = im.astype(np.float32); b, g, r = f[..., 0], f[..., 1], f[..., 2]; hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV); lum = f.mean(2)
tex = np.sqrt(np.maximum(cv2.blur(lum * lum, (9, 9)) - cv2.blur(lum, (9, 9)) ** 2, 0))
def blobs(mask, min_m2, ksz=5):
    m = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, np.ones((ksz, ksz), np.uint8)); m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((ksz * 2 + 1, ksz * 2 + 1), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m); return [(lab == i, st[i]) for i in range(1, n) if st[i, 4] * mp * mp >= min_m2]
S = []
def add(kind, comp, roof, h, min_fill=0.72, max_w=1e9):
    pts = np.argwhere(comp)[:, ::-1].astype(np.float32); (cx, cy), (w, d), a = cv2.minAreaRect(pts); fill = comp.sum() / max(w * d, 1)
    if fill < min_fill or min(w, d) * mp < 4.5 or min(w, d) * mp > max_w: return
    if inner[int(cy), int(cx)] and kind != 'poultry': return
    if kind != 'poultry' and fill < 0.93:                   # not a true rectangle (a tapering plastic tunnel): keep its own outline, straightened to a few edges
        ke = int(3.0 / mp) | 1; tight = cv2.erode(cv2.morphologyEx(comp.astype(np.uint8), cv2.MORPH_OPEN, np.ones((int(8 / mp) | 1,) * 2, np.uint8)), np.ones((ke, ke), np.uint8))      # drop thin spurs, then pull the walls 1.5 m inside the sheet's edge: plastic drapes outward, and tracks run right beside it
        cs = cv2.findContours(tight, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
        if not cs: return
        c = max(cs, key=cv2.contourArea); ring = cv2.approxPolyDP(c, 1.0 / mp, True).reshape(-1, 2); h = min(h, 3.2) if w * d * mp * mp > 1500 else h
        if len(ring) >= 3: x, z = to_w(cx, cy); S.append(dict(x=round(x, 2), z=round(z, 2), ring=[[round(v, 2) for v in to_w(*q)] for q in ring], h=h, roof="flat", kind=kind, big=int(w * d * mp * mp > 1500), src="wide")); return
    s_ = fill ** 0.5 * 1.02 if kind != 'poultry' else 1.0; x, z = to_w(cx, cy)
    if kind == 'poultry':                                   # tiled sheds here are about 11 m across; the colour mask tends to catch a little less
        if w < d: w, d = 11.5 / mp, d + 1.5 / mp
        else: w, d = w + 1.5 / mp, 11.5 / mp
    S.append(dict(x=round(x, 2), z=round(z, 2), w=round(w * mp * s_, 2), d=round(d * mp * s_, 2), a=round(float(np.deg2rad(a)), 4), h=h, roof=roof, kind=kind, big=int(w * d * mp * mp > 1500), src="wide"))
red = (r - g > 72) & (r - b > 95) & (r > 205) & valid                        # tiled poultry sheds: red, even-textured (ploughed red soil is rougher and duller)
for comp, st in blobs(red, 60, 7):
    pts = np.argwhere(comp)[:, ::-1].astype(np.float32); (cx, cy), (w, d), ang = cv2.minAreaRect(pts)
    if max(w, d) / max(min(w, d), 1) < 3 or min(w, d) * mp > 14 or max(w, d) * mp < 25: continue
    add("poultry", comp, "gable", 3.0, 0.55)
white = (hsv[..., 1] < 55) & (lum > 178) & valid                                           # sheet roofs, terraces, plastic tunnels
for comp, st in blobs(white, 25): add("building", comp, "flat", 3.4, 0.7)
poly = (hsv[..., 1] < 60) & (lum > 120) & (lum <= 200) & (b >= r - 6) & (tex < 16) & valid      # polyhouses and net houses: large, pale, slightly blue-green, very even
for comp, st in blobs(poly, 400, 9): add("polyhouse", comp, "flat", 4.5, 0.75)
for x_, z_, w_, d_ in [(374, -100, 9, 6), (355.5, -47.8, 6, 7)]: S.append(dict(x=x_, z=z_, w=w_, d=d_, a=0.04, h=3.2, roof='flat', kind='building', big=0, src='wide'))      # small white buildings the colour rule misses, read off the photo
S = [s for i, s in enumerate(S) if not any(j < i and abs(s["x"] - t["x"]) < 4 and abs(s["z"] - t["z"]) < 4 for j, t in enumerate(S))]
# trees: dark, green, round, 2-12 m across
lm = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32); exg = (2 * g - r - b) / (r + g + b + 1); T = []
for s1, s2, thr in ((2.5, 7, 9), (6, 16, 8)):
    dog = cv2.GaussianBlur(lm, (0, 0), s2) - cv2.GaussianBlur(lm, (0, 0), s1); ks = int(s1 * 4) | 1
    pk = (dog == cv2.dilate(dog, np.ones((ks, ks), np.uint8))) & (dog > thr) & (cv2.GaussianBlur(exg, (0, 0), s1) > 0.035) & (cv2.GaussianBlur(lm, (0, 0), s1) < 105) & (cv2.GaussianBlur(exg, (0, 0), s2 * 1.5) < 0.075) & valid & (inner == 0)      # a dark dot inside a green crop is a plant row, not a tree
    for y, x in np.argwhere(pk):
        rad = float(np.clip(s1 * mp * 1.5 * (0.8 + (dog[y, x] - thr) * 0.03), 1.0, 6.5))
        if any(abs(x - t[0]) * mp < max(rad, t[2]) and abs(y - t[1]) * mp < max(rad, t[2]) for t in T[-400:]): continue
        T.append((x, y, rad))
roofm = np.zeros((H, W), np.uint8)
def ring_px(s):
    if 'ring' in s: return np.int32([[(x - WJ['x0']) / mp, (z - WJ['z0']) / mp] for x, z in s['ring']])
    c_, s_ = np.cos(s['a']), np.sin(s['a']); return np.int32([[(s['x'] + c_ * i * s['w'] / 2 - s_ * j * s['d'] / 2 - WJ['x0']) / mp, (s['z'] + s_ * i * s['w'] / 2 + c_ * j * s['d'] / 2 - WJ['z0']) / mp] for i, j in [(-1, -1), (1, -1), (1, 1), (-1, 1)]])
for s in S: cv2.fillPoly(roofm, [ring_px(s)], 1)
T = [t for t in T if not roofm[t[1], t[0]]]; vis = im.copy(); out = []
for x, y, rad in T:
    px = im[max(y - 3, 0):y + 4, max(x - 3, 0):x + 4].reshape(-1, 3).astype(np.float32); l = px @ np.array([0.11, 0.59, 0.3]); hi, lo = px[l >= np.percentile(l, 65)].mean(0), px[l <= np.percentile(l, 35)].mean(0)
    hx = lambda c: int(c[2]) << 16 | int(c[1]) << 8 | int(c[0]); wx, wz = to_w(x, y); out.append([round(wx, 1), round(wz, 1), round(rad, 2), round(rad * 1.7, 2), 0, hx(hi), hx(lo)]); cv2.circle(vis, (x, y), int(rad / mp), (0, 255, 255), 1)
col = dict(poultry=(255, 0, 255), building=(0, 0, 255), polyhouse=(255, 128, 0))
for i, s in enumerate(S):
    P = ring_px(s); cv2.polylines(vis, [P], True, col[s["kind"]], 3); cv2.putText(vis, str(i), tuple(P[0]), 0, 0.9, (255, 255, 255), 2)
cv2.polylines(vis, [cv2.findContours(inner, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0][0]], True, (255, 255, 255), 2)
cv2.imwrite("work/wide_objects.jpg", vis, [1, 82]); json.dump(S, open("work/wide_structures.json", "w")); json.dump(out, open("work/wide_trees.json", "w")); print(len(S), "structures", {k_: sum(s["kind"] == k_ for s in S) for k_ in col}, "|", len(out), "trees")
