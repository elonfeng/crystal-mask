# -*- coding: utf-8 -*-
"""Anonymous(V字仇杀队)面具：把真实面具图贴到你脸上并跟随头部(刚性, 像真戴塑料面具)。

用法:
    python run.py --no-vcam        # 看预览(默认: 面具贴在你真实画面上)
    python run.py                  # 同时输出虚拟摄像头(需 OBS) 给 Zoom/腾讯会议/Meet
    python run.py --void           # 黑底, 面具浮在虚空(不显示真实背景)
    python run.py --camera 1       # 指定摄像头
按 q 退出。
"""
import argparse
import json
import time

import cv2
import numpy as np

import config
from src.tracker import FaceTracker

# 用户眼睛(虹膜中心): MediaPipe 478点里 468=左虹膜 473=右虹膜; 不足则用眼角均值兜底
L_IRIS, R_IRIS = 468, 473
L_EYE_CORNERS, R_EYE_CORNERS = [33, 133], [362, 263]


def open_camera(index, w, h):
    """macOS 强制 AVFoundation 后端, 并逐序号兜底。"""
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


def user_eyes(lms, w, h):
    """返回用户左右眼中心(按屏幕x排序)的像素坐标。"""
    if len(lms) > max(L_IRIS, R_IRIS):
        e1, e2 = lms[L_IRIS, :2], lms[R_IRIS, :2]
    else:
        e1 = lms[L_EYE_CORNERS, :2].mean(0)
        e2 = lms[R_EYE_CORNERS, :2].mean(0)
    pts = np.array([[e1[0] * w, e1[1] * h], [e2[0] * w, e2[1] * h]], np.float32)
    return pts[pts[:, 0].argsort()]


def similarity_from_eyes(mask_l, mask_r, usr_l, usr_r):
    """两对眼睛点 -> 相似变换(缩放+旋转+平移)的 2x3 仿射矩阵。"""
    vm, vu = mask_r - mask_l, usr_r - usr_l
    s = (np.linalg.norm(vu) + 1e-6) / (np.linalg.norm(vm) + 1e-6)
    ang = np.arctan2(vu[1], vu[0]) - np.arctan2(vm[1], vm[0])
    cos, sin = np.cos(ang) * s, np.sin(ang) * s
    t = usr_l - np.array([[cos, -sin], [sin, cos]], np.float32) @ mask_l
    return np.array([[cos, -sin, t[0]], [sin, cos, t[1]]], np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--camera', type=int, default=config.CAM_INDEX)
    ap.add_argument('--width', type=int, default=config.WIDTH)
    ap.add_argument('--height', type=int, default=config.HEIGHT)
    ap.add_argument('--no-vcam', action='store_true')
    ap.add_argument('--void', action='store_true', help='黑底(默认贴在真实画面上)')
    args = ap.parse_args()
    W, H = args.width, args.height

    mask = cv2.imread('assets/anon_mask.png', cv2.IMREAD_UNCHANGED)   # BGRA
    if mask is None or mask.shape[2] != 4:
        print("[err] 缺少 assets/anon_mask.png。先把面具图放到 assets/anon_src.png，"
              "再跑: python scripts/make_anon_asset.py")
        return
    anc = json.load(open('assets/anon_anchors.json'))
    mask_l = np.array(anc['leye'], np.float32)
    mask_r = np.array(anc['reye'], np.float32)

    cap = open_camera(args.camera, W, H)
    if cap is None:
        print("[err] 打不开摄像头。系统设置→隐私与安全性→摄像头 给终端授权后, 完全退出终端再重开。")
        return
    tracker = FaceTracker()
    vcam = None if args.no_vcam else open_vcam(W, H, config.FPS)

    smooth = None
    t0 = time.monotonic()
    last_ts = -1
    print("[run] Anonymous 面具已启动，按 q 退出。" + ("  (黑底)" if args.void else "  (贴真实画面)"))
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

        canvas = np.zeros((H, W, 3), np.uint8) if args.void else frame.copy()
        if res is not None:
            eyes = user_eyes(res[0], W, H)
            smooth = eyes if smooth is None else 0.5 * eyes + 0.5 * smooth
            M = similarity_from_eyes(mask_l, mask_r, smooth[0], smooth[1])
            warped = cv2.warpAffine(mask, M, (W, H), flags=cv2.INTER_LINEAR,
                                    borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
            a = warped[:, :, 3:4].astype(np.float32) / 255.0
            canvas[:] = (warped[:, :, :3].astype(np.float32) * a
                         + canvas.astype(np.float32) * (1 - a)).astype(np.uint8)

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
