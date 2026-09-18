"""Local drone-vs-satellite offsets (edge phase-correlation in 80 m tiles, reaching into the edges),
outliers rejected against a smooth quadratic, then a smoothed thin-plate spline sampled on a
33x25 grid over the photo. The viewer adds that grid to the mesh so roads meet the satellite cleanly."""
import cv2, numpy as np, json
from scipy.interpolate import RBFInterpolator
al = json.load(open("sat/align.json")); A = np.array(al["A"], np.float32)
sat = cv2.imread("sat/sat_wide.png"); Hs, Ws = sat.shape[:2]
drone = cv2.imread("web/tex_hd.jpg"); hd, wd = drone.shape[:2]
def edges(im):
    g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 1.2)
    m = cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    return m / (np.percentile(m, 99) + 1e-6)
warp = cv2.warpAffine(drone, A, (Ws, Hs), flags=cv2.INTER_AREA)
mask = cv2.warpAffine(np.full((hd, wd), 255, np.uint8), A, (Ws, Hs), flags=cv2.INTER_NEAREST)
es, ed = edges(sat), edges(warp)
T, step = 160, 50
win = cv2.createHanningWindow((T, T), cv2.CV_32F)
pts, offs, conf = [], [], []
for y in range(0, Hs - T, step):
    for x in range(0, Ws - T, step):
        cov = (mask[y:y + T, x:x + T] > 0).mean()
        if cov < 0.9: continue
        m = (mask[y:y + T, x:x + T] > 0).astype(np.float32)
        (dx, dy), r = cv2.phaseCorrelate(es[y:y + T, x:x + T] * win * m, ed[y:y + T, x:x + T] * win * m)
        if r > 0.06 and abs(dx) < 24 and abs(dy) < 24:
            pts.append((x + T / 2, y + T / 2)); offs.append((-dx, -dy)); conf.append(r)
pts, offs, conf = np.array(pts), np.array(offs), np.array(conf)
def design(p):
    x = (p[:, 0] - Ws / 2) / Ws; y = (p[:, 1] - Hs / 2) / Hs
    return np.stack([np.ones_like(x), x, y, x * x, x * y, y * y], 1)
best = None; rng = np.random.default_rng(0)
for _ in range(4000):
    idx = rng.choice(len(pts), 8, replace=False)
    c, *_ = np.linalg.lstsq(design(pts[idx]), offs[idx], rcond=None)
    inl = np.hypot(*(design(pts) @ c - offs).T) < 4.0
    if best is None or inl.sum() > best[1].sum(): best = (c, inl)
inl = best[1]
print(f"{len(pts)} tiles, {inl.sum()} consistent; raw offsets median {np.median(np.hypot(*offs[inl].T))*0.5:.2f} m, max {np.hypot(*offs[inl].T).max()*0.5:.2f} m")
tps = RBFInterpolator(pts[inl], offs[inl], kernel="thin_plate_spline", smoothing=10000.0, degree=1)
res = np.hypot(*(tps(pts[inl]) - offs[inl]).T) * 0.5
print(f"spline residual median {np.median(res):.2f} m, 90% {np.percentile(res, 90):.2f} m")
# sample the correction on a grid over the photo (drone uv), in satellite pixels
GX, GY = 33, 25
uu, vv = np.meshgrid(np.linspace(0, wd, GX), np.linspace(0, hd, GY))
P = np.stack([uu.ravel(), vv.ravel()], 1) @ A[:, :2].T + A[:, 2]
G = tps(P).reshape(GY, GX, 2)
json.dump({"gx": GX, "gy": GY, "d": np.round(G, 2).tolist(), "note": "sat-px offset at drone uv grid (u: 0..W, v: 0..H)"}, open("web/seam.json", "w"))
# check image: corrected drone over satellite, zooms at the four edges
dense = RBFInterpolator(pts[inl], offs[inl], kernel="thin_plate_spline", smoothing=10000.0, degree=1)
x0, y0, bw, bh = cv2.boundingRect(mask)
ys, xs = np.mgrid[y0 - 60:y0 + bh + 60:4, x0 - 60:x0 + bw + 60:4]
D = dense(np.stack([xs.ravel(), ys.ravel()], 1)).reshape(ys.shape + (2,)).astype(np.float32)
Dfull = cv2.resize(D, (xs.shape[1] * 4, xs.shape[0] * 4), interpolation=cv2.INTER_LINEAR)
H2, W2 = Dfull.shape[:2]
gy, gx = np.mgrid[y0 - 60:y0 - 60 + H2, x0 - 60:x0 - 60 + W2].astype(np.float32)
mx, my = gx - Dfull[..., 0], gy - Dfull[..., 1]
w2 = cv2.remap(warp, mx, my, cv2.INTER_LINEAR); m2 = cv2.remap(mask, mx, my, cv2.INTER_NEAREST)
crop = sat[y0 - 60:y0 - 60 + H2, x0 - 60:x0 - 60 + W2].copy(); crop[m2 > 0] = w2[m2 > 0]
cnt, _ = cv2.findContours(m2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); cv2.drawContours(crop, cnt, -1, (0, 210, 255), 1)
cv2.imwrite("sat/seam_after_tps.jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 88])
