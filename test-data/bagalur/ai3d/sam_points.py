"""Second pass: SAM 2.1 prompted with one click per roof the automatic pass missed -> work/sam_pts.npy"""
import numpy as np, torch
from PIL import Image
from transformers import Sam2Model, Sam2Processor
DEV = "cpu"   # 12 clicks only; keeps clear of whatever else is on the GPU
PTS = [(2370, 1480), (2370, 1580), (2950, 365), (2040, 2940), (2160, 2900), (2950, 2700), (3230, 2700), (3420, 2560), (3800, 3000), (3870, 2200), (2330, 1100), (2900, 1140)]
BOXES = [(2335, 1365, 2440, 1505), (3180, 2500, 3300, 2790), (3750, 2130, 4031, 2370)]   # roofs a click alone splits up
proc = Sam2Processor.from_pretrained("facebook/sam2.1-hiera-large"); model = Sam2Model.from_pretrained("facebook/sam2.1-hiera-large").to(DEV).eval()
im = Image.open("web/tex_hd.jpg").convert("RGB"); W, H = im.size; out = []
for p in PTS + BOXES:
    px, py = (p if len(p) == 2 else ((p[0] + p[2]) // 2, (p[1] + p[3]) // 2))
    x0, y0 = int(np.clip(px - 800, 0, W - 1600)), int(np.clip(py - 800, 0, H - 1600))
    crop = im.crop((x0, y0, x0 + 1600, y0 + 1600))
    kw = dict(input_points=[[[[px - x0, py - y0]]]], input_labels=[[[1]]]) if len(p) == 2 else dict(input_boxes=[[[p[0] - x0, p[1] - y0, p[2] - x0, p[3] - y0]]])
    inp = proc(images=crop, return_tensors="pt", **kw).to(DEV)
    with torch.no_grad(): o = model(**inp)
    ms = proc.post_process_masks(o.pred_masks.cpu(), inp["original_sizes"])[0][0].numpy() > 0
    sc = o.iou_scores[0, 0].cpu().numpy()
    a = ms.reshape(3, -1).sum(1); i = int(np.argmax(sc * (a < 6e5)))      # best mask that is not the whole scene
    m = ms[i]; ys, xs = np.where(m)
    print((px, py), "area", int(a[i]), "score", round(float(sc[i]), 2), [int(v) for v in a])
    out.append(dict(x=x0 + xs.min(), y=y0 + ys.min(), m=np.packbits(m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]), shape=(ys.max() - ys.min() + 1, xs.max() - xs.min() + 1), score=float(sc[i]), cut=False, prompt=True))
np.save("work/sam_pts.npy", np.array(out, dtype=object), allow_pickle=True)
