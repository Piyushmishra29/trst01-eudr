"""DJI_0995 -> sat grid, via SIFT against DJI_0001 (already aligned to the satellite) resampled onto the same grid."""
import cv2, numpy as np, json
ref = cv2.imread("sat/d0001_on_grid.png", cv2.IMREAD_UNCHANGED)   # BGRA
refrgb = ref[..., :3].copy(); alpha = ref[..., 3]
drone = cv2.imread("web/tex_hd.jpg"); hd, wd = drone.shape[:2]
gsd = 349.7 * (9.6 / 8064) / 6.72 * (8064 / wd)
s0 = gsd / 0.5
small = cv2.resize(drone, None, fx=s0, fy=s0, interpolation=cv2.INTER_AREA)
g = lambda im: cv2.createCLAHE(2.0, (8, 8)).apply(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
sift = cv2.SIFT_create(20000)
k1, d1 = sift.detectAndCompute(g(small), None)
k2, d2 = sift.detectAndCompute(g(refrgb), (alpha > 0).astype(np.uint8) * 255)
m = cv2.BFMatcher().knnMatch(d1, d2, k=2)
good = [a for a, b in m if a.distance < 0.75 * b.distance]
p1 = np.float32([k1[a.queryIdx].pt for a in good]) / s0
p2 = np.float32([k2[a.trainIdx].pt for a in good])
A, inl = cv2.estimateAffinePartial2D(p1, p2, method=cv2.RANSAC, ransacReprojThreshold=3, maxIters=20000)
inl = inl[:, 0] == 1
res = np.linalg.norm(p1[inl] @ A[:, :2].T + A[:, 2] - p2[inl], axis=1) * 0.5
sc = float(np.hypot(A[0, 0], A[1, 0])) / s0; rot = float(np.degrees(np.arctan2(A[1, 0], A[0, 0])))
print(f"matches {len(good)}  inliers {inl.sum()}  scale {sc:.3f}  rot {rot:.2f} deg  median err {np.median(res):.2f} m")
sat = cv2.imread("sat/sat_wide.png"); Hs, Ws = sat.shape[:2]
json.dump({"A": A.tolist(), "sat_px_m": 0.5, "sat_size": [Ws, Hs], "drone_size": [wd, hd],
           "inliers": int(inl.sum()), "median_err_m": float(np.median(res))}, open("sat/align.json", "w"), indent=1)
warp = cv2.warpAffine(drone, A, (Ws, Hs)); mask = cv2.warpAffine(np.full((hd, wd), 255, np.uint8), A, (Ws, Hs))
yy, xx = np.mgrid[:Hs, :Ws]; cb = ((xx // 120 + yy // 120) % 2 == 0) & (mask > 0)
out = sat.copy(); out[cb] = warp[cb]
x0, y0, w, h = cv2.boundingRect(mask)
cv2.imwrite("sat/check.jpg", out[max(0, y0 - 150):y0 + h + 150, max(0, x0 - 150):x0 + w + 150], [cv2.IMWRITE_JPEG_QUALITY, 85])
