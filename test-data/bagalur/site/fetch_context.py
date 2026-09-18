"""Wide satellite context for the site model: Esri World Imagery, 16 x 16 km at 4 m/px around the 2 x 1.5 km block, on the same UTM 43N grid (work/context.tif)."""
import math, io, subprocess, requests, numpy as np
from PIL import Image
from pyproj import Transformer
CXU, CYU, HALF, Z = 808152.0 + 1000, 1418908.0 - 750, 8000, 15                       # block centre (UTM 43N), half-size in metres, tile zoom
lon0, lat0 = Transformer.from_crs(32643, 4326, always_xy=True).transform(CXU - HALF * 1.1, CYU - HALF * 1.1); lon1, lat1 = Transformer.from_crs(32643, 4326, always_xy=True).transform(CXU + HALF * 1.1, CYU + HALF * 1.1)
tx = lambda lon: int((lon + 180) / 360 * 2 ** Z); ty = lambda lat: int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * 2 ** Z)
x0, x1, y0, y1 = tx(lon0), tx(lon1), ty(lat1), ty(lat0); print((x1 - x0 + 1) * (y1 - y0 + 1), "tiles")
mos = Image.new("RGB", ((x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256)); s = requests.Session(); s.headers["User-Agent"] = "trst01-eudr site model (one-off context fetch)"
for x in range(x0, x1 + 1):
    for y in range(y0, y1 + 1):
        r = s.get(f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{Z}/{y}/{x}", timeout=30); r.raise_for_status(); mos.paste(Image.open(io.BytesIO(r.content)).convert("RGB"), ((x - x0) * 256, (y - y0) * 256))
mos.save("work/context_3857.png"); R = 20037508.342789244; res = 2 * R / 2 ** Z / 256
subprocess.run(["gdal_translate", "-q", "-a_srs", "EPSG:3857", "-a_ullr", str(-R + x0 * 256 * res), str(R - y0 * 256 * res), str(-R + (x1 + 1) * 256 * res), str(R - (y1 + 1) * 256 * res), "work/context_3857.png", "work/context_3857.tif"], check=True)
subprocess.run(["gdalwarp", "-q", "-overwrite", "-t_srs", "EPSG:32643", "-te", str(CXU - HALF), str(CYU - HALF), str(CXU + HALF), str(CYU + HALF), "-tr", "4", "4", "-r", "cubic", "work/context_3857.tif", "work/context.tif"], check=True)
