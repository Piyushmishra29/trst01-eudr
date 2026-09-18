"""Pick buildings out of the SAM 2.1 segments: raised in the AI depth, not vegetation, compact shape. -> web/buildings.json"""
import json, numpy as np, cv2
W, H = 4032, 3024
im = cv2.imread("web/tex_hd.jpg")
d = cv2.resize(np.load("work/d0995.npy").astype(np.float32), (W, H))
ground = cv2.GaussianBlur(cv2.erode(cv2.resize(d, (1008, 756)), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))), (0, 0), 20)
obj = np.clip(d - cv2.resize(ground, (W, H)), 0, None); obj /= np.percentile(obj, 99.7)
b, g, r = [c.astype(np.float32) for c in cv2.split(im)]
exg = (2 * g - r - b) / (r + g + b + 1)
hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
cands = []
for k in list(np.load("work/sam_masks.npy", allow_pickle=True)) + list(np.load("work/sam_pts.npy", allow_pickle=True)):
    h, w = k["shape"]; m = np.unpackbits(k["m"])[:h * w].reshape(h, w).astype(np.uint8)
    a = int(m.sum())
    if a < 1000 or a > 1.6e6: continue
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); c = max(cs, key=cv2.contourArea)
    rect = cv2.minAreaRect(c); ra = rect[1][0] * rect[1][1] + 1
    hull = cv2.contourArea(cv2.convexHull(c)) + 1
    sl = (slice(k["y"], k["y"] + h), slice(k["x"], k["x"] + w)); mb = m.astype(bool)
    pad = 40; y0, x0 = max(k["y"] - pad, 0), max(k["x"] - pad, 0)
    big = np.zeros((min(k["y"] + h + pad, H) - y0, min(k["x"] + w + pad, W) - x0), np.uint8); big[k["y"] - y0:k["y"] - y0 + h, k["x"] - x0:k["x"] - x0 + w] = m
    ring = (cv2.dilate(big, np.ones((2 * pad + 1,) * 2, np.uint8)) > 0) & (big == 0)
    o = obj[y0:y0 + big.shape[0], x0:x0 + big.shape[1]]
    cands.append(dict(x=int(k["x"]), y=int(k["y"]), a=a, rectness=a / ra, solid=a / hull, exg=float(exg[sl][mb].mean()), sat=float(hsv[..., 1][sl][mb].mean()), val=float(hsv[..., 2][sl][mb].mean()),
                      hin=float(np.median(obj[sl][mb])), hout=float(np.percentile(o[ring], 25)), cut=k["cut"], prompt=k.get("prompt", False), score=k["score"], c=(c + [k["x"], k["y"]]).reshape(-1, 2), asp=max(rect[1]) / (min(rect[1]) + 1)))
print(len(cands), "segments")
def ok(c):
    if c["prompt"]: return c["a"] < 4e5
    dh = c["hin"] - c["hout"]
    if c["solid"] < 0.86 or c["asp"] > 9 or c["exg"] > 0.06 or c["val"] < 115: return False      # dark blobs are orchard trees
    if c["rectness"] > 0.62 and dh > 0.10: return True
    return c["rectness"] > 0.78 and dh > 0.05 and c["val"] > 165 and c["sat"] < 50                # bright grey/white roofs the depth model underrates
keep = [c for c in cands if ok(c)]
print(len(keep), "building-like segments")
# whole segments first, small to large: skip duplicates and "containers" (roof + yard in one segment);
# then the pieces cut by tile edges, joined, where nothing whole already covers them
U = np.zeros((H, W), np.uint8); lab = np.zeros((H, W), np.int32); n = 1
for c in sorted([c for c in keep if not c["cut"]], key=lambda c: (not c["prompt"], c["a"])):   # prompted roofs first
    m = np.zeros((H, W), np.uint8); cv2.drawContours(m, [c["c"]], -1, 1, -1)
    if (U[m > 0] > 0).mean() > 0.35: continue
    lab[(m > 0) & (U == 0)] = n; n += 1; U |= m
C = np.zeros((H, W), np.uint8)
for c in keep:
    if c["cut"]: cv2.drawContours(C, [c["c"]], -1, 1, -1)
C = cv2.morphologyEx(C, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)) & (1 - cv2.dilate(U, np.ones((15, 15), np.uint8)))
nc, labc = cv2.connectedComponents(C)
for i in range(1, nc): lab[labc == i] = n; n += 1
U |= C
st = np.array([[0, 0, 0, 0, (lab == i).sum()] for i in range(n)])
out = []; vis = im.copy()
for i in range(1, n):
    if st[i, cv2.CC_STAT_AREA] < 1200: continue
    m = cv2.morphologyEx((lab == i).astype(np.uint8), cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    if m.sum() < 1200: continue
    c = max(cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0], key=cv2.contourArea)
    rect = cv2.minAreaRect(c); a = cv2.contourArea(c)
    poly = cv2.boxPoints(rect) if a / (rect[1][0] * rect[1][1]) > 0.88 else cv2.approxPolyDP(c, 0.012 * cv2.arcLength(c, True), True).reshape(-1, 2)
    ring = (cv2.dilate(m, np.ones((81, 81), np.uint8)) > 0) & (U == 0)
    dh = float(np.median(obj[m > 0]) - np.percentile(obj[ring], 25))
    out.append(dict(poly=[[round(float(x), 1), round(float(y), 1)] for x, y in poly], h=round(max(dh, 0.12), 3), area_m2=round(a * 0.0108, 0)))
    cv2.polylines(vis, [np.int32(poly)], True, (255, 0, 255), 5)
    cv2.putText(vis, f"{len(out)-1} h{dh:.2f}", tuple(np.int32(poly).min(0)), 0, 1.4, (0, 255, 255), 3)
print(len(out), "buildings")
cv2.imwrite("work/bld_vis.jpg", cv2.resize(vis, (2016, 1512)), [1, 85])
json.dump(dict(size=[W, H], buildings=out), open("web/buildings.json", "w"))
