#!/usr/bin/python3 -s
"""Match a placed drone photo's colours to a reference map (e.g. satellite) over the same ground.

Usage: ./match_colors.py photo_geo.tif satellite.tif [-o out.tif]
Per-channel histogram matching, computed only where both images overlap, then
applied to the full-resolution photo as a lookup table (detail is untouched).
"""
import argparse
import os
import numpy as np
from osgeo import gdal

gdal.UseExceptions()


def lut_for(src, ref):
    s_vals, s_cnt = np.unique(src, return_counts=True)
    r_vals, r_cnt = np.unique(ref, return_counts=True)
    s_cdf = np.cumsum(s_cnt) / src.size
    r_cdf = np.cumsum(r_cnt) / ref.size
    mapped = np.interp(s_cdf, r_cdf, r_vals)
    lut = np.interp(np.arange(256), s_vals, mapped)
    return np.clip(lut, 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("photo")
    ap.add_argument("reference")
    ap.add_argument("-o", "--out")
    ap.add_argument("--mode", choices=["tone", "full", "stable"], default="stable",
                    help="stable (default) = copy map colours using only ground that looks the same kind in both "
                         "(veg-veg, soil-soil; roofs/water/changed fields ignored). tone = brightness only. "
                         "full = copy all colours (breaks where the ground changed)")
    a = ap.parse_args()
    out = a.out or a.photo.replace("_geo.tif", "_matched_geo.tif")

    ph = gdal.Open(a.photo)
    gt = ph.GetGeoTransform()
    w, h = ph.RasterXSize, ph.RasterYSize
    te = [gt[0], gt[3] + h * gt[5], gt[0] + w * gt[1], gt[3]]
    # compare on a coarse common grid (1 m) - enough for colour statistics
    small = gdal.Warp("", a.photo, format="MEM", outputBounds=te, xRes=1, yRes=1, resampleAlg="average")
    ref = gdal.Warp("", a.reference, format="MEM", outputBounds=te, xRes=1, yRes=1,
                    dstSRS=ph.GetProjection(), resampleAlg="average")
    p = small.ReadAsArray()
    r = ref.ReadAsArray()[:3]
    mask = p[3] > 0 if p.shape[0] == 4 else np.ones(p.shape[1:], bool)
    mask &= r.sum(0) > 0
    if a.mode == "stable":
        def classes(x):
            x = x[:3].astype(np.float32)
            lum = x.mean(0)
            exg = (2 * x[1] - x[0] - x[2]) / (x.sum(0) + 1)
            c = np.where(exg > np.percentile(exg[mask], 60), 1, 2)  # 1 veg, 2 soil (relative to each image)
            c[lum > np.percentile(lum[mask], 97)] = 0  # roofs / glare
            c[lum < np.percentile(lum[mask], 3)] = 0   # water / deep shadow
            return c
        cp, cr = classes(p), classes(r)
        keep = mask & (cp == cr) & (cp > 0)
        print(f"stable ground used: {keep.sum() / mask.sum():.0%} of overlap", flush=True)
        luts = [lut_for(p[b][keep], r[b][keep]) for b in range(3)]
    elif a.mode == "full":
        luts = [lut_for(p[b][mask], r[b][mask]) for b in range(3)]
    else:
        # one shared curve from luminance, so hue/saturation stay the photo's own
        pl = p[:3].astype(np.float32).mean(0)[mask].round().astype(np.uint8)
        rl = r[:3].astype(np.float32).mean(0)[mask].round().astype(np.uint8)
        luts = [lut_for(pl, rl)] * 3

    drv = gdal.GetDriverByName("GTiff")
    dst = drv.Create(out, w, h, 4, gdal.GDT_Byte, ["COMPRESS=JPEG", "JPEG_QUALITY=92", "TILED=YES"])
    dst.SetGeoTransform(gt)
    dst.SetProjection(ph.GetProjection())
    for y0 in range(0, h, 1024):  # stream in strips to keep memory low
        rows = min(1024, h - y0)
        if a.mode == "tone":
            px = np.stack([ph.GetRasterBand(b + 1).ReadAsArray(0, y0, w, rows) for b in range(3)]).astype(np.float32)
            l = px.mean(0)
            li = np.clip(l.round(), 0, 255).astype(np.uint8)
            ratio = luts[0][li].astype(np.float32) / np.maximum(l, 1)
            px = np.clip(px * ratio, 0, 255).astype(np.uint8)
            for b in range(3):
                dst.GetRasterBand(b + 1).WriteArray(px[b], 0, y0)
        else:
            for b in range(3):
                dst.GetRasterBand(b + 1).WriteArray(luts[b][ph.GetRasterBand(b + 1).ReadAsArray(0, y0, w, rows)], 0, y0)
        dst.GetRasterBand(4).WriteArray(ph.GetRasterBand(4).ReadAsArray(0, y0, w, rows), 0, y0)
    for b in range(3):
        dst.GetRasterBand(b + 1).SetColorInterpretation([gdal.GCI_RedBand, gdal.GCI_GreenBand, gdal.GCI_BlueBand][b])
    dst.GetRasterBand(4).SetColorInterpretation(gdal.GCI_AlphaBand)
    dst.BuildOverviews("AVERAGE", [2, 4, 8, 16])
    dst = None
    print("matched ->", out, flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
