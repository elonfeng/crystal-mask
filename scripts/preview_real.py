# -*- coding: utf-8 -*-
"""用真实人脸照跑 FaceLandmarker，渲染新晶体面具，导出预览(含正脸/张嘴/侧脸炸裂)。"""
import os
import sys
import numpy as np
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from src.renderer import CrystalRenderer, load_canonical_model

W, H = config.WIDTH, config.HEIGHT

base = python.BaseOptions(model_asset_path=config.MODEL_PATH)
opts = vision.FaceLandmarkerOptions(base_options=base, num_faces=1,
                                    output_face_blendshapes=True)
lm = vision.FaceLandmarker.create_from_options(opts)

img = cv2.imread('/tmp/face.jpg')
img = cv2.resize(img, (W, H))
rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
res = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
assert res.face_landmarks, "没检测到人脸"
lms = np.array([[l.x, l.y, l.z] for l in res.face_landmarks[0]], np.float32)
print("landmarks:", lms.shape)

r = CrystalRenderer(W, H)
verts_c, tris_c = load_canonical_model(config.CANON_OBJ)
pts2d = np.stack([lms[:, 0] * W, lms[:, 1] * H], 1)
r.set_tri(tris_c, pts2d, verts_c)


def compose(lms3d, warm=0.0, shatter=0.0, jaw=0.0):
    canvas = np.zeros((H, W, 3), np.uint8)
    glow = np.zeros((H, W, 3), np.uint8)
    edge = np.zeros((H, W, 3), np.uint8)
    r.draw(canvas, glow, edge, lms3d, warm, shatter, jaw)
    bloom = cv2.GaussianBlur(glow, (0, 0), config.BLOOM_SIGMA)
    out = cv2.add(canvas, glow)
    out = cv2.add(out, (bloom * config.BLOOM_STRENGTH).astype(np.uint8))
    out = cv2.add(out, edge)
    return out


cv2.imwrite('/tmp/cm_front.png', compose(lms))
# 张嘴：把下唇区域往下推一点，并给 jaw 让口腔挖空
open_lms = lms.copy()
open_lms[[14, 17, 84, 314, 87, 317, 178, 402], 1] += 0.05
cv2.imwrite('/tmp/cm_open.png', compose(open_lms, jaw=0.6))
cv2.imwrite('/tmp/cm_shatter.png', compose(lms, shatter=1.0))
print("saved /tmp/cm_front.png /tmp/cm_open.png /tmp/cm_shatter.png")
