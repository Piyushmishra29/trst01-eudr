"""Honest clean-up of DJI_0995 before tiling: remove the haze veil of a 350 m shot, lift local contrast, sharpen. Classical filters only:
nothing is invented, every pixel still comes from the photo (no AI super-resolution; that would not be evidence)."""
import cv2, numpy as np
SRC = "/media/piyushmishra/C141-8B20/DCIM/100MEDIA/DJI_0995.JPG"
def enhance(bgr):
    im = bgr.astype(np.float32) / 255
    # haze: subtract the per-channel veil (low percentile of a heavily blurred dark channel), then stretch to the white point
    veil = np.array([np.percentile(cv2.GaussianBlur(im[..., c], (0, 0), 25), 0.5) for c in range(3)]) * 0.85
    im = np.clip((im - veil) / (np.percentile(im, 99.7, axis=(0, 1)) - veil), 0, 1)
    lab = cv2.cvtColor((im * 255).astype(np.uint8), cv2.COLOR_BGR2LAB); L = lab[..., 0]
    L = cv2.addWeighted(L, 0.45, cv2.createCLAHE(clipLimit=1.8, tileGridSize=(12, 16)).apply(L), 0.55, 0)          # local contrast, half strength
    Lf = L.astype(np.float32); fine = Lf - cv2.GaussianBlur(Lf, (0, 0), 1.0); mid = Lf - cv2.GaussianBlur(Lf, (0, 0), 4.0)
    Lf = Lf + 0.7 * np.clip(fine, -12, 12) + 0.22 * np.clip(mid, -16, 16)                                         # clipped unsharp: crisp edges, no halos
    lab[..., 0] = np.clip(Lf, 0, 255).astype(np.uint8); lab[..., 1:] = cv2.GaussianBlur(lab[..., 1:], (0, 0), 1.6)      # the 48 MP quad-bayer sensor leaves colour noise: smooth colour only, never brightness
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
if __name__ == "__main__":
    out = enhance(cv2.imread(SRC)); cv2.imwrite("work/DJI_0995_enh.png", out)
    a = cv2.imread(SRC)[1300:1700, 2100:2700]; b = out[1300:1700, 2100:2700]; cv2.imwrite("work/enh_compare.jpg", np.vstack([a, b]), [cv2.IMWRITE_JPEG_QUALITY, 92])
