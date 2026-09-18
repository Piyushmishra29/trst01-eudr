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
