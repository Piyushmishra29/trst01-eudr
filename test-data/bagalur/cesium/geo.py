"""Drone pixel (4032-wide DJI_0995) -> lon/lat, through the same placement the 3D viewer uses (align.json + seam.json)."""
import json, numpy as np
from pyproj import Transformer
_AL = json.load(open("../ai3d/web/align.json")); _S = json.load(open("../ai3d/web/seam.json"))
A = np.array(_AL["A"]); D = np.array(_S["d"], np.float64); GX, GY = _S["gx"], _S["gy"]; DW, DH = _AL["drone_size"]
X0, Y1, PX = 808152.0, 1418908.0, 0.5                      # satellite grid: UTM 43N, top-left corner, m per px
_T = Transformer.from_crs(32643, 4326, always_xy=True)
def seam(u, v):
    fx, fy = np.clip(u / DW * (GX - 1), 0, GX - 1.001), np.clip(v / DH * (GY - 1), 0, GY - 1.001)
    ix, iy = np.floor(fx).astype(int), np.floor(fy).astype(int); tx, ty = (fx - ix)[..., None], (fy - iy)[..., None]
    return (D[iy, ix] * (1 - tx) + D[iy, ix + 1] * tx) * (1 - ty) + (D[iy + 1, ix] * (1 - tx) + D[iy + 1, ix + 1] * tx) * ty
def utm(u, v):
    u, v = np.asarray(u, float), np.asarray(v, float); d = seam(u, v)
    X = A[0, 0] * u + A[0, 1] * v + A[0, 2] + d[..., 0]; Y = A[1, 0] * u + A[1, 1] * v + A[1, 2] + d[..., 1]
    return X0 + X * PX, Y1 - Y * PX
def lonlat(u, v):
    return _T.transform(*utm(u, v))
if __name__ == "__main__":
    print(lonlat([0, 4032, 2016], [0, 3024, 1512]))
