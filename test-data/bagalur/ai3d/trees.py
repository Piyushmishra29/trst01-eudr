"""Tree crowns with DeepForest (open source, weecology). Photo at 4032 px is ~10 cm/px = the model's training scale."""
import json, numpy as np, cv2, torch
from deepforest import main
m = main.deepforest(); m.load_model("weecology/deepforest-tree")
m.config.score_thresh = 0.15
if torch.cuda.is_available(): m.model.to("cuda")
im = cv2.cvtColor(cv2.imread("web/tex_hd.jpg"), cv2.COLOR_BGR2RGB)
df = m.predict_tile(image=im, patch_size=500, patch_overlap=0.25, iou_threshold=0.3)
df = df[["xmin", "ymin", "xmax", "ymax", "score"]].round(2)
df.to_csv("work/trees.csv", index=False)
print(len(df), "crowns; score quantiles", df.score.quantile([.1, .5, .9]).tolist())
vis = cv2.cvtColor(im, cv2.COLOR_RGB2BGR)
for r in df.itertuples():
    cv2.ellipse(vis, (int((r.xmin + r.xmax) / 2), int((r.ymin + r.ymax) / 2)), (int((r.xmax - r.xmin) / 2), int((r.ymax - r.ymin) / 2)), 0, 0, 360, (0, 255, 255) if r.score > .3 else (0, 120, 255), 2)
cv2.imwrite("work/trees_vis.jpg", cv2.resize(vis, (2016, 1512)), [1, 85])
