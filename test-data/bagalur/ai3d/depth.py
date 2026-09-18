import torch, numpy as np, sys
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForDepthEstimation
src, out = sys.argv[1], sys.argv[2]
im = Image.open(src).convert("RGB")
mid = "depth-anything/Depth-Anything-V2-Large-hf"
proc = AutoImageProcessor.from_pretrained(mid)
model = AutoModelForDepthEstimation.from_pretrained(mid, torch_dtype=torch.float16).cuda().eval()
H, Wd = 1512, 2016  # multiples of 14, 4:3
x = proc(images=im, return_tensors="pt", size={"height": H, "width": Wd}, do_resize=True, keep_aspect_ratio=False)["pixel_values"].cuda().half()
with torch.no_grad():
    d = model(pixel_values=x).predicted_depth[0].float().cpu().numpy()
print("depth", d.shape, d.min(), d.max(), torch.cuda.max_memory_allocated()/1e9, "GB")
np.save(out + ".npy", d)
v = (d - np.percentile(d, 1)) / (np.percentile(d, 99.5) - np.percentile(d, 1))
Image.fromarray((np.clip(v, 0, 1) * 65535).astype(np.uint16)).save(out + "_16.png")
Image.fromarray((np.clip(v, 0, 1) * 255).astype(np.uint8)).save(out + "_8.png")
