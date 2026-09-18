#!/usr/bin/python3 -s
"""Photo-correct a placed drone image: remove haze, white-balance on white roofs, restore saturation.

Usage: ./dehaze.py in_geo.tif [-o out.tif] [--sat 1.35] [--haze 1.0]
High flights (200-500 m) look grey-blue and flat because of the air between camera and
ground; map colour matching can't undo that. Stats come from a 1/8 preview, the
correction is applied to the full-resolution file in strips. Georeferencing is copied.
"""
import argparse
import os
import numpy as np
from osgeo import gdal

gdal.UseExceptions()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("-o", "--out")
    ap.add_argument("--sat", type=float, default=1.15, help="saturation boost")
    ap.add_argument("--haze", type=float, default=0.8, help="0 = none, 1 = remove the estimated veil")
    ap.add_argument("--contrast", type=float, default=0.35, help="S-curve strength")
    ap.add_argument("--wb", choices=["camera", "roofs"], default="camera",
                    help="camera = keep the DNG's as-shot white balance (default); roofs = neutralise the brightest roofs")
    ap.add_argument("--ref", help="map/satellite to take the overall colour tint from (instead of white roofs)")
    a = ap.parse_args()
    out = a.out or a.src.replace("_geo.tif", "_clean_geo.tif")
    ds = gdal.Open(a.src)
    w, h, nb = ds.RasterXSize, ds.RasterYSize, ds.RasterCount

    pv = gdal.Translate("", ds, format="MEM", width=w // 8, height=h // 8, resampleAlg="average").ReadAsArray()
    valid = pv[3] > 0 if nb == 4 else np.ones(pv.shape[1:], bool)
    x = pv[:3].astype(np.float32)
    # 1. haze = the floor each channel never goes below (darkest real ground still reads grey-blue)
    floor = np.array([np.percentile(x[c][valid], 0.5) for c in range(3)]) * a.haze
    if a.wb == "camera" and not a.ref:
        floor = np.full(3, floor.min(), np.float32) + (floor - floor.min()) * 0.5  # remove the blue veil only halfway
    x = x - floor[:, None, None]
    # 2. white balance: overall tint from a reference map if given, else neutral white roofs
    if a.ref:
        gt = ds.GetGeoTransform()
        te = [gt[0], gt[3] + h * gt[5], gt[0] + w * gt[1], gt[3]]
        r = gdal.Warp("", a.ref, format="MEM", outputBounds=te, width=pv.shape[2], height=pv.shape[1],
                      dstSRS=ds.GetProjection(), resampleAlg="average").ReadAsArray()[:3].astype(np.float32)
        rv = valid & (r.sum(0) > 0)
        ref_bal = np.array([np.median(r[c][rv]) for c in range(3)]); ref_bal /= ref_bal.mean()
        own_bal = np.array([np.median(x[c][rv]) for c in range(3)]); own_bal /= own_bal.mean()
        gain = ref_bal / own_bal
    elif a.wb == "camera":
        gain = np.ones(3, np.float32)
    else:
        lum = x.mean(0)
        wp = valid & (lum >= np.percentile(lum[valid], 99))
        white = np.array([np.median(x[c][wp]) for c in range(3)])
        gain = white.mean() / white
    x = x * gain[:, None, None]
    # 3. stretch so 99.5th percentile of luminance hits ~245
    top = np.percentile(x.mean(0)[valid], 99.5)
    k = 245.0 / top
    print(f"haze floor {floor.round(1)}  wb gain {gain.round(3)}  stretch x{k:.2f}", flush=True)

    drv = gdal.GetDriverByName("GTiff")
    dst = drv.Create(out, w, h, nb, gdal.GDT_Byte, ["COMPRESS=JPEG", "JPEG_QUALITY=92", "TILED=YES"])
    dst.SetGeoTransform(ds.GetGeoTransform())
    dst.SetProjection(ds.GetProjection())
    for y0 in range(0, h, 512):
        rows = min(512, h - y0)
        px = np.stack([ds.GetRasterBand(b + 1).ReadAsArray(0, y0, w, rows).astype(np.float32) for b in range(3)])
        px = (px - floor[:, None, None]) * gain[:, None, None] * k
        # gentle S-curve for contrast, then saturation around luminance
        px = np.clip(px, 0, 255) / 255.0
        px = px + a.contrast * px * (1 - px) * (2 * px - 1)  # S-curve: darker darks, brighter lights
        l = px.mean(0, keepdims=True)
        px = l + (px - l) * a.sat
        px = np.clip(px * 255, 0, 255).astype(np.uint8)
        for b in range(3):
            dst.GetRasterBand(b + 1).WriteArray(px[b], 0, y0)
        if nb == 4:
            dst.GetRasterBand(4).WriteArray(ds.GetRasterBand(4).ReadAsArray(0, y0, w, rows), 0, y0)
    for b, ci in enumerate([gdal.GCI_RedBand, gdal.GCI_GreenBand, gdal.GCI_BlueBand] + ([gdal.GCI_AlphaBand] if nb == 4 else [])):
        dst.GetRasterBand(b + 1).SetColorInterpretation(ci)
    dst.BuildOverviews("AVERAGE", [2, 4, 8, 16])
    dst = None
    print("clean ->", out, flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
