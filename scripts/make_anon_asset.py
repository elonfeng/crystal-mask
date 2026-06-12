# -*- coding: utf-8 -*-
"""把正脸面具照(assets/anon_src.png)处理成"完整面具网格"用素材：
  - 面具图检测 478 关键点(取前468) = 贴图坐标 UV
  - 官方人脸网格拓扑(898 三角)
  - 沿脸轮廓(face oval)向外测到面具真实边缘 -> 每点延伸比例 ratio
    (用来补全脸缘外的白色塑料外沿: 额头顶/两颊/下巴底, 让面具完整闭合)
  -> assets/anon_rig3d.npz (uv, tris, oval, ratios)；纹理用 anon_src.png

用法: 面具图放到 assets/anon_src.png, 然后 python scripts/make_anon_asset.py
"""
import os
import sys

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from src.tracker import ensure_model

SRC = "assets/anon_src.png"
# 脸轮廓(有序闭环)
OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379,
        378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127,
        162, 21, 54, 103, 67, 109]


def load_canonical_tris(path):
    tris = []
    with open(path) as f:
        for line in f:
            if line.startswith('f '):
                tris.append([int(t.split('/')[0]) - 1 for t in line.split()[1:4]])
    return np.array(tris, np.int32)


def silhouette(img):
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    th = (gray > 38).astype(np.uint8) * 255
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    ncc, lab, stats, _ = cv2.connectedComponentsWithStats(th)
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    body = (lab == big).astype(np.uint8) * 255
    ff = body.copy()
    cv2.floodFill(ff, np.zeros((H + 2, W + 2), np.uint8), (0, 0), 255)
    return cv2.bitwise_or(body, cv2.bitwise_not(ff))


def main():
    if not os.path.exists(SRC):
        print(f"[err] 缺少 {SRC}（把面具照命名为 anon_src.png 放进 assets/）")
        sys.exit(1)
    ensure_model(config.MODEL_PATH, config.MODEL_URL)
    ensure_model(config.CANON_OBJ, config.CANON_URL)
    img = cv2.imread(SRC)
    H, W = img.shape[:2]
    sil = silhouette(img)

    base = python.BaseOptions(model_asset_path=config.MODEL_PATH)
    lm = vision.FaceLandmarker.create_from_options(
        vision.FaceLandmarkerOptions(base_options=base, num_faces=1))
    res = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                             data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
    if not res.face_landmarks:
        print("[err] 面具图上没检测到人脸，换一张更清晰的正脸面具照")
        sys.exit(1)
    uv = np.array([[l.x * W, l.y * H] for l in res.face_landmarks[0]], np.float32)[:468]
    tris = load_canonical_tris(config.CANON_OBJ)

    cen = uv.mean(0)
    ratios = []
    for idx in OVAL:
        d = uv[idx] - cen
        L = float(np.linalg.norm(d))
        if L < 1:
            ratios.append(1.0)
            continue
        u = d / L
        r_edge = L
        r = L
        while r < L * 2.3:                       # 从轮廓点向外测到面具边缘(剪影外缘)
            px, py = cen + u * r
            if 0 <= int(px) < W and 0 <= int(py) < H and sil[int(py), int(px)] > 0:
                r_edge = r
                r += 2
            else:
                break
        ratios.append(min(2.3, max(1.0, r_edge / L)))

    # 闭环平滑 + 下限: 消除下巴/边缘的凹口, 让外沿平滑闭合
    ratios = np.maximum(np.array(ratios, np.float32), 1.08)
    n = len(ratios)
    sm = np.array([ratios[(np.arange(i - 2, i + 3)) % n].mean() for i in range(n)], np.float32)
    ratios = sm

    np.savez("assets/anon_rig3d.npz", uv=uv, tris=tris,
             oval=np.array(OVAL, np.int32), ratios=ratios)
    print(f"[ok] anon_rig3d.npz  锚点468 三角{len(tris)} 轮廓{len(OVAL)} "
          f"延伸比例{np.round(np.array(ratios), 2).tolist()}")


if __name__ == "__main__":
    main()
