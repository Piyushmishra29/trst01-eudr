"""Planting + structures for the site-model page, all in the viewer's world metres.
web/flora.json      every tree the AI found (with its own two leaf colours from the photo), shrubs filling the scrub inside the survey,
                    and trees spotted on the satellite land around it. Rows: x, z, crown radius m, height m, kind, light rgb, dark rgb
                    kind 0 tree, 1 palm, 2 shrub, 3 tree on the satellite land
web/structures.json the AI roof outlines squared up into rectangles (L-shapes become two), so walls are straight and corners crisp.
Everything here is indicative: positions come from one photo, heights from AI depth."""
import json, numpy as np, cv2
from PIL import Image
from build_site_geo import world_px, photo_px, DW, DH, SW, SH, PX
rng = np.random.default_rng(7); MPP = 0.1228                                   # metres per drone px at 4032
rd = lambda p: cv2.cvtColor(np.array(Image.open(p).convert("RGB")), cv2.COLOR_RGB2BGR)
tex = rd("web/tex_hd.webp"); sat = rd("web/sat_hd.webp")                       # the images the viewer shows: colours sampled here match the ground
TREES = json.load(open("../ai3d/web/trees.json"))["trees"]; BLD = json.load(open("../ai3d/web/buildings.json"))["buildings"]
hexc = lambda bgr: int(bgr[2]) << 16 | int(bgr[1]) << 8 | int(bgr[0])
def two_tones(px):                                                             # sunlit and shaded leaf colour of one crown
    if len(px) < 8: return None
    l = px.astype(np.float32) @ np.array([0.11, 0.59, 0.3]); hi, lo = px[l >= np.percentile(l, 65)].mean(0), px[l <= np.percentile(l, 35)].mean(0); return hexc(hi), hexc(lo)

# ---------- structures
def largest_rect(m):                                                           # largest all-ones rectangle in a 0/1 grid (histogram stack)
    h = np.zeros(m.shape[1], int); best = (0, 0, 0, 0, 0)
    for y in range(m.shape[0]):
        h = np.where(m[y] > 0, h + 1, 0); st = []
        for x in range(len(h) + 1):
            cur = h[x] if x < len(h) else 0; start = x
            while st and st[-1][1] >= cur:
                s, hh = st.pop(); a = hh * (x - s)
                if a > best[0]: best = (a, s, y - hh + 1, x - s, hh)
                start = s
            st.append((start, cur))
    return best
structures = []; C = 0.25
for bi, b in enumerate(BLD):
    Wd = np.array([world_px(u, v) for u, v in b["poly"]], np.float32); (cx, cz), (w, d), ang = cv2.minAreaRect(Wd); a = np.deg2rad(ang)
    ex, ez = np.array([np.cos(a), np.sin(a)]), np.array([-np.sin(a), np.cos(a)]); L = (Wd - [cx, cz]) @ np.stack([ex, ez]).T
    gw, gd = int(np.ceil(w / C)) + 2, int(np.ceil(d / C)) + 2; m = np.zeros((gd, gw), np.uint8); cv2.fillPoly(m, [np.int32((L + [w / 2, d / 2]) / C + 1)], 1)
    h = 4.2 if b["area_m2"] > 1500 else float(np.clip(2.7 + 5.5 * b["h"], 2.8, 7.5)); parts = []
    fill = m.sum() * C * C / (w * d)
    if fill > 0.8: k = min(1.0, fill ** 0.5 * 1.02); parts = [(0.0, 0.0, w * k, d * k)]                # same area as the outline: the bounding box of a wobbly outline overshoots the roof
    else:                                                                       # not a rectangle (two wings, a bend): keep the outline, straightened to a few clean edges
        ring = cv2.approxPolyDP(Wd.reshape(-1, 1, 2), 1.3, True).reshape(-1, 2)
        if len(ring) >= 3: structures.append(dict(ring=[[round(float(q[0]), 2), round(float(q[1]), 2)] for q in ring], h=round(h, 2), roof="flat", g=bi, big=int(b["area_m2"] > 1500))); print("  outline kept:", bi, b["area_m2"], "m2, fill", round(float(fill), 2), len(ring), "edges")
    for lx, lz, pw, pd in parts:
        c = np.array([cx, cz]) + ex * lx + ez * lz
        structures.append(dict(x=round(float(c[0]), 2), z=round(float(c[1]), 2), w=round(float(pw), 2), d=round(float(pd), 2), a=round(float(a), 4), h=round(h, 2), roof=b["roof"] if min(pw, pd) < 32 else "flat", g=bi, big=int(b["area_m2"] > 1500)))
# ---------- what only the 500 m photo sees (build_wide_objects.py): full-length poultry sheds, tunnels, greenhouses. A shed the main photo cuts off at its edge is replaced by the full one.
import os
if os.path.exists("work/wide_structures.json"):
    WS = json.load(open("work/wide_structures.json")); inside = lambda s, x, z, pad: abs((x - s["x"]) * np.cos(s["a"]) + (z - s["z"]) * np.sin(s["a"])) < s["w"] / 2 + pad and abs(-(x - s["x"]) * np.sin(s["a"]) + (z - s["z"]) * np.cos(s["a"])) < s["d"] / 2 + pad
    cen = lambda s: (s["x"], s["z"]) if "x" in s else tuple(np.mean(s["ring"], 0)); n0 = len(structures)
    structures = [s for s in structures if not any(w_["kind"] == "poultry" and inside(w_, *cen(s), 3) for w_ in WS)]; print(n0 - len(structures), "clipped sheds replaced by their full-length version;", len(WS), "structures added from the 500 m photo")
    structures += [dict(s, g=100 + i) for i, s in enumerate(WS)]
def ring_of(s):
    if "ring" in s: return s["ring"]
    c_, s_ = np.cos(s["a"]), np.sin(s["a"]); return [[s["x"] + c_ * i * s["w"] / 2 - s_ * j * s["d"] / 2, s["z"] + s_ * i * s["w"] / 2 + c_ * j * s["d"] / 2] for i, j in [(-1, -1), (1, -1), (1, 1), (-1, 1)]]
# where a tree hangs over a roof the photo would paint leaves onto the 3D roof: inside each roof outline, leaf and deep-shade pixels take the roof's own colour (skylights and panels stay)
def clean_roofs(img, k):                                                        # k = px per 4032-px
    n = 0
    for s in structures:
        if s.get("src") == "wide": continue
        pts = np.int32([[c * k for c in photo_px(*q)] for q in ring_of(s)]); x0, y0 = np.maximum(pts.min(0) - 4, 0); x1, y1 = pts.max(0) + 4
        roi = img[y0:y1, x0:x1]; mk = np.zeros(roi.shape[:2], np.uint8); cv2.fillPoly(mk, [pts - [x0, y0]], 1)
        if mk.sum() < 30: continue
        f = roi.astype(np.float32); lum = f.mean(2); exg = (2 * f[..., 1] - f[..., 0] - f[..., 2]) / (f.sum(2) + 1); clean = (mk > 0) & (exg < 0.02)
        if clean.sum() < 20: continue
        med = np.median(f[clean], 0); leaf = ((exg > 0.035) & (mk > 0)).astype(np.uint8); kn = int(44 * k) | 1; near = cv2.dilate(cv2.morphologyEx(leaf, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)), np.ones((kn, kn), np.uint8)) > 0      # deep shade counts only right next to leaves: solar panels and dark sheets stay
        bad = ((leaf > 0) | ((lum < 0.8 * med.mean()) & near)) & (mk > 0); frac = bad.sum() / mk.sum()
        if frac < 0.03 or frac > 0.7: continue
        bad = cv2.dilate(bad.astype(np.uint8), np.ones((5, 5), np.uint8)) * mk; a_ = cv2.GaussianBlur(bad.astype(np.float32), (0, 0), 1.5)[..., None]
        roi[:] = np.clip(f * (1 - a_) + (med + rng.normal(0, 2.5, roi.shape[:2] + (1,))) * a_, 0, 255).astype(np.uint8); n += 1
    return n
for tag, q in (("uhd", 80), ("hd", 82), ("sd", 80)):
    t = rd(f"web/tex_{tag}.webp"); n = clean_roofs(t, t.shape[1] / DW)
    if n: Image.fromarray(cv2.cvtColor(t, cv2.COLOR_BGR2RGB)).save(f"web/tex_{tag}.webp", "WEBP", quality=q, method=6)      # a second run finds nothing left to clean and leaves the files alone
print(n, "roofs cleaned of overhanging leaves"); cv2.imwrite("work/roofs_clean.jpg", t[500:850, 150:650])
json.dump(dict(structures=structures), open("web/structures.json", "w"), separators=(",", ":")); print(len(BLD), "outlines ->", len(structures), "blocks")

# ---------- trees the AI found, each with its own leaf colours
flora = []; H4, W4 = tex.shape[:2]
crown = np.zeros((H4 // 4, W4 // 4), np.uint8)
for cx, cy, rx, ry, ht, palm in TREES:
    x0, x1, y0, y1 = int(max(cx - rx, 0)), int(min(cx + rx + 1, W4)), int(max(cy - ry, 0)), int(min(cy + ry + 1, H4)); ys, xs = np.mgrid[y0:y1, x0:x1]
    q = ((xs - cx) / (rx * 0.75)) ** 2 + ((ys - cy) / (ry * 0.75)) ** 2 < 1; tt = two_tones(tex[y0:y1, x0:x1][q])
    if tt is None: continue
    r = (rx + ry) / 2 * MPP; x, z = world_px(cx, cy); flora.append([x, z, round(r, 2), round(max(ht * 10, 1.5 * r) if not palm else max(ht * 16, 2.2 * r), 2), int(palm), *tt])
    cv2.ellipse(crown, (int(cx / 4), int(cy / 4)), (int(rx / 4 + 3), int(ry / 4 + 3)), 0, 0, 360, 1, -1)
n_ai = len(flora)

# ---------- small trees the detector skipped (orchard rows, young plantation): dark round blobs 2-5 m across, away from crowns already found
md = cv2.resize(tex, (W4 // 2, H4 // 2), interpolation=cv2.INTER_AREA); lm = cv2.cvtColor(md, cv2.COLOR_BGR2GRAY).astype(np.float32)
dog = cv2.GaussianBlur(lm, (0, 0), 7) - cv2.GaussianBlur(lm, (0, 0), 2.4); ring = cv2.GaussianBlur(lm, (0, 0), 2.4)
pk = (dog == cv2.dilate(dog, np.ones((11, 11), np.uint8))) & (dog > 7.5) & (ring < 100)
pk &= cv2.resize(cv2.dilate(crown, np.ones((5, 5), np.uint8)), (W4 // 2, H4 // 2), interpolation=cv2.INTER_NEAREST) == 0
bm2 = np.zeros(lm.shape, np.uint8)
for b in BLD: cv2.fillPoly(bm2, [np.int32(np.array(b["poly"]) / 2)], 1)
pk &= cv2.dilate(bm2, np.ones((41, 41), np.uint8)) == 0                          # building shadows are dark blobs too
hsv = cv2.cvtColor(md, cv2.COLOR_BGR2HSV); water = (hsv[..., 0] > 80) & (hsv[..., 0] < 130) & (hsv[..., 1] > 40); pk &= cv2.dilate(water.astype(np.uint8), np.ones((25, 25), np.uint8)) == 0
ys, xs = np.where(pk); n_or = 0; vis = md.copy()
for x, y in zip(xs, ys):
    r = float(np.clip(1.0 + (dog[y, x] - 7.5) * 0.05, 1.0, 2.4)); k = int(r / (MPP * 2)); px = md[max(y - k, 0):y + k + 1, max(x - k, 0):x + k + 1].reshape(-1, 3); tt = two_tones(px)
    wx, wz = world_px(x * 2, y * 2); flora.append([wx, wz, round(r, 2), round(r * float(rng.uniform(1.35, 1.8)), 2), 0, *tt]); n_or += 1
    cv2.circle(vis, (int(x), int(y)), int(r / (MPP * 2)), (0, 255, 255), 1); cv2.circle(crown, (int(x // 2), int(y // 2)), int(r / (MPP * 4)) + 2, 1, -1)
cv2.imwrite("work/orchard_trees.jpg", vis, [1, 80])

# ---------- shrubs: green, rough-textured ground the crowns do not already cover (scrub, hedges, field edges). Smooth green = crop, left alone.
sm = cv2.resize(tex, (W4 // 4, H4 // 4), interpolation=cv2.INTER_AREA).astype(np.float32); bb, gg, rr = sm[..., 0], sm[..., 1], sm[..., 2]; s = bb + gg + rr + 1
exg = (2 * gg - rr - bb) / s; lum = s / 3; rough = np.sqrt(np.maximum(cv2.GaussianBlur(lum * lum, (0, 0), 2.5) - cv2.GaussianBlur(lum, (0, 0), 2.5) ** 2, 0))
veg = (exg > 0.035) & (lum < 125) & (rough > 9) & (crown == 0)
bm = np.zeros_like(crown)
for b in BLD: cv2.fillPoly(bm, [np.int32(np.array(b["poly"]) / 4)], 1)
veg &= cv2.dilate(bm, np.ones((9, 9), np.uint8)) == 0
veg = cv2.morphologyEx(veg.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
dark = lum < cv2.GaussianBlur(lum, (0, 0), 6) - 4                                 # a shrub reads as a dark clump against its surroundings
ys, xs = np.where((veg > 0) & dark); order = rng.permutation(len(xs)); cell = 5; taken = {}; n_sh = 0          # ~2.4 m apart at 0.49 m/px
for i in order:
    x, y = xs[i], ys[i]; k = (x // cell, y // cell)
    if any((k[0] + dx, k[1] + dy) in taken for dx in (-1, 0, 1) for dy in (-1, 0, 1)): continue
    taken[k] = 1; r = float(rng.uniform(0.9, 1.9)); px = sm[max(y - 2, 0):y + 3, max(x - 2, 0):x + 3].reshape(-1, 3); tt = two_tones(px.astype(np.uint8))
    wx, wz = world_px(x * 4, y * 4); flora.append([wx, wz, round(r, 2), round(r * float(rng.uniform(1.1, 1.6)), 2), 2, *tt]); n_sh += 1
    if n_sh >= 4500: break
cv2.imwrite("work/shrub_mask.jpg", cv2.addWeighted(sm.astype(np.uint8), 0.6, cv2.merge([veg * 0, veg * 255, veg * 0]), 0.4, 0))

# ---------- trees on the satellite land (0.5 m/px): dark green blobs a few metres across
f = sat.astype(np.float32); bb, gg, rr = f[..., 0], f[..., 1], f[..., 2]; s = bb + gg + rr + 1; lum = s / 3; exg = (2 * gg - rr - bb) / s
dog = cv2.GaussianBlur(lum, (0, 0), 9) - cv2.GaussianBlur(lum, (0, 0), 3)             # positive where a ~6-10 m blob is darker than its surroundings
score = dog * (exg > 0.0) * (lum < 120); pk = (score == cv2.dilate(score, np.ones((13, 13), np.uint8))) & (score > 7)
inside = np.zeros(sat.shape[:2], np.uint8); cv2.fillPoly(inside, [np.int32([[c / PX + SW / 2 for c in world_px(u, v)] for u, v in [(0, 0), (DW, 0), (DW, DH), (0, DH)]])], 1)
pk &= inside == 0; ys, xs = np.where(pk); n_out = 0
for x, y in zip(xs, ys):
    r = float(np.clip(2.2 + (score[y, x] - 7) * 0.16, 2.2, 5.5)); px = sat[max(y - 4, 0):y + 5, max(x - 4, 0):x + 5].reshape(-1, 3); tt = two_tones(px)
    flora.append([round((x - SW / 2) * PX, 1), round((y - SH / 2) * PX, 1), round(r, 2), round(r * float(rng.uniform(1.5, 2.1)), 2), 3, *tt]); n_out += 1
if os.path.exists("work/wide_trees.json"):                                                  # where the 500 m photo covers the ground its trees replace the satellite guesses
    WJ = json.load(open("work/wide.json")); va = cv2.imread("web/wide_a.png", 0); kx, kz = va.shape[1] / (WJ["x1"] - WJ["x0"]), va.shape[0] / (WJ["z1"] - WJ["z0"])
    def covered(x, z): i, j = int((x - WJ["x0"]) * kx), int((z - WJ["z0"]) * kz); return 0 <= i < va.shape[1] and 0 <= j < va.shape[0] and va[j, i] > 128
    n0 = len(flora); flora = [t for t in flora if not (t[4] == 3 and covered(t[0], t[1]))]; wt = [t for t in json.load(open("work/wide_trees.json")) if covered(t[0], t[1])]; flora += wt; print(n0 - len(flora) + len(wt), "satellite trees replaced by", len(wt), "trees from the 500 m photo")
vis = sat.copy()
for x, y in zip(xs, ys): cv2.circle(vis, (int(x), int(y)), 6, (0, 255, 255), 1)
cv2.imwrite("work/sat_trees.jpg", cv2.resize(vis, None, fx=0.5, fy=0.5), [1, 80])
foot = [np.float32(ring_of(s)) for s in structures]; keep = [f for f in flora if f[4] == 3 or not any(cv2.pointPolygonTest(g, (float(f[0]), float(f[1])), True) > -max(1.0, 0.45 * f[2]) for g in foot)]; print(len(flora) - len(keep), "stems inside buildings dropped"); flora = keep
json.dump(dict(flora=flora), open("web/flora.json", "w"), separators=(",", ":")); print(n_ai, "AI crowns +", n_or, "small trees +", n_sh, "shrubs +", n_out, "satellite trees")
