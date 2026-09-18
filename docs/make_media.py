#!/usr/bin/python3 -s
"""Rebuild every image in docs/img from the project data (run from the repo root).

  ./docs/make_media.py

Needs the local rasters that are not in git (test-data/bagalur/*.tif, estates/*/sat_1m.tif).
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from osgeo import gdal, ogr, osr
from PIL import Image, ImageDraw, ImageFont

gdal.UseExceptions()
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/img"
OUT.mkdir(parents=True, exist_ok=True)
BAG = ROOT / "test-data/bagalur"
PLOTS = BAG / "plots"
sys.path.insert(0, str(PLOTS))
from roads_px import HIGHWAY  # noqa: E402

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_R = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
RED, YEL, CYAN, INK = (255, 59, 48), (255, 214, 10), (90, 200, 250), (15, 17, 21)

# the Bagalur scene: p05 pixel grid (0.5 m), origin of DJI_0001_final_geo.tif
OX, OY, RES = 808974.963, 1418434.035, 0.5
PX0, PY0, PX1, PY1 = -40, 40, 1540, 1330          # frame in p05 px
SCALE = 0.62                                       # output px per p05 px


def warp(src, dst, alpha=False, rs="average"):
    te = [OX + PX0 * RES, OY - PY1 * RES, OX + PX1 * RES, OY - PY0 * RES]
    args = ["gdalwarp", "-q", "-overwrite", "-te", *map(str, te), "-tr", str(RES), str(RES), "-r", rs]
    if alpha:
        args.append("-dstalpha")
    subprocess.run(args + [str(src), str(dst)], check=True)
    return gdal.Open(str(dst)).ReadAsArray().transpose(1, 2, 0).astype(np.float32)


def over(base, top):
    a = top[..., 3:4] / 255
    return top[..., :3] * a + base * (1 - a)


def font(size, bold=True):
    return ImageFont.truetype(FONT if bold else FONT_R, size)


def caption(im, step, title, sub):
    """Bottom bar with step number, title and one-line subtitle."""
    w, h = im.size
    bar = 92
    d = ImageDraw.Draw(im, "RGBA")
    d.rectangle([0, h - bar, w, h], fill=(15, 17, 21, 225))
    d.rounded_rectangle([22, h - bar + 20, 74, h - 20], 10, fill=RED + (255,))
    d.text((48, h - bar / 2), str(step), font=font(28), fill="white", anchor="mm")
    d.text((92, h - bar + 16), title, font=font(26), fill="white")
    d.text((92, h - bar + 52), sub, font=font(17, False), fill=(200, 205, 212))
    return im


def badge(im, text):
    d = ImageDraw.Draw(im, "RGBA")
    f = font(16)
    tw = d.textlength(text, font=f)
    d.rounded_rectangle([im.width - tw - 40, 18, im.width - 18, 50], 8, fill=(15, 17, 21, 200))
    d.text((im.width - 29, 34), text, font=f, fill="white", anchor="rm")
    return im


def to_img(arr):
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return im.resize((int(im.width * SCALE), int(im.height * SCALE)), Image.LANCZOS)


def T(x, y):
    return ((x - PX0) * SCALE, (y - PY0) * SCALE)


def draw_polys(im, polys, color, width, fill=None, labels=None):
    d = ImageDraw.Draw(im, "RGBA")
    for n, pts in polys.items():
        q = [T(*p) for p in pts]
        if fill:
            d.polygon(q, fill=fill)
        d.line(q + [q[0]], fill=color, width=width, joint="curve")
        if labels:
            cx = sum(a for a, _ in q) / len(q); cy = sum(b for _, b in q) / len(q)
            d.text((cx, cy), labels[n], font=font(15), fill="white", anchor="mm",
                   stroke_width=3, stroke_fill=(0, 0, 0))
    return im


def draw_roads(im, roads):
    d = ImageDraw.Draw(im, "RGBA")
    for w, pts, _ in roads.values():
        d.line([T(*p) for p in pts], fill=CYAN + (255,), width=max(3, int(w * SCALE * 0.8)), joint="curve")
    d.line([T(*p) for p in HIGHWAY], fill=CYAN + (110,), width=int(84 * SCALE))
    return im


def area_labels():
    rows = {}
    for f in json.load(open(PLOTS / "bagalur_whole_plot.eudr.geojson"))["features"]:
        rows[f["properties"]["ProductionPlace"].replace("BAGALUR-", "")] = f["properties"]["Area"]
    return rows


def bagalur():
    tmp = Path(tempfile.mkdtemp())
    sat = warp(BAG / "sat_esri.tif", tmp / "s.tif", rs="cubic")[..., :3]
    raw = warp(BAG / "jpg/DJI_0001_geo.tif", tmp / "r.tif", alpha=True)
    fin = warp(BAG / "jpg/DJI_0001_final_geo.tif", tmp / "f.tif", alpha=True)
    pol = json.load(open(PLOTS / "polished_px.json"))
    roads = json.load(open(PLOTS / "roads_snapped.json"))
    ha = area_labels()
    labels = {n: f"{n.split()[0]}\n{ha.get(n.split()[0], 0):.2f} ha" for n in pol["whole"]}

    f1 = to_img(sat)
    f2 = to_img(over(sat, raw))
    f3 = to_img(over(sat, fin))
    f4 = draw_roads(f3.copy(), roads)
    f5 = draw_polys(f3.copy(), pol["fields"], YEL + (255,), 2, fill=YEL + (38,))
    f6 = draw_polys(f5.copy(), pol["whole"], RED + (255,), 4, labels=labels)

    frames = [
        (f1, 1, "Satellite base map", "Esri World Imagery, Bagalur (Hosur), the reference every layer is checked against"),
        (f2, 2, "One drone photo, placed from its own GPS", "DJI Mini 3 Pro, 500 m, nadir, 8.9 cm/px. Camera XMP only, ~23 m off"),
        (f3, 3, "Aligned to the road network", "Edge phase-correlation + ECC against the satellite: the highway now runs straight through"),
        (f4, 4, "Roads and tracks snapped", "11 cart tracks + NH snapped to the photo within about 1 m, then cut out of every plot"),
        (f5, 5, "45 fields traced", "Every field, orchard and polyhouse as its own polygon (11.0 ha)"),
        (f6, 6, "14 whole plots, EUDR-ready", "Land parcels bounded by tracks and hedges: 21.2 ha, WGS84, 6 dp, all pass eudr_check"),
    ]
    stills = []
    for im, n, t, s in frames:
        im = badge(caption(im.copy(), n, t, s), "TRST01 · EUDR plot mapping")
        stills.append(im)
        im.save(OUT / f"step{n}.jpg", quality=88)

    # GIF: hold each step, short cross-fade to the next
    seq, dur = [], []
    for i, im in enumerate(stills):
        seq.append(im); dur.append(1900 if i < len(stills) - 1 else 3600)
        nxt = stills[(i + 1) % len(stills)]
        for k in (1, 2):
            seq.append(Image.blend(im, nxt, k / 3)); dur.append(110)
    gw = 820                                  # GIF a bit smaller than the stills keeps it < 5 MB
    seq = [s.resize((gw, int(s.height * gw / s.width)), Image.LANCZOS) for s in seq]
    pal = [s.convert("RGB").quantize(colors=160, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for s in seq]
    pal[0].save(OUT / "pipeline.gif", save_all=True, append_images=pal[1:], duration=dur, loop=0, optimize=True)

    # before / after alignment split
    w = f2.width
    split = f3.copy()
    split.paste(f2.crop((0, 0, w // 2, f2.height)), (0, 0))
    d = ImageDraw.Draw(split)
    d.line([(w // 2, 0), (w // 2, split.height)], fill="white", width=3)
    for x, t in ((20, "GPS only"), (w // 2 + 20, "aligned")):
        d.text((x, 20), t, font=font(24), fill="white", stroke_width=3, stroke_fill=(0, 0, 0))
    split.save(OUT / "alignment_split.jpg", quality=88)

    # close-up of W08/W09 at 3x
    zoom(sat, fin, pol, roads, (560, 440, 1300, 800), "closeup_w08_w09.jpg")


def zoom(sat, fin, pol, roads, box, name, Z=1.6):
    x0, y0, x1, y1 = box
    base = over(sat, fin)[y0 - PY0:y1 - PY0, x0 - PX0:x1 - PX0]
    im = Image.fromarray(base.astype(np.uint8)).resize((int((x1 - x0) * Z), int((y1 - y0) * Z)), Image.LANCZOS)
    d = ImageDraw.Draw(im, "RGBA")
    t = lambda x, y: ((x - x0) * Z, (y - y0) * Z)
    for pts in pol["fields"].values():
        q = [t(*p) for p in pts]; d.line(q + [q[0]], fill=YEL + (255,), width=2)
    for pts in pol["whole"].values():
        q = [t(*p) for p in pts]; d.line(q + [q[0]], fill=RED + (255,), width=4, joint="curve")
    im.save(OUT / name, quality=88)


def estate():
    """Yelliemadaloo draft boundary + one-battery flight blocks on the satellite."""
    e = ROOT / "estates/3_yelliemadaloo_murgadi"
    ds = gdal.Open(str(e / "sat_1m.tif"))
    a = ds.ReadAsArray()[:3].transpose(1, 2, 0)
    gt = ds.GetGeoTransform()
    srs = osr.SpatialReference(wkt=ds.GetProjection())
    wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326); wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    tr = osr.CoordinateTransformation(wgs, srs)
    im = Image.fromarray(a).convert("RGB")
    d = ImageDraw.Draw(im, "RGBA")

    def rings(path):
        src = ogr.Open(str(path))
        for lyr in src:
            for f in lyr:
                g = f.GetGeometryRef().Clone(); g.FlattenTo2D(); g.Transform(tr)
                polys = [g] if g.GetGeometryType() == ogr.wkbPolygon else [g.GetGeometryRef(i) for i in range(g.GetGeometryCount())]
                for p in polys:
                    r = p.GetGeometryRef(0)
                    yield f.GetField("Name") if f.GetFieldIndex("Name") >= 0 else "", [
                        ((r.GetX(i) - gt[0]) / gt[1], (r.GetY(i) - gt[3]) / gt[5]) for i in range(r.GetPointCount())]

    cols = [(255, 214, 10), (90, 200, 250), (52, 199, 89), (255, 149, 0), (191, 90, 242)]
    for i, (n, q) in enumerate(rings(e / "boundary.blocks.kml")):
        c = cols[i % len(cols)]
        d.polygon(q, fill=c + (60,), outline=c + (255,))
        cx = sum(x for x, _ in q) / len(q); cy = sum(y for _, y in q) / len(q)
        d.text((cx, cy), n.replace("Block ", "B"), font=font(18), fill="white", anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0))
    for _, q in rings(e / "boundary.kml"):
        d.line(q + [q[0]], fill=RED + (255,), width=4)
    s = 900 / im.width
    im = im.resize((900, int(im.height * s)), Image.LANCZOS)
    badge(im, "Yelliemadaloo · 75.9 ha draft · 4 blocks").save(OUT / "estate_flight_blocks.jpg", quality=88)


def webodm():
    p = ROOT / "test-data/aukerman-output"
    a = Image.open(p / "ortho_preview.png").convert("RGB")
    b = Image.open(p / "dsm_preview.png").convert("RGB").resize(a.size)
    im = Image.new("RGB", (a.width * 2 + 12, a.height), "white")
    im.paste(a, (0, 0)); im.paste(b, (a.width + 12, 0))
    s = 900 / im.width
    im = im.resize((900, int(im.height * s)), Image.LANCZOS)
    badge(im, "WebODM GPU test · 77 photos · 14 min").save(OUT / "webodm_test.jpg", quality=88)


if __name__ == "__main__":
    bagalur()
    estate()
    webodm()
    for f in sorted(OUT.iterdir()):
        print(f"{f.stat().st_size / 1e6:6.2f} MB  {f.name}")
    sys.stdout.flush()
    os._exit(0)
