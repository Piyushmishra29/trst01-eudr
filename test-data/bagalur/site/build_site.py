"""Data + textures for the site-model page (web/): parcels in the viewer's world metres, points of interest, and the dehazed photo at three sizes."""
import json, numpy as np, cv2
from PIL import Image
def webp(path, bgr, q): Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).save(path, "WEBP", quality=q, method=6)
from shapely.geometry import Polygon
from build_site_geo import *
parcels = []
for i, f in enumerate(json.load(open("../plots/bagalur_whole_plot.eudr.geojson"))["features"]):
    ring = [world_ll(*c[:2]) for c in f["geometry"]["coordinates"][0]]; p = Polygon(ring); c = p.representative_point()
    parcels.append(dict(id=f"{i + 1:02d}", ring=ring, m2=round(p.area), perim=round(p.length), at=[round(c.x, 1), round(c.y, 1)]))
# ---------- focus: everything outside the parcels is dimmed and greyed a little, baked into the images (soft 8 m edge), so the eye goes to the estate
def focus(img, to_px, m_per_px, dim=0.6, sat=0.55):
    mask = np.zeros(img.shape[:2], np.uint8)
    for p in parcels: cv2.fillPoly(mask, [np.int32([to_px(*q) for q in p["ring"]])], 255)
    m = cv2.GaussianBlur(mask.astype(np.float32) / 255, (0, 0), max(1.0, 8 / m_per_px / 2))[..., None]; f = img.astype(np.float32); g = f.mean(2, keepdims=True)
    return np.clip(f * m + ((g + (f - g) * sat) * dim + 14) * (1 - m), 0, 255).astype(np.uint8)
pois = [dict(name=n, at=world_px(u, v)) for n, u, v in [("Polyhouses", 1600, 2760), ("Packing sheds", 660, 1280), ("Farm pond", 1030, 1760), ("Mango orchard", 3400, 520), ("Areca plantation", 1600, 690), ("Solar roof", 3250, 2680)]]
json.dump(dict(parcels=parcels, pois=pois, surveyed_m2=round(Polygon([world_px(*q) for q in [(0, 0), (DW, 0), (DW, DH), (0, DH)]]).area)), open("web/site.json", "w"), separators=(",", ":"))
print(len(parcels), "parcels", sum(p["m2"] for p in parcels) / 1e4, "ha")
im = cv2.imread("../cesium/work/DJI_0995_enh.png")                                  # enhance.py output (8064 x 6048)
im = (np.clip((im.astype(np.float32) / 255) ** 0.8 * 0.94 + 0.05, 0, 1) * 255).astype(np.uint8)      # open the shadows a little: the 3D scene adds its own shading on top

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
    m = cv2.cvtColor(np.clip((lab(x) - ls.mean(0)) * gain + ld.mean(0) - np.array([6, 0, 0]), 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR); return cv2.addWeighted(m, 0.8, x, 0.2, 0)
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
