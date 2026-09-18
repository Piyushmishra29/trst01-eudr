#!/usr/bin/python3 -s
"""Put a single straight-down DJI photo on the map using only its own metadata.

Usage:
  ./place_photo.py /media/.../DJI_0006.JPG [-o outdir]

Reads GPS, RelativeAltitude and GimbalYawDegree from the DJI XMP, computes the
ground footprint, and writes <name>_geo.tif (UTM, at the photo's own GSD) that
opens in QGIS on top of satellite imagery. If given a .DNG, the sibling .JPG is used.
Only for nadir shots (gimbal pitch about -90); oblique photos are refused.
Height is above TAKE-OFF, so the footprint is off when the ground here is
much higher or lower than the take-off point.
"""
import argparse
import math
import re
import subprocess
import sys
from pathlib import Path

from osgeo import gdal, osr

gdal.UseExceptions()

# DJI camera model -> (sensor width mm, focal mm)
CAMERAS = {"FC3582": (9.6, 6.72), "FC3170": (6.4, 4.49), "FC3411": (13.2, 8.38)}


def xmp(path):
    head = path.read_bytes()[:600_000].decode("latin-1")
    get = lambda k: float(re.search(rf'drone-dji:{k}="([-+0-9.]+)"', head).group(1))
    model = re.search(r'tiff:Model="([^"]+)"', head).group(1)
    return dict(lat=get("GpsLatitude"), lon=get("GpsLongitude"), h=get("RelativeAltitude"),
                yaw=get("GimbalYawDegree"), pitch=get("GimbalPitchDegree"), model=model)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photo", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path.cwd())
    ap.add_argument("--raw", action="store_true", help="develop the .DNG (camera white balance) instead of using the JPG")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.raw:
        dng = a.photo.with_suffix(".DNG") if a.photo.with_suffix(".DNG").exists() else a.photo
        m = xmp(dng)
        src = a.out / f"{dng.stem}_raw.tif"
        here = Path(__file__).resolve().parent
        subprocess.run([str(here / ".venv/bin/python"), str(here / "develop_dng.py"), str(dng), str(src)], check=True)
    else:
        src = a.photo.with_suffix(".JPG") if a.photo.suffix.upper() == ".DNG" and a.photo.with_suffix(".JPG").exists() else a.photo
        m = xmp(src)
    if abs(m["pitch"] + 90) > 3:
        sys.exit(f"gimbal pitch {m['pitch']} - not a straight-down photo, can't place it this way")
    if m["model"] not in CAMERAS:
        sys.exit(f"unknown camera {m['model']}; add its sensor width/focal to CAMERAS")
    sw, f = CAMERAS[m["model"]]
    ds = gdal.Open(str(src))
    W, H = ds.RasterXSize, ds.RasterYSize
    gsd = m["h"] * (sw / W) / f
    fw, fh = W * gsd, H * gsd

    wgs = osr.SpatialReference(); wgs.ImportFromEPSG(4326); wgs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    epsg = 32600 + int((m["lon"] + 180) // 6) + 1
    utm = osr.SpatialReference(); utm.ImportFromEPSG(epsg)
    cx, cy, _ = osr.CoordinateTransformation(wgs, utm).TransformPoint(m["lon"], m["lat"])
    r = math.radians(m["yaw"])  # image "up" points to this compass heading

    def corner(dx, dy):  # dx right / dy up in the image, metres
        return cx + dx * math.cos(r) + dy * math.sin(r), cy - dx * math.sin(r) + dy * math.cos(r)

    gcps = [(0, 0, *corner(-fw / 2, fh / 2)), (W, 0, *corner(fw / 2, fh / 2)),
            (W, H, *corner(fw / 2, -fh / 2)), (0, H, *corner(-fw / 2, -fh / 2)), (W / 2, H / 2, cx, cy)]
    tmp = a.out / f"{src.stem}_gcp.tif"
    out = a.out / f"{src.stem}_geo.tif"
    subprocess.run(["gdal_translate", "-q", "-a_srs", f"EPSG:{epsg}"]
                   + sum([["-gcp", str(p), str(l), f"{x:.2f}", f"{y:.2f}"] for p, l, x, y in gcps], [])
                   + [str(src), str(tmp)], check=True)
    res = f"{gsd:.3f}"  # keep the photo's own detail
    subprocess.run(["gdalwarp", "-q", "-overwrite", "-r", "bilinear", "-tr", res, res, "-dstalpha",
                    "-co", "COMPRESS=JPEG", "-co", "JPEG_QUALITY=92", "-co", "TILED=YES", "-b", "1", "-b", "2", "-b", "3",
                    str(tmp), str(out)], check=True)
    tmp.unlink()
    print(f"{src.name}: {m['lat']:.6f}, {m['lon']:.6f}  {m['h']:.0f} m above take-off, facing {m['yaw']:.0f} deg")
    print(f"  {gsd * 100:.1f} cm/px, covers {fw:.0f} x {fh:.0f} m -> {out}")


if __name__ == "__main__":
    main()
