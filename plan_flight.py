#!/usr/bin/python3 -s
"""Split an estate boundary into one-battery mapping blocks and estimate the job.

Usage:
  ./plan_flight.py estates/devadhanam/boundary.kml
  ./plan_flight.py boundary.kml --drone air2s --alt 90 --side 75

Input: any polygon file GDAL reads (KML/KMZ from Google Earth, GeoJSON, GPKG, SHP).
Output, next to the input:
  <name>.blocks.kml   one polygon per battery -> import each into DroneDeploy
                      (Flight plan > import KML) as its own mission
  <name>.lines.kml    the flight lines, for checking coverage in QGIS/Google Earth
  <name>.plan.txt     GSD, spacing, batteries, photos, flying time

Photogrammetry is processed later in WebODM; ODM itself does not fly the drone.
"""
import argparse
import math
import os
import sys
from pathlib import Path

from osgeo import gdal, ogr, osr

gdal.UseExceptions()
ogr.UseExceptions()
gdal.PushErrorHandler("CPLQuietErrorHandler")

# 12 MP / native stills. pixel = sensor width / image width, all in mm.
DRONES = {
    "air2":     dict(name="DJI Mavic Air 2 (12MP)", f=4.49, px=0.0016, w=4000, h=3000, batt_min=34),
    "air2s":    dict(name="DJI Air 2S (20MP 1in)",  f=8.38, px=0.00241, w=5472, h=3648, batt_min=31),
    "mini3pro": dict(name="DJI Mini 3 Pro (12MP)",  f=6.72, px=0.0024, w=4032, h=3024, batt_min=34),
}


def srs(epsg):
    s = osr.SpatialReference()
    s.ImportFromEPSG(epsg)
    s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return s


WGS84 = srs(4326)


def load_boundary(path):
    ds = gdal.OpenEx(str(path), gdal.OF_VECTOR)
    union = None
    for li in range(ds.GetLayerCount()):
        layer = ds.GetLayer(li)
        src = layer.GetSpatialRef() or WGS84
        src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        tr = None if src.IsSame(WGS84) else osr.CoordinateTransformation(src, WGS84)
        for feat in layer:
            g = feat.GetGeometryRef()
            if g is None or ogr.GT_Flatten(g.GetGeometryType()) not in (ogr.wkbPolygon, ogr.wkbMultiPolygon):
                continue
            g = g.Clone()
            g.FlattenTo2D()
            if tr:
                g.Transform(tr)
            g = g if g.IsValid() else g.MakeValid()
            union = g if union is None else union.Union(g)
    if union is None:
        sys.exit("no polygon found in " + str(path))
    return union


def utm_for(geom):
    lon, lat = geom.Centroid().GetPoint_2D(0)
    return srs((32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1)


def write_kml(path, feats):
    drv = ogr.GetDriverByName("KML")
    if path.exists():
        path.unlink()
    ds = drv.CreateDataSource(str(path))
    layer = ds.CreateLayer(path.stem, WGS84)
    layer.CreateField(ogr.FieldDefn("Name", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("Description", ogr.OFTString))
    for name, desc, g in feats:
        f = ogr.Feature(layer.GetLayerDefn())
        f.SetField("Name", name)
        f.SetField("Description", desc)
        f.SetGeometry(g)
        layer.CreateFeature(f)
    ds = None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("boundary", type=Path)
    ap.add_argument("--drone", choices=DRONES, default="air2")
    ap.add_argument("--alt", type=float, default=100, help="height above take-off, m (max 120 in India)")
    ap.add_argument("--front", type=float, default=80, help="front overlap %%")
    ap.add_argument("--side", type=float, default=75, help="side overlap %% (75+ for tree canopy)")
    ap.add_argument("--speed", type=float, default=5, help="m/s; keep <=5 for rolling shutter")
    ap.add_argument("--reserve", type=float, default=0.35, help="battery fraction held back (RTH, wind, hills)")
    ap.add_argument("--heading", type=float, default=None, help="line direction in degrees; default = long axis")
    a = ap.parse_args()
    if a.alt > 120:
        sys.exit("India limit is 120 m (400 ft) AGL")

    d = DRONES[a.drone]
    gsd = a.alt * d["px"] / d["f"]  # m/px
    foot_w, foot_h = gsd * d["w"], gsd * d["h"]  # across-track, along-track
    spacing = foot_w * (1 - a.side / 100)
    trigger = foot_h * (1 - a.front / 100)
    usable_s = d["batt_min"] * 60 * (1 - a.reserve)
    line_m_per_batt = a.speed * usable_s * 0.85  # 15% lost to turns / transit
    ha_per_batt = line_m_per_batt * spacing / 10_000

    wgs = load_boundary(a.boundary)
    utm = utm_for(wgs)
    to_utm = osr.CoordinateTransformation(WGS84, utm)
    to_wgs = osr.CoordinateTransformation(utm, WGS84)
    b = wgs.Clone()
    b.Transform(to_utm)
    area_ha = b.GetArea() / 10_000

    # line direction: long axis of the minimum bounding box, unless given
    if a.heading is None:
        best = None
        hull = b.ConvexHull()
        ring = hull.GetGeometryRef(0)
        pts = [ring.GetPoint_2D(i) for i in range(ring.GetPointCount())]
        for deg in range(0, 180, 5):
            r = math.radians(deg)
            c, s = math.cos(r), math.sin(r)
            vs = [(-x * s + y * c) for x, y in pts]
            width = max(vs) - min(vs)  # lines run along u, so fewer lines when v is narrow
            if best is None or width < best[1]:
                best = (deg, width)
        heading = best[0]
    else:
        heading = a.heading
    r = math.radians(heading)
    ux, uy = math.cos(r), math.sin(r)     # along-line
    vx, vy = -math.sin(r), math.cos(r)    # across-line

    # blocks: strips of whole lines, cut along-track so each fits one battery
    minx, maxx, miny, maxy = b.GetEnvelope()
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    R = math.hypot(maxx - minx, maxy - miny) / 2 + spacing
    lines_per_block = max(2, int(math.sqrt(line_m_per_batt / spacing)))  # roughly square blocks
    block_w = lines_per_block * spacing
    block_l = line_m_per_batt / lines_per_block

    def rect(v0, v1, u0, u1):
        ring = ogr.Geometry(ogr.wkbLinearRing)
        for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1), (u0, v0)):
            ring.AddPoint_2D(cx + u * ux + v * vx, cy + u * uy + v * vy)
        p = ogr.Geometry(ogr.wkbPolygon)
        p.AddGeometry(ring)
        return p

    blocks, lines = [], []
    v = -R
    while v < R:
        u = -R
        while u < R:
            cell = rect(v, v + block_w, u, u + block_l).Intersection(b)
            if not cell.IsEmpty() and cell.GetArea() > 0.02 * block_w * block_l:
                blocks.append(cell)
            u += block_l
        v += block_w
    # fold slivers (<30% of a full block) into the neighbour they share most edge with
    full = block_w * block_l
    changed = True
    while changed and len(blocks) > 1:
        changed = False
        blocks.sort(key=lambda g: g.GetArea())
        small = blocks[0]
        if small.GetArea() >= 0.3 * full:
            break
        ring = small.Buffer(1.0)
        fits = [k for k in range(1, len(blocks)) if blocks[k].GetArea() + small.GetArea() <= 1.15 * full]
        if not fits:
            break
        best = max(fits, key=lambda k: ring.Intersection(blocks[k]).GetArea())
        if ring.Intersection(blocks[best]).GetArea() > 0:
            blocks[best] = blocks[best].Union(small)
            blocks.pop(0)
            changed = True

    total_line = 0.0
    v = -R + spacing / 2
    while v < R:
        seg = ogr.Geometry(ogr.wkbLineString)
        seg.AddPoint_2D(cx - R * ux + v * vx, cy - R * uy + v * vy)
        seg.AddPoint_2D(cx + R * ux + v * vx, cy + R * uy + v * vy)
        inter = seg.Intersection(b.Buffer(spacing / 2))
        if not inter.IsEmpty():
            total_line += inter.Length()
            lines.append(inter)
        v += spacing

    photos = int(total_line / trigger)
    fly_min = total_line / a.speed / 60 / 0.85
    batts = math.ceil(fly_min / (usable_s / 60))

    stem = a.boundary.with_suffix("")
    feats = []
    for i, blk in enumerate(sorted(blocks, key=lambda g: (-g.Centroid().GetY(), g.Centroid().GetX())), 1):
        ha = blk.GetArea() / 10_000
        g = blk.Clone()
        g.Transform(to_wgs)
        feats.append((f"Block {i:02d}", f"{ha:.1f} ha, 1 battery, {a.alt:.0f} m, {a.front:.0f}/{a.side:.0f} overlap", g))
    write_kml(Path(f"{stem}.blocks.kml"), feats)
    lf = []
    for i, ln in enumerate(lines, 1):
        g = ln.Clone()
        g.Transform(to_wgs)
        lf.append((f"line {i}", "", g))
    write_kml(Path(f"{stem}.lines.kml"), lf)

    report = f"""Flight plan: {a.boundary.name}
Drone        {d['name']}
Area         {area_ha:.1f} ha ({area_ha * 2.471:.0f} acres)
Height       {a.alt:.0f} m above take-off  -> GSD {gsd * 100:.1f} cm/px (on flat ground)
Footprint    {foot_w:.0f} x {foot_h:.0f} m per photo
Overlap      front {a.front:.0f}% (photo every {trigger:.0f} m, {trigger / a.speed:.1f} s)  side {a.side:.0f}% (lines {spacing:.0f} m apart)
Speed        {a.speed:.0f} m/s, line heading {heading:.0f} deg
Per battery  ~{ha_per_batt:.1f} ha ({usable_s / 60:.0f} min usable of {d['batt_min']})
Blocks       {len(blocks)}  -> {Path(f'{stem}.blocks.kml').name}
Flight lines {total_line / 1000:.1f} km, ~{photos} photos, ~{fly_min:.0f} min in the air
Batteries    ~{batts} flights (add 20% spare for hills/wind)
WebODM       split into jobs of <=800 photos on 32 GB RAM -> ~{max(1, math.ceil(photos / 800))} job(s)

On a slope the GSD and overlap change: take off from the HIGHEST point of each
block, or the far side will be closer to the drone than planned.
"""
    Path(f"{stem}.plan.txt").write_text(report)
    print(report)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
