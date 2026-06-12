# -*- coding: utf-8 -*-
"""Anonymous(V字仇杀队)面具：把真实面具图按你的眼睛位置贴合并跟随头部(刚性, 像戴真面具)。

用法:
    python anon.py --no-vcam          # 只看预览(黑底, 面具浮在虚空)
    python anon.py                    # 同时输出虚拟摄像头(需 OBS)
    python anon.py --camera-bg        # 背景显示真实摄像头画面(像真戴上)
    python anon.py --camera 1         # 指定摄像头
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
        print(f"[vcam] 虚拟摄像头就绪: {cam.device} (会议里选它)")
        return cam
    except Exception as e:
        print(f"[vcam] 未启用虚拟摄像头({e}). 仅预览。")
        return None


def user_eyes(lms, w, h):
    """返回用户左右眼中心(按屏幕x排序)的像素坐标。"""
    if len(lms) > max(L_IRIS, R_IRIS):
        e1 = lms[L_IRIS, :2]
        e2 = lms[R_IRIS, :2]
    else:
        e1 = lms[L_EYE_CORNERS, :2].mean(0)
        e2 = lms[R_EYE_CORNERS, :2].mean(0)
    pts = np.array([[e1[0] * w, e1[1] * h], [e2[0] * w, e2[1] * h]], np.float32)
    return pts[pts[:, 0].argsort()]            # 左(x小) -> 右


def similarity_from_eyes(mask_l, mask_r, usr_l, usr_r):
    """由两对眼睛点求相似变换(缩放+旋转+平移)的 2x3 仿射矩阵。"""
    vm = mask_r - mask_l
    vu = usr_r - usr_l
    s = (np.linalg.norm(vu) + 1e-6) / (np.linalg.norm(vm) + 1e-6)
    ang = np.arctan2(vu[1], vu[0]) - np.arctan2(vm[1], vm[0])
    cos, sin = np.cos(ang) * s, np.sin(ang) * s
    R = np.array([[cos, -sin], [sin, cos]], np.float32)
    t = usr_l - R @ mask_l
    return np.array([[cos, -sin, t[0]], [sin, cos, t[1]]], np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--camera', type=int, default=config.CAM_INDEX)
    ap.add_argument('--width', type=int, default=config.WIDTH)
    ap.add_argument('--height', type=int, default=config.HEIGHT)
    ap.add_argument('--no-vcam', action='store_true')
    ap.add_argument('--camera-bg', action='store_true', help='背景用真实摄像头(默认黑底)')
    args = ap.parse_args()
    W, H = args.width, args.height

    mask = cv2.imread('assets/anon_mask.png', cv2.IMREAD_UNCHANGED)   # BGRA
    if mask is None or mask.shape[2] != 4:
        print("[err] 缺少 assets/anon_mask.png，先跑抠图预处理")
        return
    anc = json.load(open('assets/anon_anchors.json'))
    mask_l = np.array(anc['leye'], np.float32)
    mask_r = np.array(anc['reye'], np.float32)

    cap = open_camera(args.camera, W, H)
    if cap is None:
        print("[err] 打不开摄像头(权限/序号)。系统设置→隐私→摄像头给终端授权后重开终端。")
        return
    tracker = FaceTracker()
    vcam = None if args.no_vcam else open_vcam(W, H, config.FPS)

    smooth = None                                # 眼睛平滑
    t0 = time.monotonic()
    last_ts = -1
    print("[anon] Anonymous 面具启动，按 q 退出。")
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

        canvas = frame.copy() if args.camera_bg else np.zeros((H, W, 3), np.uint8)
        if res is not None:
            lms = res[0]
            eyes = user_eyes(lms, W, H)
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
