# -*- coding: utf-8 -*-
"""Anonymous 面具：屏幕上一个面具(纯黑背景), 表情跟随你本人(你张嘴它张嘴)。

用法:
    python run.py --no-vcam        # 看预览
    python run.py                  # 同时输出虚拟摄像头(需 OBS) 给 Zoom/腾讯会议/Meet
    python run.py --camera 1       # 指定摄像头
按 q 退出。
"""
import argparse
import os
import time

import cv2
import numpy as np

import config
from src.tracker import FaceTracker
from src.maskwarp import MaskWarper


def open_camera(index, w, h):
    attempts = [(index, cv2.CAP_AVFOUNDATION), (index, cv2.CAP_ANY)]
    for i in (0, 1, 2):
        if i != index:
            attempts.append((i, cv2.CAP_AVFOUNDATION))
    for idx, backend in attempts:
        cap = cv2.VideoCapture(idx, backend)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        if cap.isOpened():
            ok, _ = cap.read()
            if ok:
                print(f"[cam] 摄像头已打开: index={idx}")
                return cap
        cap.release()
    return None


def open_vcam(w, h, fps):
    try:
        import pyvirtualcam
        cam = pyvirtualcam.Camera(width=w, height=h, fps=fps)
        print(f"[vcam] 虚拟摄像头就绪: {cam.device}  (会议里选它)")
        return cam
    except Exception as e:
        print(f"[vcam] 未启用虚拟摄像头({e}). 仅预览。装好 OBS 后即可输出。")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--camera', type=int, default=config.CAM_INDEX)
    ap.add_argument('--width', type=int, default=config.WIDTH)
    ap.add_argument('--height', type=int, default=config.HEIGHT)
    ap.add_argument('--no-vcam', action='store_true')
    args = ap.parse_args()
    W, H = args.width, args.height

    if not (os.path.exists('assets/anon_src.png') and os.path.exists('assets/anon_rig3d.npz')):
        print("[err] 缺少面具素材。先把面具图放到 assets/anon_src.png，再跑:")
        print("       python scripts/make_anon_asset.py")
        return
    warper = MaskWarper('assets/anon_src.png', 'assets/anon_rig3d.npz')

    cap = open_camera(args.camera, W, H)
    if cap is None:
        print("[err] 打不开摄像头。系统设置→隐私与安全性→摄像头 给终端授权后, 完全退出终端再重开。")
        return
    tracker = FaceTracker()
    vcam = None if args.no_vcam else open_vcam(W, H, config.FPS)

    smooth = None
    jaw_s = 0.0
    t0 = time.monotonic()
    last_ts = -1
    print("[run] Anonymous 面具已启动（纯黑底·跟随头部·张嘴露黑缝），按 q 退出。")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (W, H))
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        ts = int((time.monotonic() - t0) * 1000)
        if ts <= last_ts:
            ts = last_ts + 1
        last_ts = ts
        res = tracker.process(rgb, ts)

        if res is not None:
            lms = res[0]                                    # (478,3) 归一化
            smooth = lms if smooth is None else 0.5 * lms + 0.5 * smooth
            jaw = res[1].get('jawOpen', 0.0) if res[1] else 0.0
            jaw_s = 0.4 * jaw + 0.6 * jaw_s                 # 张嘴平滑
            canvas = warper.render(smooth, jaw_s, W, H)
        else:
            canvas = np.zeros((H, W, 3), np.uint8)

        cv2.imshow('Anonymous mask  (q quit)', canvas)
        if vcam is not None:
            vcam.send(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
            vcam.sleep_until_next_frame()
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    if vcam is not None:
        vcam.close()


if __name__ == '__main__':
    main()
