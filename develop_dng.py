#!/usr/bin/env python3
"""Develop a DJI DNG with its as-shot camera white balance (no in-camera JPG styling).
Run with the venv: .venv/bin/python develop_dng.py in.DNG out.tif"""
import sys
import rawpy
from PIL import Image

with rawpy.imread(sys.argv[1]) as raw:
    rgb = raw.postprocess(use_camera_wb=True, output_color=rawpy.ColorSpace.sRGB,
                          output_bps=8, no_auto_bright=False, auto_bright_thr=0.001,
                          demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD)
Image.fromarray(rgb).save(sys.argv[2], compression="tiff_lzw")
print(f"developed {rgb.shape[1]}x{rgb.shape[0]} -> {sys.argv[2]}")
