#!/usr/bin/python3 -s
"""traced_px.py (pixel outlines) -> WGS84 KML: bagalur_plots.kml (fields) and bagalur_whole_plot.kml."""
import os
from osgeo import ogr, osr
import json
from traced_px import PLOTS, WHOLE, ORIGIN, RES
# road-snapped outlines from polish_plots.py win over the raw hand traces
if os.path.exists("polished_px.json"):
    _p = json.load(open("polished_px.json"))
    WHOLE, PLOTS = _p["whole"], _p["fields"]
ogr.UseExceptions()
utm = osr.SpatialReference(); utm.ImportFromEPSG(32643)
wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326); wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
tr = osr.CoordinateTransformation(utm, wgs)


def write(path, plots):
    if os.path.exists(path):
        os.remove(path)
    ds = ogr.GetDriverByName("KML").CreateDataSource(path)
    lyr = ds.CreateLayer("plots", wgs)
    for f in ("farm_id", "farmer_name", "Description"):
        lyr.CreateField(ogr.FieldDefn(f, ogr.OFTString))
    for name, pts in plots.items():
        ring = ogr.Geometry(ogr.wkbLinearRing)
        for c, r in list(pts) + [pts[0]]:
            ring.AddPoint_2D(ORIGIN[0] + c * RES, ORIGIN[1] - r * RES)
        poly = ogr.Geometry(ogr.wkbPolygon); poly.AddGeometry(ring)
        ha = poly.GetArea() / 1e4
        poly.Transform(tr)
        f = ogr.Feature(lyr.GetLayerDefn())
        f.SetField("farm_id", f"BAGALUR-{name.split()[0]}"); f.SetField("farmer_name", name[4:])
        f.SetField("Description", f"{name[4:]}, {ha:.2f} ha, traced on DJI_0001 (13 Sep)")
        f.SetGeometry(poly); lyr.CreateFeature(f)
    ds = None


write("bagalur_plots.kml", PLOTS)
write("bagalur_whole_plot.kml", WHOLE)
os._exit(0)
