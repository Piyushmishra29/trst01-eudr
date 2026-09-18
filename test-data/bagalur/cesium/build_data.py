"""Everything the Cesium page draws, in lon/lat: EUDR plots, crop blocks with plant counts, buildings, trees, points of interest."""
import json, numpy as np, cv2
from scipy import ndimage as ndi
from geo import lonlat, A
M = float(np.hypot(A[0, 0], A[1, 0]) * 0.5)                       # metres per drone px (4032 wide)
im = cv2.imread("../ai3d/web/tex_hd.jpg"); b, g, r = [c.astype(np.float32) for c in cv2.split(im)]
exg = cv2.GaussianBlur((2 * g - r - b) / (r + g + b + 1), (0, 0), 3)
ll = lambda u, v: [round(float(x), 7) for x in lonlat(u, v)]
ring = lambda pts: [ll(u, v) for u, v in pts]

# crop blocks, outlined by hand on the photo (px); crop type from the grower + how the crowns look. The camera faced west: photo right = north, photo top = west
BLOCKS = [("Mango orchard · north-west", "mango", [(3130, 160), (3680, 160), (3680, 880), (3130, 880)], 30),
          ("Mango orchard · north", "mango", [(2900, 960), (3620, 960), (3620, 1400), (2900, 1400)], 30),
          ("Mango orchard · north-east", "mango", [(2790, 2140), (3540, 2140), (3540, 2330), (2790, 2330)], 26),
          ("Areca nut (supari) · west", "areca", [(1240, 440), (1960, 440), (1960, 940), (1240, 940)], 12),
          ("Areca nut (supari) · south-west", "areca", [(330, 580), (660, 580), (660, 1010), (330, 1010)], 12)]
blocks = []; plants = []
for name, crop, pts, md in BLOCKS:
    m = np.zeros(exg.shape, np.uint8); cv2.fillPoly(m, [np.int32(pts)], 1)
    pk = (exg == ndi.maximum_filter(exg, size=2 * md + 1)) & (exg > 0.06) & (m > 0)       # one peak of greenness per plant
    area = cv2.contourArea(np.float32(pts)) * M * M / 1e4
    blocks.append(dict(name=name, crop=crop, ring=ring(pts), ha=round(area, 2), plants=int(pk.sum()), centre=ll(*np.mean(pts, 0))))
    ys, xs = np.where(pk); plants += [[int(x), int(y), crop] for x, y in zip(xs, ys)]
    print(name, blocks[-1]["ha"], "ha", blocks[-1]["plants"], "plants")

json.dump(plants, open("work/block_plants.json", "w"))                 # photo px of every counted orchard plant, for build_trees.py
T = json.load(open("../ai3d/web/trees.json"))["trees"]; trees = []
for cx, cy, rx, ry, ht, palm in T:
    rw = (rx + ry) / 2 * M; H = max(ht * 10 * (1.6 if palm else 1), (2.2 if palm else 1.5) * rw)
    x0, x1, y0, y1 = int(cx - rx * .5), int(cx + rx * .5) + 1, int(cy - ry * .5), int(cy + ry * .5) + 1
    c = im[max(y0, 0):y1, max(x0, 0):x1].reshape(-1, 3).mean(0)[::-1]
    trees.append([*ll(cx, cy), round(rw, 1), round(H, 1), int(palm), *[int(v) for v in c]])
B = json.load(open("../ai3d/web/buildings.json"))["buildings"]
blds = [dict(ring=ring(b_["poly"]), h=round((0.25 + 0.6 * b_["h"]) * 10, 1), m2=b_["area_m2"], roof=b_["roof"]) for b_ in B]
plots = json.load(open("../plots/bagalur_whole_plot.eudr.geojson"))
pois = [dict(name="Polyhouses", text="Protected cultivation, about 1.1 ha under cover", at=ll(1600, 2760)),
        dict(name="Packing sheds", text="Two large sheds beside the farm track", at=ll(660, 1280)),
        dict(name="Quarry ponds", text="Old quarry, now water. Outside the farm plots", at=ll(200, 1150)),
        dict(name="Farm pond", text="Lined pond for irrigation", at=ll(1030, 1760)),
        dict(name="Solar roof", text="Rooftop solar on the unit by the road", at=ll(3250, 2680))]
foot = ring([(0, 0), (4032, 0), (4032, 3024), (0, 3024)])
out = dict(footprint=foot, centre=ll(2016, 1512), blocks=blocks, trees=trees, buildings=blds, plots=plots, pois=pois,
           stats=dict(trees=len(trees), palms=sum(t[4] for t in trees), buildings=len(blds), plots=len(plots["features"]), plots_ha=round(sum(f["properties"]["Area"] for f in plots["features"]), 1), gsd_cm=round(M * 50, 1)))
json.dump(out, open("web/data.json", "w"), separators=(",", ":")); print(out["stats"])
