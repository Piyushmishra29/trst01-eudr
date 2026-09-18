"""Full-resolution DJI_0995 as a GeoTIFF (UTM 43N, 6 cm/px), placed with the viewer's alignment + seam spline."""
import subprocess, numpy as np
from geo import utm
SRC = "work/DJI_0995_enh.png"                              # enhance.py: dehazed + sharpened copy of the 48 MP original (8064 x 6048)
gcps = []
for v in np.linspace(0, 3024, 13):
    for u in np.linspace(0, 4032, 17):
        x, y = utm(u, v); gcps += ["-gcp", f"{u * 2:.1f}", f"{v * 2:.1f}", f"{float(x):.3f}", f"{float(y):.3f}"]
subprocess.run(["gdal_translate", "-q", "-a_srs", "EPSG:32643", *gcps, SRC, "work/gcp.tif"], check=True)
subprocess.run(["gdalwarp", "-q", "-overwrite", "-tps", "-r", "lanczos", "-tr", "0.06", "0.06", "-dstalpha", "-multi", "-wo", "NUM_THREADS=ALL_CPUS",
                "-co", "COMPRESS=DEFLATE", "-co", "PREDICTOR=2", "-co", "TILED=YES", "-co", "BIGTIFF=IF_SAFER", "work/gcp.tif", "work/bagalur_drone_0995.tif"], check=True)
