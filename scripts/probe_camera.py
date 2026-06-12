# -*- coding: utf-8 -*-
"""摄像头探测：逐个序号尝试 AVFoundation 后端，触发 macOS 权限弹窗并报告哪个能用。"""
import cv2

print("OpenCV:", cv2.__version__)
found = []
for idx in range(4):
    cap = cv2.VideoCapture(idx, cv2.CAP_AVFOUNDATION)
    opened = cap.isOpened()
    ok = False
    if opened:
        ok, frame = cap.read()
        if ok:
            h, w = frame.shape[:2]
            print(f"  index {idx}: 可用 ✅  分辨率 {w}x{h}")
            found.append(idx)
        else:
            print(f"  index {idx}: 打开了但读不到帧 ❌ (多半是没给终端摄像头权限)")
    else:
        print(f"  index {idx}: 打不开")
    cap.release()

print("-" * 40)
if found:
    print(f"可用摄像头序号: {found}  ->  运行: python run.py --no-vcam --camera {found[0]}")
else:
    print("没有可用摄像头。请到 系统设置→隐私与安全性→摄像头，")
    print("给你的终端App(Terminal/iTerm)打开开关，然后【完全退出终端再重新打开】再试。")
