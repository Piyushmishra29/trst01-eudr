"""The 500 m overview photo (DJI_0001, 8.7 cm/px) as a second drone layer: it covers the whole estate out to the highway, where the 350 m photo stops.
Same honest clean-up as enhance.py, then warped onto the viewer's world grid using the georeferenced copy in ../raw (made earlier from the RAW file; the JPG has the better colour,
so the JPG is matched to that copy and takes its place). Output: work/wide_enh.png + work/wide.json (world extent)."""
import json, cv2, numpy as np
from enhance import enhance
SRC = "/media/piyushmishra/C141-8B20/DCIM/101MEDIA/DJI_0001.JPG"; REF = "../raw/DJI_0001_final2_geo.tif"; X0, Y1, SW, SH, PX = 808152.0, 1418908.0, 4000, 3000, 0.5
r4 = cv2.imread("work/wide_ref.png", cv2.IMREAD_UNCHANGED); ref, alpha = r4[..., :3], r4[..., 3]; G = json.load(open("work/wide_ref.json")); gt = G["gt"]; RW, RH = G["size"]      # gdal_translate -of PNG ../raw/DJI_0001_final2_geo.tif work/wide_ref.png ; gdalinfo -json -> wide_ref.json
jpg = cv2.imread(SRC); k = 0.25; a = cv2.cvtColor(cv2.resize(jpg, None, fx=k, fy=k, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY); b = cv2.cvtColor(cv2.resize(ref, None, fx=k, fy=k, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
sift = cv2.SIFT_create(12000); ka, da = sift.detectAndCompute(a, None); kb, db = sift.detectAndCompute(b, cv2.resize(alpha, None, fx=k, fy=k))
m = [p for p, q in cv2.BFMatcher().knnMatch(da, db, k=2) if p.distance < 0.7 * q.distance]
A = np.float32([ka[p.queryIdx].pt for p in m]) / k; B = np.float32([kb[p.trainIdx].pt for p in m]) / k; H, inl = cv2.findHomography(A, B, cv2.RANSAC, 3.0)
res = np.linalg.norm(cv2.perspectiveTransform(A[None], H)[0] - B, axis=1)[inl.ravel() > 0]; print(len(m), "matches,", int(inl.sum()), "inliers, residual px median/95%:", round(float(np.median(res)), 2), round(float(np.percentile(res, 95)), 2))
wx0, wz0 = gt[0] - X0 - SW * PX / 2, Y1 - gt[3] - SH * PX / 2; wx1, wz1 = wx0 + RW * gt[1], wz0 + RH * gt[1]      # world extent of the reference grid
out = cv2.warpPerspective(enhance(jpg), H, (RW, RH), flags=cv2.INTER_LANCZOS4); valid = cv2.warpPerspective(np.full(jpg.shape[:2], 255, np.uint8), H, (RW, RH))
cv2.imwrite("work/wide_enh.png", out); cv2.imwrite("work/wide_valid.png", valid); json.dump(dict(x0=wx0, z0=wz0, x1=wx1, z1=wz1, m_per_px=gt[1]), open("work/wide.json", "w")); print("world extent", round(wx0), round(wz0), round(wx1), round(wz1))
