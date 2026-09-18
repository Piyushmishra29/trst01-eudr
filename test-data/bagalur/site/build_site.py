"""Data + textures for the site-model page (web/): parcels in the viewer's world metres, points of interest, and the dehazed photo at three sizes."""
import json, numpy as np, cv2
from PIL import Image
def webp(path, bgr, q): Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).save(path, "WEBP", quality=q, method=6)
def poly(ring):                                           # area, perimeter, and a label point inside the shape (centroid, else the roomiest grid point) - same rule as the page's editor
    r = np.array(ring[:-1] if ring[0] == ring[-1] else ring, float); x, z = r[:, 0], r[:, 1]; x2, z2 = np.roll(x, -1), np.roll(z, -1); k = x * z2 - x2 * z; a2 = k.sum()
    at = [((x + x2) * k).sum() / (3 * a2), ((z + z2) * k).sum() / (3 * a2)]; c = np.float32(r)
    if cv2.pointPolygonTest(c, (float(at[0]), float(at[1])), False) < 0:
        at = max(((gx, gz) for gx in np.linspace(x.min(), x.max(), 18)[1:-1] for gz in np.linspace(z.min(), z.max(), 18)[1:-1]), key=lambda q: cv2.pointPolygonTest(c, (float(q[0]), float(q[1])), True))
    return abs(a2) / 2, float(np.hypot(x2 - x, z2 - z).sum()), at
from build_site_geo import *
parcels = []
import os; SRC = "../plots/bagalur_parcels_edited.geojson" if os.path.exists("../plots/bagalur_parcels_edited.geojson") else "../plots/bagalur_whole_plot.eudr.geojson"   # boundaries edited in the page (pull_edits.py) win
for i, f in enumerate(json.load(open(SRC))["features"]):
    ring = [world_ll(*c[:2]) for c in f["geometry"]["coordinates"][0]]; ar, pe, c = poly(ring)
    parcels.append(dict(id=f["properties"].get("id") or f"{i + 1:02d}", ring=ring, m2=round(ar), perim=round(pe), at=[round(float(c[0]), 1), round(float(c[1]), 1)]))
# ---------- focus: everything outside the parcels is dimmed and greyed a little, baked into the images (soft 8 m edge), so the eye goes to the estate
def focus(img, to_px, m_per_px, dim=0.6, sat=0.55):
    mask = np.zeros(img.shape[:2], np.uint8)
    for p in parcels: cv2.fillPoly(mask, [np.int32([to_px(*q) for q in p["ring"]])], 255)
    m = cv2.GaussianBlur(mask.astype(np.float32) / 255, (0, 0), max(1.0, 8 / m_per_px / 2))[..., None]; f = img.astype(np.float32); g = f.mean(2, keepdims=True)
    return np.clip(f * m + ((g + (f - g) * sat) * dim + 14) * (1 - m), 0, 255).astype(np.uint8)
pois = [dict(name=n, at=world_px(u, v)) for n, u, v in [("Polyhouses", 1600, 2760), ("Packing sheds", 660, 1280), ("Farm pond", 1030, 1760), ("Mango orchard", 3400, 520), ("Areca plantation", 1600, 690), ("Solar roof", 3250, 2680)]]
pois += [dict(name="Staff quarters", at=[-15.0, -52.0]), dict(name="Poultry sheds", at=[200.0, -8.0]), dict(name="Poultry sheds", at=[392.0, -83.0])]      # named by Piyush; world metres
json.dump(dict(parcels=parcels, pois=pois, surveyed_m2=round(poly([world_px(*q) for q in [(0, 0), (DW, 0), (DW, DH), (0, DH)]])[0])), open("web/site.json", "w"), separators=(",", ":"))
print(len(parcels), "parcels", sum(p["m2"] for p in parcels) / 1e4, "ha")
im = cv2.imread("../cesium/work/DJI_0995_enh.png")                                  # enhance.py output (8064 x 6048)
im = (np.clip((im.astype(np.float32) / 255) ** 0.8 * 0.94 + 0.05, 0, 1) * 255).astype(np.uint8)      # open the shadows a little: the 3D scene adds its own shading on top

# ---------- land colour: the dehazed dry-season photo reads grey-violet. Grey land is eased to what it is: dark scrub towards green, light bare ground towards warm brown.
# Already colourful pixels (red soil, crops, water) keep their hue and gain a little saturation; roofs are masked out so sheets and concrete stay neutral.
def grade(bgr, keep=None, k=1.0):
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32); L, a, b = lab[..., 0], lab[..., 1] - 128, lab[..., 2] - 128; ch = np.hypot(a, b)
    grey = np.clip(1 - ch / 24, 0, 1) * np.clip((230 - L) / 40, 0, 1)                       # how grey (and not a white surface) the pixel is
    dark = np.clip((125 - L) / 45, 0, 1); w = grey * k                                       # dark grey = scrub and canopy shade, light grey = bare ground and tracks
    ta = -13 * dark + 5 * (1 - dark); tb = 17 * dark + 15 * (1 - dark)                      # target tint: leaf green / warm earth
    vib = 1 + 0.42 * k * np.clip(1 - ch / 45, 0, 1); a2 = a * vib + (ta - a) * w * 0.9; b2 = b * vib + (tb - b) * w * 0.9
    cool = (b < -4) & (a < 6)                                                                # water and blue sheets: leave alone
    a2 = np.where(cool, a, a2); b2 = np.where(cool, b, b2)
    purple = np.clip((a - 1) / 5, 0, 1) * np.clip((5 - b) / 8, 0, 1) * np.clip((120 - L) / 40, 0, 1)      # dehazing leaves shadows violet: dark violet goes to a plain, slightly warm dark
    a2 = a2 * (1 - purple) + 0.5 * purple; b2 = b2 * (1 - purple) + 5 * purple
    out = cv2.cvtColor(np.clip(np.dstack([L, a2 + 128, b2 + 128]), 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
    if keep is not None: m = cv2.GaussianBlur(keep.astype(np.float32), (0, 0), 3)[..., None]; out = (out * (1 - m) + bgr * m).astype(np.uint8)
    return out
roofs = np.zeros(im.shape[:2], np.uint8)
for b_ in json.load(open("../ai3d/web/buildings.json"))["buildings"]: cv2.fillPoly(roofs, [np.int32(np.array(b_["poly"]) * im.shape[1] / DW)], 1)
cv2.imwrite("work/grade_before.jpg", cv2.resize(im, (2016, 1512)), [1, 85]); im = grade(im, cv2.dilate(roofs, np.ones((9, 9), np.uint8))); cv2.imwrite("work/grade_after.jpg", cv2.resize(im, (2016, 1512)), [1, 85])

# ---------- seamless edge: the satellite is another day, season and camera, so the surveyed rectangle reads as a box unless the colours meet
sat = cv2.imread("../ai3d/web/sat_hd.jpg"); k = sat.shape[1] / SW                       # satellite block, maybe stored smaller than its nominal grid
w, h = 1008, 756; uu, vv = np.meshgrid(np.linspace(0, DW, w), np.linspace(0, DH, h)); fx, fy = uu / DW * (GX - 1), vv / DH * (GY - 1)
dmap = cv2.remap(D.astype(np.float32), fx.astype(np.float32), fy.astype(np.float32), cv2.INTER_LINEAR)
mx = ((A[0, 0] * uu + A[0, 1] * vv + A[0, 2] + dmap[..., 0]) * k).astype(np.float32); my = ((A[1, 0] * uu + A[1, 1] * vv + A[1, 2] + dmap[..., 1]) * k).astype(np.float32)
sat_d = cv2.remap(sat, mx, my, cv2.INTER_LINEAR)                                       # the satellite seen through the drone photo's pixel grid
dr = cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA); lab = lambda x: cv2.cvtColor(x, cv2.COLOR_BGR2LAB).astype(np.float32)
# 1. whole satellite block takes the drone photo's overall tone (Lab mean and spread over the shared ground)
ls, ld = lab(sat_d).reshape(-1, 3), lab(dr).reshape(-1, 3); gain = ld.std(0) / ls.std(0); gain = np.clip(gain, 0.8, 1.22)
def tone(x):                                             # 80% of the way: a full match over-cooks fields the drone never saw
    m = cv2.cvtColor(np.clip((lab(x) - ls.mean(0)) * gain + ld.mean(0) - np.array([6, 0, 0]), 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR); return grade(cv2.addWeighted(m, 0.8, x, 0.2, 0), k=0.8)
sat_m = focus(tone(sat), lambda x, z: (x / PX + SW / 2, z / PX + SH / 2), PX); webp("web/sat_hd.webp", sat_m, 80); webp("web/sat_sd.webp", cv2.resize(sat_m, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA), 78)
# 2. near the border the drone photo's broad colour (not its detail) eases into the satellite's, so fields carry across the edge
blur = lambda x, s: cv2.GaussianBlur(x.astype(np.float32), (0, 0), s); diff = blur(tone(sat_d), 22) - blur(dr, 22)
edge = np.minimum.reduce([uu / DW, 1 - uu / DW, (vv / DH) * 0.75, (1 - vv / DH) * 0.75]) * DW * 0.1228                 # metres to the nearest photo edge
wgt = np.clip(1 - edge / 70, 0, 1) ** 1.5; corr = diff * wgt[..., None]
for tag, W_, q_ in (("uhd", 6720, 80), ("hd", 4032, 82), ("sd", 2016, 80)):
    t = cv2.resize(im, (W_, W_ * 3 // 4), interpolation=cv2.INTER_AREA).astype(np.float32) + cv2.resize(corr, (W_, W_ * 3 // 4), interpolation=cv2.INTER_CUBIC)
    webp(f"web/tex_{tag}.webp", focus(np.clip(t, 0, 255).astype(np.uint8), lambda x, z, k_=W_ / DW: tuple(c * k_ for c in photo_px(x, z)), 0.1228 * DW / W_), q_)
print("sat tone gain", gain.round(2), "edge blend up to 70 m")

# ---------- wide context (fetch_context.py): same tone as the inner block, so the land carries on to the horizon
ctx = cv2.imread("work/context.tif")
if ctx is not None:
    inner = cv2.resize(sat, (500, 375), interpolation=cv2.INTER_AREA); c0 = ctx[2000 - 187:2000 + 188, 2000 - 250:2000 + 250]        # the inner block's place in the 4 m grid
    a_, b_ = lab(c0).reshape(-1, 3), lab(inner).reshape(-1, 3); ctx_l = (lab(ctx) - a_.mean(0)) * np.clip(b_.std(0) / a_.std(0), 0.8, 1.25) + b_.mean(0)      # first onto the inner block's own tone (different tile dates)
    webp("web/context.webp", focus(cv2.resize(tone(cv2.cvtColor(np.clip(ctx_l, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)), (3072, 3072), interpolation=cv2.INTER_AREA), lambda x, z: ((x + 8000) / 16000 * 3072, (z + 8000) / 16000 * 3072), 16000 / 3072), 72); print("context written")

# ---------- wide drone layer (make_wide.py): the 500 m photo, 8.7 cm/px, under the 350 m photo and over the satellite. Same tone as the main photo, same land colour, same focus.
import os
if os.path.exists("work/wide_enh.png"):
    WJ = json.load(open("work/wide.json")); wide = cv2.imread("work/wide_enh.png"); valid = cv2.imread("work/wide_valid.png", 0)
    wide = (np.clip((wide.astype(np.float32) / 255) ** 0.8 * 0.94 + 0.05, 0, 1) * 255).astype(np.uint8); hW, wW = wide.shape[:2]; mp = WJ["m_per_px"]
    gs = 40; gx, gz = np.meshgrid(np.arange(gs // 2, wW, gs), np.arange(gs // 2, hW, gs)); pa, pb = [], []                                   # tone: where both photos see the same ground, the wide one takes the main one's Lab mean and spread
    small_w = cv2.blur(wide, (gs, gs)); small_d = cv2.blur(cv2.resize(im, (DW, DH), interpolation=cv2.INTER_AREA), (24, 24))
    for x, z in zip(gx.ravel(), gz.ravel()):
        if valid[z, x] < 255: continue
        u, v = photo_px(WJ["x0"] + x * mp, WJ["z0"] + z * mp)
        if 40 < u < DW - 40 and 40 < v < DH - 40: pa.append(small_w[z, x]); pb.append(small_d[int(v), int(u)])
    la, lb = lab(np.uint8([pa]))[0], lab(np.uint8([pb]))[0]; g2 = np.clip(lb.std(0) / la.std(0), 0.85, 1.25); print("wide layer: overlap samples", len(pa), "gain", g2.round(2))
    wide = cv2.cvtColor(np.clip((lab(wide) - la.mean(0)) * g2 + lb.mean(0), 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
    wide = grade(wide, k=1.0)      # `im` was graded before it was sampled above, so the match already carries most of the colour; this evens out what the match cannot
    to_px = lambda x, z, k_=1.0: ((x - WJ["x0"]) / mp * k_, (z - WJ["z0"]) / mp * k_)
    for tag, W_, q_ in (("hd", 6144, 80), ("sd", 3072, 78)):
        k_ = W_ / wW; webp(f"web/wide_{tag}.webp", focus(cv2.resize(wide, (W_, round(hW * k_)), interpolation=cv2.INTER_AREA), lambda x, z, k_=k_: to_px(x, z, k_), mp / k_), q_)
    a_ = cv2.resize(valid, (1024, round(hW * 1024 / wW)), interpolation=cv2.INTER_AREA); a_ = (a_ == 255).astype(np.uint8); kpx = 1024 / (wW * mp)       # soft 35 m edge into the satellite
    a_[[0, -1], :] = 0; a_[:, [0, -1]] = 0; dt = cv2.distanceTransform(a_, cv2.DIST_L2, 5) / kpx; cv2.imwrite("web/wide_a.png", (np.clip((dt - 4) / 35, 0, 1) ** 1.3 * 255).astype(np.uint8))
    json.dump(dict(x0=WJ["x0"], z0=WJ["z0"], x1=WJ["x1"], z1=WJ["z1"]), open("web/wide.json", "w")); print("wide layer written")
