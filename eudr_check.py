#!/usr/bin/python3 -s
"""Turn any farm file TRST01 sends into EUDR-ready GeoJSON, and check every plot.

Usage:
  ./eudr_check.py incoming/farms.kml            # one file
  ./eudr_check.py incoming/                     # every file in a folder
  ./eudr_check.py incoming/ --fix               # also repair invalid polygons

Reads anything GDAL can open: KML/KMZ, GeoJSON, Shapefile, GeoPackage, GPX,
CSV with lat/lon columns (or a WKT column). Writes, per input file:
  out/<name>.eudr.geojson   WGS84 (EPSG:4326), 2D, 6 decimal places
  out/<name>.report.csv     one row per plot with status + problems

EUDR rules checked (Reg. 2023/1115 as amended Dec 2025):
  - plot > 4 ha  -> must be a polygon (a point is not enough)
  - plot <= 4 ha -> point or polygon both fine
  - polygon must be valid: closed, >= 4 distinct vertices, no self-intersections
  - coordinates must fall inside India (catches swapped lat/lon)
Also flags farms that overlap each other, and multi-part plots.
"""
import argparse
import csv
import os
import sys
from pathlib import Path

from osgeo import gdal, ogr, osr

gdal.UseExceptions()
ogr.UseExceptions()
gdal.PushErrorHandler("CPLQuietErrorHandler")

HA_LIMIT = 4.0
INDIA_BBOX = (68.0, 6.0, 98.0, 37.5)  # lon_min, lat_min, lon_max, lat_max
OVERLAP_MIN_HA = 0.01
READABLE = {".kml", ".kmz", ".geojson", ".json", ".shp", ".gpkg", ".gpx", ".csv"}


def srs(epsg):
    s = osr.SpatialReference()
    s.ImportFromEPSG(epsg)
    s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)  # lon, lat
    return s


WGS84 = srs(4326)
_UTM_CACHE = {}


def to_utm(geom):
    """Transform to the UTM zone of the plot's own centroid (India spans zones 42-47)."""
    lon, lat = geom.Centroid().GetPoint_2D(0)
    epsg = (32600 if lat >= 0 else 32700) + min(60, max(1, int((lon + 180) // 6) + 1))
    if epsg not in _UTM_CACHE:
        _UTM_CACHE[epsg] = osr.CoordinateTransformation(WGS84, srs(epsg))
    g = geom.Clone()
    g.Transform(_UTM_CACHE[epsg])
    return g


def open_any(path):
    if path.suffix.lower() == ".csv":
        return gdal.OpenEx(str(path), gdal.OF_VECTOR, open_options=[
            "X_POSSIBLE_NAMES=lon*,long*,x,easting",
            "Y_POSSIBLE_NAMES=lat*,y,northing",
            "GEOM_POSSIBLE_NAMES=wkt,geom*,polygon",
            "KEEP_GEOM_COLUMNS=NO",
        ])
    return gdal.OpenEx(str(path), gdal.OF_VECTOR)


def first_field(feat, keys):
    for key in keys:
        i = feat.GetFieldIndex(key)
        if i >= 0 and feat.GetField(i) not in (None, ""):
            return str(feat.GetField(i))
    return None


def farm_name(feat, idx):
    for key in ("farm_id", "plot_id", "id", "name", "Name", "farmer", "farmer_name"):
        i = feat.GetFieldIndex(key)
        if i >= 0 and feat.GetField(i) not in (None, ""):
            return str(feat.GetField(i))
    return f"plot_{idx}"


def distinct_vertices(geom):
    pts = set()
    for i in range(geom.GetGeometryCount()):
        part = geom.GetGeometryRef(i)
        ring = part.GetGeometryRef(0) if part.GetGeometryCount() else part
        for j in range(ring.GetPointCount()):
            x, y = ring.GetPoint_2D(j)
            pts.add((round(x, 6), round(y, 6)))
    return len(pts)


def check_plot(geom, declared_ha, fix):
    """Return (geom, area_ha, problems[], warnings[])."""
    problems, warnings = [], []
    gtype = ogr.GT_Flatten(geom.GetGeometryType())

    env = geom.GetEnvelope()  # minx, maxx, miny, maxy
    if not (INDIA_BBOX[0] <= env[0] and env[1] <= INDIA_BBOX[2]
            and INDIA_BBOX[1] <= env[2] and env[3] <= INDIA_BBOX[3]):
        if INDIA_BBOX[1] <= env[0] <= INDIA_BBOX[3] and INDIA_BBOX[0] <= env[2] <= INDIA_BBOX[2]:
            problems.append("lat/lon look SWAPPED")
        else:
            problems.append("coordinates outside India")

    if gtype in (ogr.wkbPoint, ogr.wkbMultiPoint):
        area = declared_ha
        if declared_ha is None:
            warnings.append("point with no declared area - confirm plot is <= 4 ha")
        elif declared_ha > HA_LIMIT:
            problems.append(f"point given but plot is {declared_ha:.2f} ha > 4 ha - needs a polygon")
        return geom, area, problems, warnings

    if gtype not in (ogr.wkbPolygon, ogr.wkbMultiPolygon):
        problems.append(f"unsupported geometry {ogr.GeometryTypeToName(gtype)} (lines must be closed into polygons)")
        return geom, None, problems, warnings

    if not geom.IsValid():
        if fix:
            fixed = geom.MakeValid()
            if ogr.GT_Flatten(fixed.GetGeometryType()) == ogr.wkbGeometryCollection:
                polys = ogr.Geometry(ogr.wkbMultiPolygon)
                for i in range(fixed.GetGeometryCount()):
                    g = fixed.GetGeometryRef(i)
                    if ogr.GT_Flatten(g.GetGeometryType()) == ogr.wkbPolygon:
                        polys.AddGeometry(g)
                fixed = polys
            geom = fixed
            warnings.append("was invalid (self-intersection) - auto-repaired, CHECK SHAPE")
        else:
            problems.append("invalid polygon (self-intersection / bad ring) - rerun with --fix or redraw")

    if distinct_vertices(geom) < 4:
        problems.append("fewer than 4 distinct vertices")
    if ogr.GT_Flatten(geom.GetGeometryType()) == ogr.wkbMultiPolygon and geom.GetGeometryCount() > 1:
        warnings.append(f"multi-part plot ({geom.GetGeometryCount()} parts) - EUDR expects one polygon per plot; split if these are separate plots")

    area = to_utm(geom).GetArea() / 10_000
    if declared_ha and abs(area - declared_ha) / declared_ha > 0.25:
        warnings.append(f"mapped {area:.2f} ha vs declared {declared_ha:.2f} ha (>25% off)")
    return geom, area, problems, warnings


def declared_area(feat):
    for key in ("area_ha", "hectares", "ha", "area"):
        i = feat.GetFieldIndex(key)
        if i >= 0 and feat.GetField(i) not in (None, ""):
            try:
                return float(feat.GetField(i))
            except (TypeError, ValueError):
                pass
    return None


def process(path, outdir, fix):
    ds = open_any(path)
    rows, plots = [], []
    idx = 0
    for li in range(ds.GetLayerCount()):
        layer = ds.GetLayer(li)
        src = layer.GetSpatialRef()
        if src is not None:
            src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        to_wgs = osr.CoordinateTransformation(src, WGS84) if src and not src.IsSame(WGS84) else None
        for feat in layer:
            idx += 1
            geom = feat.GetGeometryRef()
            name = farm_name(feat, idx)
            if geom is None or geom.IsEmpty():
                rows.append([name, "", "", "FAIL", "no geometry", ""])
                continue
            geom = geom.Clone()
            geom.FlattenTo2D()
            if to_wgs:
                geom.Transform(to_wgs)
            geom, area, problems, warnings = check_plot(geom, declared_area(feat), fix)
            plots.append((name, geom, area, problems, first_field(feat, ("farmer_name", "farmer", "producer", "owner")) or name))
            rows.append([name, ogr.GeometryTypeToName(ogr.GT_Flatten(geom.GetGeometryType())),
                         "" if area is None else f"{area:.3f}",
                         "FAIL" if problems else ("WARN" if warnings else "OK"),
                         "; ".join(problems), "; ".join(warnings)])

    # farms overlapping each other (double-declared land)
    for i in range(len(plots)):
        for j in range(i + 1, len(plots)):
            a, b = plots[i][1], plots[j][1]
            if ogr.GT_Flatten(a.GetGeometryType()) == ogr.wkbPoint or ogr.GT_Flatten(b.GetGeometryType()) == ogr.wkbPoint:
                continue
            if a.IsValid() and b.IsValid() and a.Intersects(b):
                ha = to_utm(a.Intersection(b)).GetArea() / 10_000
                if ha >= OVERLAP_MIN_HA:
                    for k, other in ((i, plots[j][0]), (j, plots[i][0])):
                        r = rows[[x[0] for x in rows].index(plots[k][0])]
                        r[5] = "; ".join(filter(None, [r[5], f"overlaps {other} by {ha:.2f} ha"]))
                        if r[3] == "OK":
                            r[3] = "WARN"

    # write EUDR GeoJSON (only plots with no hard problems)
    out_json = outdir / f"{path.stem}.eudr.geojson"
    drv = ogr.GetDriverByName("GeoJSON")
    if out_json.exists():
        drv.DeleteDataSource(str(out_json))
    ods = drv.CreateDataSource(str(out_json))
    ol = ods.CreateLayer("plots", WGS84, ogr.wkbUnknown,
                         options=["RFC7946=YES", "COORDINATE_PRECISION=6", "WRITE_NAME=NO"])
    ol.CreateField(ogr.FieldDefn("ProducerName", ogr.OFTString))
    fa = ogr.FieldDefn("Area", ogr.OFTReal)
    ol.CreateField(fa)
    ol.CreateField(ogr.FieldDefn("ProductionPlace", ogr.OFTString))
    written = 0
    for name, geom, area, problems, producer in plots:
        if problems:
            continue
        f = ogr.Feature(ol.GetLayerDefn())
        f.SetField("ProducerName", producer)
        f.SetField("ProductionPlace", name)
        if area is not None:
            f.SetField("Area", round(area, 4))
        f.SetGeometry(geom)
        ol.CreateFeature(f)
        written += 1
    ods = None

    out_csv = outdir / f"{path.stem}.report.csv"
    with open(out_csv, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["plot", "geometry", "area_ha", "status", "problems", "warnings"])
        w.writerows(rows)

    ok = sum(r[3] == "OK" for r in rows)
    warn = sum(r[3] == "WARN" for r in rows)
    fail = sum(r[3] == "FAIL" for r in rows)
    total_ha = sum(float(r[2]) for r in rows if r[2])
    print(f"\n== {path.name}: {len(rows)} plots, {total_ha:.1f} ha | OK {ok}  WARN {warn}  FAIL {fail}")
    for r in rows:
        if r[3] != "OK":
            print(f"  [{r[3]}] {r[0]} ({r[2] or '?'} ha): {r[4] or r[5]}" + (f" | {r[5]}" if r[4] and r[5] else ""))
    print(f"  -> {out_json}  ({written} plots written; FAIL plots left out)")
    print(f"  -> {out_csv}")
    return fail


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path(__file__).parent / "out")
    ap.add_argument("--fix", action="store_true", help="auto-repair invalid polygons (check the result!)")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    files = []
    for p in args.inputs:
        files += sorted(f for f in p.iterdir() if f.suffix.lower() in READABLE) if p.is_dir() else [p]
    if not files:
        sys.exit("no readable farm files found")
    fails = sum(process(f, args.out, args.fix) for f in files)
    sys.stdout.flush()
    os._exit(1 if fails else 0)  # skip GDAL SWIG teardown noise


if __name__ == "__main__":
    main()
