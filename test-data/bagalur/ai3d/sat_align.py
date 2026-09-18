"""Place DJI_0995 on the Esri satellite block: GPS/yaw first guess, then edge phase-correlation + ECC refine."""
import cv2, numpy as np, json, math
sat = cv2.imread("sat/sat_wide.tif")                      # 4000x3000, 0.5 m/px, centred on the photo GPS
drone = cv2.imread("web/tex_hd.jpg")                      # 4032x3024 of DJI_0995
Hs, Ws = sat.shape[:2]; hd, wd = drone.shape[:2]
gsd = 349.7 * (9.6 / 8064) / 6.72 * (8064 / wd)           # m per tex_hd pixel (height above take-off)
# image (u,v) -> metres east/north of centre -> sat px
def guess(scale=1.0, yaw=0.0):
    g = gsd * scale / 0.5
    c, s = math.cos(yaw), math.sin(yaw)
    # dx = (u-wd/2)*g, dy_up = -(v-hd/2)*g ; E = dx c + dy s ; N = -dx s + dy c ; X = W/2 + E ; Y = H/2 - N
    a = np.array([[g * c, -g * s], [g * s, g * c]])
    t = np.array([Ws / 2, Hs / 2]) - a @ np.array([wd / 2, hd / 2])
    return np.hstack([a, t[:, None]]).astype(np.float32)
def edges(im):
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g = cv2.GaussianBlur(g, (0, 0), 1.5)
    m = cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    return m / (np.percentile(m, 99) + 1e-6)
es = edges(sat)
best = None
ed_full = edges(drone)
for yd in (0, 90, -90, 180):   # XMP yaw was -90.6 but the frame looks north-up: test all four
  for sc in np.arange(0.90, 1.12, 0.04):                   # take-off vs ground height is unknown
    for dr in (-4, -2, 0, 2, 4):
        A = guess(sc, math.radians(yd)); R = cv2.getRotationMatrix2D((Ws / 2, Hs / 2), dr, 1.0)
        A = (np.vstack([R, [0, 0, 1]]) @ np.vstack([A, [0, 0, 1]]))[:2].astype(np.float32)
        ew = cv2.warpAffine(ed_full, A, (Ws, Hs))
        mk = cv2.warpAffine(np.ones((hd, wd), np.float32), A, (Ws, Hs))
        win = cv2.createHanningWindow((Ws, Hs), cv2.CV_32F)
        (sx, sy), r = cv2.phaseCorrelate(es * win, ew * win)
        if best is None or r > best[0]:
            best = (r, sc, dr, sx, sy, A, yd)
r, sc, dr, sx, sy, A, yd = best
print('yaw', yd)
A[:, 2] -= (sx, sy)
print(f"coarse: scale {sc:.2f} rot {dr:+.1f} deg shift {sx*0.5:+.1f},{sy*0.5:+.1f} m  peak {r:.3f}")
# ECC refine (affine) at half res
f = 0.5
es_s = cv2.resize(es, None, fx=f, fy=f); ed_s = cv2.resize(edges(drone), None, fx=f * 1, fy=f * 1)
S = np.diag([f, f, 1.0]); Si = np.diag([1 / f, 1 / f, 1.0])
A0 = (S @ np.vstack([A, [0, 0, 1]]) @ Si)[:2].astype(np.float32)
try:
    _, W = cv2.findTransformECC(es_s, ed_s, cv2.invertAffineTransform(A0), cv2.MOTION_AFFINE,
                                (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 300, 1e-6), None, 5)
    A1 = cv2.invertAffineTransform(W)
    A = (Si @ np.vstack([A1, [0, 0, 1]]) @ S)[:2].astype(np.float32)
    print("ECC ok")
except cv2.error as e:
    print("ECC failed, keeping coarse", e)
scale = float(np.hypot(A[0, 0], A[1, 0])) * 0.5 / gsd; rot = float(np.degrees(np.arctan2(A[1, 0], A[0, 0])))
print(f"final: scale vs GPS height {scale:.3f}, rotation {rot:.2f} deg")
json.dump({"A": A.tolist(), "sat_px_m": 0.5, "sat_size": [Ws, Hs], "drone_size": [wd, hd]}, open("sat/align.json", "w"), indent=1)
warp = cv2.warpAffine(drone, A, (Ws, Hs))
mask = cv2.warpAffine(np.full((hd, wd), 255, np.uint8), A, (Ws, Hs))
yy, xx = np.mgrid[:Hs, :Ws]
cb = ((xx // 120 + yy // 120) % 2 == 0) & (mask > 0)
out = sat.copy(); out[cb] = warp[cb]
cv2.imwrite("sat/check.jpg", cv2.resize(out, (2000, 1500)), [cv2.IMWRITE_JPEG_QUALITY, 85])
