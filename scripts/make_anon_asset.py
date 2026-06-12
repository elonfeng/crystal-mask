# -*- coding: utf-8 -*-
"""把一张正脸面具照(assets/anon_src.png, 黑/暗背景)抠成透明背景, 并自动定位两只眼洞当锚点。
生成 assets/anon_mask.png(RGBA) + assets/anon_anchors.json, 供 anon.py 使用。

用法: 把你的面具图放到 assets/anon_src.png, 然后:
    python scripts/make_anon_asset.py
"""
import json
import os
import sys

import cv2
import numpy as np

SRC = "assets/anon_src.png"
OUT = "assets/anon_mask.png"
ANC = "assets/anon_anchors.json"


def main():
    if not os.path.exists(SRC):
        print(f"[err] 缺少 {SRC}（把你的面具照命名为 anon_src.png 放进 assets/）")
        sys.exit(1)
    img = cv2.imread(SRC)
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1) 亮区=面具主体 -> 取最大连通域
    th = (gray > 38).astype(np.uint8) * 255
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    ncc, lab, stats, _ = cv2.connectedComponentsWithStats(th)
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    body = (lab == big).astype(np.uint8) * 255

    # 2) 填内部洞(眼洞/眉毛/胡子并入剪影, 保留原色)
    ff = body.copy()
    cv2.floodFill(ff, np.zeros((H + 2, W + 2), np.uint8), (0, 0), 255)
    holes = cv2.bitwise_not(ff)
    sil = cv2.bitwise_or(body, holes)

    # 3) 上半部最大的两个洞 = 眼睛
    nh, _, hs, hc = cv2.connectedComponentsWithStats(holes)
    cands = [(hs[i, cv2.CC_STAT_AREA], tuple(hc[i])) for i in range(1, nh)
             if hc[i][1] < 0.52 * H and hs[i, cv2.CC_STAT_AREA] > 200]
    cands.sort(reverse=True)
    if len(cands) < 2:
        print("[warn] 没找到两只眼洞，改用经验位置(脸宽34%/66%, 高42%)")
        eyes = [(0.34 * W, 0.42 * H), (0.66 * W, 0.42 * H)]
    else:
        eyes = sorted([c for _, c in cands[:2]], key=lambda p: p[0])

    # 4) alpha: 内缩1px去黑边 + 轻羽化
    alpha = cv2.GaussianBlur(cv2.erode(sil, np.ones((3, 3), np.uint8)), (0, 0), 1.2)
    cv2.imwrite(OUT, np.dstack([img, alpha]))

    ys, xs = np.where(sil > 0)
    cx = float((xs.min() + xs.max()) / 2)
    json.dump(dict(leye=list(map(float, eyes[0])), reye=list(map(float, eyes[1])),
                   top=[cx, float(ys.min())], bottom=[cx, float(ys.max())], W=W, H=H),
              open(ANC, "w"))
    print(f"[ok] 生成 {OUT} 和 {ANC}；眼锚点 "
          f"{tuple(round(v) for v in eyes[0])} {tuple(round(v) for v in eyes[1])}")


if __name__ == "__main__":
    main()
