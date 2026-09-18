"""Pick up boundaries saved from the page's editor (?edit): fetch edits/parcels.json from the live site and write them as lon/lat GeoJSON.
build_site.py uses ../plots/bagalur_parcels_edited.geojson when it exists, so the next build bakes the edits in (areas, labels, and the dimming outside the parcels)."""
import json, sys, urllib.request
from pyproj import Transformer
URL = "https://pi-vps-bombay-16gb.tail641fa8.ts.net/bagalur-estate/edits/parcels.json"
SW, SH, PX, X0, Y1 = 4000, 3000, 0.5, 808152.0, 1418908.0                     # satellite block: size, m/px, UTM 43N top-left corner (as in build_site_geo.py)
T = Transformer.from_crs(32643, 4326, always_xy=True)
src = sys.argv[1] if len(sys.argv) > 1 else URL                               # a downloaded parcels.json works too
d = json.load(open(src)) if not src.startswith("http") else json.load(urllib.request.urlopen(src))
feats = []
for p in d["parcels"]:
    ring = [list(map(lambda v: round(v, 7), T.transform(x + SW * PX / 2 + X0, Y1 - (z + SH * PX / 2)))) for x, z in p["ring"]]; ring.append(ring[0])
    feats.append(dict(type="Feature", properties=dict(id=p["id"], area_m2=p.get("m2"), source="edited in the site-model page, " + d.get("saved", "")), geometry=dict(type="Polygon", coordinates=[ring])))
json.dump(dict(type="FeatureCollection", features=feats), open("../plots/bagalur_parcels_edited.geojson", "w"), indent=1)
print(len(feats), "parcels saved", d.get("saved"), "-> ../plots/bagalur_parcels_edited.geojson")
