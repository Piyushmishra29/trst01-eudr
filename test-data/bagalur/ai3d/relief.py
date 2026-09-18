import numpy as np, cv2
from PIL import Image
d = np.load("d0995.npy").astype(np.float32)          # relative inverse depth, higher = closer
# ground = low envelope: min filter then smooth -> removes the fake large-scale tilt
k = 61
ground = cv2.erode(d, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
ground = cv2.GaussianBlur(ground, (0, 0), 40)
obj = np.clip(d - ground, 0, None)                  # trees, sheds, polyhouses
obj = cv2.GaussianBlur(obj, (0, 0), 1.6)
obj = np.sqrt(obj * obj.max()) * 0.5 + obj * 0.5   # rounder crowns, flatter sides
h = obj / np.percentile(obj, 99.7)                   # 0..~1
h = np.clip(h, 0, 1.2) + 0.08 * (ground - ground.min()) / (np.ptp(ground) + 1e-6)  # keep a hint of real terrain (quarry pit)
h = h / h.max()
Image.fromarray((h * 65535).astype(np.uint16)).save("height16.png")
Image.fromarray((h * 255).astype(np.uint8)).save("height8.png")
# texture: 4032 wide, mild dehaze/contrast
im = cv2.imread("/media/piyushmishra/C141-8B20/DCIM/100MEDIA/DJI_0995.JPG")
im = cv2.resize(im, (4032, 3024), interpolation=cv2.INTER_AREA)
lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB); l, a, b = cv2.split(lab)
l = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 8)).apply(l)
im = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
cv2.imwrite("tex.jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 86])
print("ok", h.shape)
