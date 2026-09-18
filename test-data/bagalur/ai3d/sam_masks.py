"""All segments with SAM 2.1 (open source, Meta) -> work/sam_masks.npz. Buildings are picked from these in buildings.py."""
import numpy as np, torch, cv2
from PIL import Image
from transformers import pipeline
gen = pipeline("mask-generation", model="facebook/sam2.1-hiera-large", device=0)
im = Image.open("web/tex_hd.jpg").convert("RGB")
W, H = im.size
out = []
T, S = 1600, 1216                                   # overlapping tiles so small sheds keep enough pixels
for y0 in range(0, H - 200, S):
    for x0 in range(0, W - 200, S):
        x1, y1 = min(x0 + T, W), min(y0 + T, H)
        r = gen(im.crop((x0, y0, x1, y1)), points_per_batch=12, points_per_crop=32, pred_iou_thresh=0.8, stability_score_thresh=0.9)
        for m, s in zip(r["masks"], r["scores"]):
            m = np.asarray(m, bool)
            if m.sum() < 400: continue
            ys, xs = np.where(m)
            bx = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
            touches = bx[0] == 0 and x0 > 0 or bx[1] == 0 and y0 > 0 or bx[2] == x1 - x0 and x1 < W or bx[3] == y1 - y0 and y1 < H
            out.append(dict(x=x0 + bx[0], y=y0 + bx[1], m=np.packbits(m[bx[1]:bx[3], bx[0]:bx[2]]), shape=(bx[3] - bx[1], bx[2] - bx[0]), score=float(s), cut=bool(touches)))
        print(x0, y0, len(out), flush=True)
np.save("work/sam_masks.npy", np.array(out, dtype=object), allow_pickle=True)
