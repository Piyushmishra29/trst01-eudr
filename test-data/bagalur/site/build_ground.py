"""Small things on the ground for the site-model page: stones, low bushes, grass and weed tufts. Read from the photos, not scattered at random.
web/ground.json rows: x*10, z*10 (world metres), size cm, kind (0 stone, 1 low bush, 2 tuft), rgb from the photo.
Source 1 = the 350 m photo (12 cm/px); source 2 = the 500 m photo (9 cm/px) where the first does not reach. Run after build_flora.py. Indicative only."""
import json, numpy as np, cv2
from PIL import Image
from build_site_geo import world_px, photo_px, DW, DH
rng = np.random.default_rng(11); Image.MAX_IMAGE_PIXELS = None
rd = lambda p: cv2.cvtColor(np.array(Image.open(p).convert("RGB")), cv2.COLOR_RGB2BGR)
FL = json.load(open("web/flora.json"))["flora"]; ST = json.load(open("web/structures.json"))["structures"]
def ring_of(s):
    if "ring" in s: return s["ring"]
    c, sn = np.cos(s["a"]), np.sin(s["a"]); return [[s["x"] + u * s["w"] / 2 * c - v * s["d"] / 2 * sn, s["z"] + u * s["w"] / 2 * sn + v * s["d"] / 2 * c] for u, v in [(-1, -1), (1, -1), (1, 1), (-1, 1)]]

def detect(img, mpp, to_px, to_world, allow, tag):
    """img BGR; to_px(x,z)->px for masking known objects; to_world(u,v)->metres; allow = 0/1 mask of where this photo is the ground the viewer shows."""
    H, W = img.shape[:2]; f = img.astype(np.float32); b, g, r = f[..., 0], f[..., 1], f[..., 2]; s = b + g + r + 1; lum = s / 3; exg = (2 * g - r - b) / s
    sat = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[..., 1].astype(np.float32); hue = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[..., 0]
    px = lambda m: m / mpp; G = lambda a, m: cv2.GaussianBlur(a, (0, 0), px(m))
    block = np.zeros((H, W), np.uint8)                                             # roofs (+1.5 m), tree and shrub crowns, water
    for t in ST: cv2.fillPoly(block, [np.int32([to_px(*p) for p in ring_of(t)])], 1)
    block = cv2.dilate(block, np.ones((int(px(3)) | 1,) * 2, np.uint8))
    crown = np.zeros((H, W), np.uint8)
    for x, z, rad, h, kind, *_ in FL:
        u, v = to_px(x, z)
        if -50 < u < W + 50 and -50 < v < H + 50: cv2.circle(crown, (int(u), int(v)), int(px(rad * (0.8 if kind == 2 else 1.0))), 1, -1)
    water = ((hue > 80) & (hue < 130) & (sat > 45)).astype(np.uint8); water = cv2.dilate(cv2.morphologyEx(water, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)), np.ones((int(px(2)) | 1,) * 2, np.uint8))
    ok = (allow > 0) & (block == 0) & (water == 0); free = ok & (crown == 0)
    rough = np.sqrt(np.maximum(G(lum * lum, 0.35) - G(lum, 0.35) ** 2, 0)); rough_w = G(rough, 1.5)
    # a track or a yard: pale, smooth, colourless ground over a few metres. Nothing grows there and stones get cleared off it
    track = (G(exg, 0.7) < 0.006) & (rough_w < 8.5) & (G(lum, 0.7) > 105); track = cv2.dilate(track.astype(np.uint8), np.ones((int(px(0.8)) | 1,) * 2, np.uint8)) > 0
    out = []; vis = img.copy()
    def peaks(score, thr, win_m):
        k = int(px(win_m)) | 1; return (score == cv2.dilate(score, np.ones((k, k), np.uint8))) & (score > thr)
    def colour(u, v, k, pick):                                                     # pick = which pixels of the patch are the object
        p = img[max(v - k, 0):v + k + 1, max(u - k, 0):u + k + 1].reshape(-1, 3).astype(np.float32); l = p.sum(1); q = p[np.argsort(l)[pick(len(l))]]; return q.mean(0)
    # ---- stones: small pale colourless specks that stand out from the soil around them
    d = G(lum, 0.16) - G(lum, 0.7); pk = peaks(d, 16, 0.9) & free & ~track & (sat < 50) & (G(lum, 0.16) > 138) & (exg < 0.02) & (G(exg, 1.0) < 0.05)
    c0 = G(lum, 0.16); k = int(round(px(0.55))); iso = np.full(lum.shape, 1e9, np.float32)                     # a stone is brighter than the ground on every side; the pale edge of a track is not
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]: iso = np.minimum(iso, c0 - np.roll(c0, (dy * k, dx * k), (0, 1)))
    pk &= iso > 9; ys, xs = np.where(pk); n = [0, 0, 0]
    for u, v in zip(xs, ys):
        size = float(np.clip(0.28 + (d[v, u] - 16) * 0.016, 0.28, 1.1)); c = colour(u, v, 2, lambda m: slice(m // 2, None)); x, z = to_world(u, v)
        out.append([round(x * 10), round(z * 10), round(size * 100), 0, int(c[2]) << 16 | int(c[1]) << 8 | int(c[0])]); n[0] += 1; cv2.circle(vis, (int(u), int(v)), 4, (255, 255, 255), 1)
    # ---- low bushes: dark green clumps about a metre across that the tree and shrub passes left alone
    d = G(lum, 0.9) - G(lum, 0.3); sc = d * (G(exg, 0.3) > 0.05) * (G(lum, 0.3) < 120) * (G(lum, 0.3) > 52); pk = peaks(sc, 7, 1.3) & free          # greener than shade: a shadow on grass is dark but dull
    ys, xs = np.where(pk)
    for u, v in zip(xs, ys):
        size = float(np.clip(0.45 + (sc[v, u] - 7) * 0.035, 0.45, 1.0)); c = colour(u, v, 3, lambda m: slice(m // 3, None)); x, z = to_world(u, v)
        out.append([round(x * 10), round(z * 10), round(size * 100), 1, int(c[2]) << 16 | int(c[1]) << 8 | int(c[0])]); n[1] += 1; cv2.circle(vis, (int(u), int(v)), int(px(size)), (0, 200, 0), 1)
        cv2.circle(crown, (int(u), int(v)), int(px(size)), 1, -1)
    # ---- tufts: rough ground with some green in it (grass, weeds, crop seedlings), one per ~1 m where the photo shows a darker, greener speck
    free = ok & (crown == 0); grassy = free & ~track & (G(exg, 0.5) > 0.018) & (rough_w > 5.5)
    sc = (G(exg, 0.12) * 400 - (G(lum, 0.12) - G(lum, 0.6))) * grassy; pk = peaks(sc, 9, 1.0)
    ys, xs = np.where(pk)
    for u, v in zip(xs, ys):
        size = float(np.clip(0.3 + sc[v, u] * 0.006 + rng.uniform(0, 0.18), 0.3, 0.75)); c = colour(u, v, 2, lambda m: slice(m // 4, None)); x, z = to_world(u, v)
        out.append([round(x * 10), round(z * 10), round(size * 100), 2, int(c[2]) << 16 | int(c[1]) << 8 | int(c[0])]); n[2] += 1; vis[v, u] = (0, 255, 255)
    cv2.imwrite(f"work/ground_{tag}.jpg", vis, [1, 82]); print(tag, "stones", n[0], "low bushes", n[1], "tufts", n[2]); return out

tex = rd("web/tex_hd.webp"); k = tex.shape[1] / DW                                  # web texture px per photo px
rows = detect(tex, 0.1228 / k, lambda x, z: [c * k for c in photo_px(x, z)], lambda u, v: world_px(u / k, v / k), np.ones(tex.shape[:2], np.uint8), "main")
WJ = json.load(open("work/wide.json")); wide = rd("work/wide_enh.png"); wa = cv2.resize(cv2.imread("web/wide_a.png", 0), wide.shape[1::-1]) > 200
kx, kz = wide.shape[1] / (WJ["x1"] - WJ["x0"]), wide.shape[0] / (WJ["z1"] - WJ["z0"])
inner = np.zeros(wide.shape[:2], np.uint8); cv2.fillPoly(inner, [np.int32([[(world_px(u, v)[0] - WJ["x0"]) * kx, (world_px(u, v)[1] - WJ["z0"]) * kz] for u, v in [(0, 0), (DW, 0), (DW, DH), (0, DH)]])], 1)
inner = cv2.erode(inner, np.ones((int(6 * kx) | 1,) * 2, np.uint8))                 # the main photo fades out over its last metres
rows += detect(wide, 1 / kx, lambda x, z: [(x - WJ["x0"]) * kx, (z - WJ["z0"]) * kz], lambda u, v: [WJ["x0"] + u / kx, WJ["z0"] + v / kz], (wa & (inner == 0)).astype(np.uint8), "wide")
json.dump(dict(ground=rows), open("web/ground.json", "w"), separators=(",", ":")); print(len(rows), "rows")
