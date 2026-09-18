"""Shared geometry for the site-model scripts: drone photo px <-> the viewer's world metres (x east, z south, origin = satellite block centre)."""
import json, numpy as np
from pyproj import Transformer
AL = json.load(open("../ai3d/web/align.json")); S = json.load(open("../ai3d/web/seam.json")); A = np.array(AL["A"]); D = np.array(S["d"], float); GX, GY = S["gx"], S["gy"]
SW, SH = AL["sat_size"]; PX = AL["sat_px_m"]; DW, DH = AL["drone_size"]; X0, Y1 = 808152.0, 1418908.0                 # satellite block: UTM 43N top-left corner
T = Transformer.from_crs(4326, 32643, always_xy=True)
def world_ll(lon, lat): x, y = T.transform(lon, lat); return [round((x - X0) - SW * PX / 2, 2), round((Y1 - y) - SH * PX / 2, 2)]      # x east, z south, origin = block centre
def world_px(u, v):
    fx, fy = min(max(u / DW * (GX - 1), 0), GX - 1.001), min(max(v / DH * (GY - 1), 0), GY - 1.001); ix, iy = int(fx), int(fy); tx, ty = fx - ix, fy - iy
    d = (D[iy, ix] * (1 - tx) + D[iy, ix + 1] * tx) * (1 - ty) + (D[iy + 1, ix] * (1 - tx) + D[iy + 1, ix + 1] * tx) * ty
    X = A[0, 0] * u + A[0, 1] * v + A[0, 2] + d[0]; Y = A[1, 0] * u + A[1, 1] * v + A[1, 2] + d[1]; return [round((X - SW / 2) * PX, 2), round((Y - SH / 2) * PX, 2)]
M2 = np.linalg.inv(A[:, :2])
def photo_px(x, z):                                        # world metres -> drone photo px (inverse of world_px, seam included)
    X, Y = x / PX + SW / 2, z / PX + SH / 2; u, v = M2 @ (np.array([X, Y]) - A[:, 2])
    for _ in range(3):
        fx, fy = min(max(u / DW * (GX - 1), 0), GX - 1.001), min(max(v / DH * (GY - 1), 0), GY - 1.001); ix, iy = int(fx), int(fy); tx, ty = fx - ix, fy - iy
        d = (D[iy, ix] * (1 - tx) + D[iy, ix + 1] * tx) * (1 - ty) + (D[iy + 1, ix] * (1 - tx) + D[iy + 1, ix + 1] * tx) * ty; u, v = M2 @ (np.array([X, Y]) - A[:, 2] - d)
    return u, v
