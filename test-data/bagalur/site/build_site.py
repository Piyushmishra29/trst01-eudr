"""Data + textures for the site-model page (web/): parcels in the viewer's world metres, points of interest, and the dehazed photo at three sizes."""
import json, numpy as np, cv2
from pyproj import Transformer
from shapely.geometry import Polygon
AL = json.load(open("../ai3d/web/align.json")); S = json.load(open("../ai3d/web/seam.json")); A = np.array(AL["A"]); D = np.array(S["d"], float); GX, GY = S["gx"], S["gy"]
SW, SH = AL["sat_size"]; PX = AL["sat_px_m"]; DW, DH = AL["drone_size"]; X0, Y1 = 808152.0, 1418908.0                 # satellite block: UTM 43N top-left corner
T = Transformer.from_crs(4326, 32643, always_xy=True)
def world_ll(lon, lat): x, y = T.transform(lon, lat); return [round((x - X0) - SW * PX / 2, 2), round((Y1 - y) - SH * PX / 2, 2)]      # x east, z south, origin = block centre
def world_px(u, v):
    fx, fy = min(max(u / DW * (GX - 1), 0), GX - 1.001), min(max(v / DH * (GY - 1), 0), GY - 1.001); ix, iy = int(fx), int(fy); tx, ty = fx - ix, fy - iy
    d = (D[iy, ix] * (1 - tx) + D[iy, ix + 1] * tx) * (1 - ty) + (D[iy + 1, ix] * (1 - tx) + D[iy + 1, ix + 1] * tx) * ty
    X = A[0, 0] * u + A[0, 1] * v + A[0, 2] + d[0]; Y = A[1, 0] * u + A[1, 1] * v + A[1, 2] + d[1]; return [round((X - SW / 2) * PX, 2), round((Y - SH / 2) * PX, 2)]
parcels = []
for i, f in enumerate(json.load(open("../plots/bagalur_whole_plot.eudr.geojson"))["features"]):
    ring = [world_ll(*c[:2]) for c in f["geometry"]["coordinates"][0]]; p = Polygon(ring); c = p.representative_point()
    parcels.append(dict(id=f"{i + 1:02d}", ring=ring, m2=round(p.area), perim=round(p.length), at=[round(c.x, 1), round(c.y, 1)]))
pois = [dict(name=n, at=world_px(u, v)) for n, u, v in [("Polyhouses", 1600, 2760), ("Packing sheds", 660, 1280), ("Farm pond", 1030, 1760), ("Mango orchard", 3400, 520), ("Areca plantation", 1600, 690), ("Solar roof", 3250, 2680)]]
json.dump(dict(parcels=parcels, pois=pois, surveyed_m2=round(Polygon([world_px(*q) for q in [(0, 0), (DW, 0), (DW, DH), (0, DH)]]).area)), open("web/site.json", "w"), separators=(",", ":"))
print(len(parcels), "parcels", sum(p["m2"] for p in parcels) / 1e4, "ha")
im = cv2.imread("../cesium/work/DJI_0995_enh.png")                                  # enhance.py output (8064 x 6048)
im = (np.clip((im.astype(np.float32) / 255) ** 0.8 * 0.94 + 0.05, 0, 1) * 255).astype(np.uint8)      # open the shadows a little: the 3D scene adds its own shading on top
for tag, w, q in (("uhd", 6720, 86), ("hd", 4032, 88), ("sd", 2016, 86)): cv2.imwrite(f"web/tex_{tag}.jpg", cv2.resize(im, (w, w * 3 // 4), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, q])

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
sat_m = tone(sat); cv2.imwrite("web/sat_hd.jpg", sat_m, [cv2.IMWRITE_JPEG_QUALITY, 88]); cv2.imwrite("web/sat_sd.jpg", cv2.resize(sat_m, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 86])
# 2. near the border the drone photo's broad colour (not its detail) eases into the satellite's, so fields carry across the edge
blur = lambda x, s: cv2.GaussianBlur(x.astype(np.float32), (0, 0), s); diff = blur(tone(sat_d), 22) - blur(dr, 22)
edge = np.minimum.reduce([uu / DW, 1 - uu / DW, (vv / DH) * 0.75, (1 - vv / DH) * 0.75]) * DW * 0.1228                 # metres to the nearest photo edge
wgt = np.clip(1 - edge / 70, 0, 1) ** 1.5; corr = diff * wgt[..., None]
for tag, W_, q_ in (("uhd", 6720, 86), ("hd", 4032, 88), ("sd", 2016, 86)):
    t = cv2.resize(im, (W_, W_ * 3 // 4), interpolation=cv2.INTER_AREA).astype(np.float32) + cv2.resize(corr, (W_, W_ * 3 // 4), interpolation=cv2.INTER_CUBIC)
    cv2.imwrite(f"web/tex_{tag}.jpg", np.clip(t, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, q_])
print("sat tone gain", gain.round(2), "edge blend up to 70 m")
