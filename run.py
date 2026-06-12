# -*- coding: utf-8 -*-
"""CrystalMask 主程序：摄像头 -> 晶体面具 + 表情特效 -> 预览窗 + 虚拟摄像头。

用法:
    python run.py                 # 预览 + 虚拟摄像头(若可用)
    python run.py --no-vcam       # 只看预览窗，不输出虚拟摄像头
    python run.py --camera 1      # 指定摄像头
    python run.py --width 800 --height 450   # 卡顿时降分辨率
按 q 退出。
"""
import argparse
import time

import cv2
import numpy as np

import config
from src.tracker import FaceTracker, ensure_model
from src.renderer import CrystalRenderer, load_canonical_model
from src.effects import EffectManager, apply_glitch, MatrixRain, crt_post
from src.triggers import TriggerEngine
from src.amplify import ExpressionAmplifier

MOUTH_IDX = [13, 14]   # 上下唇中点 -> 嘴部锚点
NOSE_TIP, FACE_L, FACE_R = 1, 234, 454   # 鼻尖 / 左脸缘 / 右脸缘 -> 侧脸程度


def profile_amount(lms):
    """侧脸程度 0(正脸)~1(完全侧脸)：鼻尖在左右脸缘之间的偏移比。"""
    lx, rx, nx = lms[FACE_L, 0], lms[FACE_R, 0], lms[NOSE_TIP, 0]
    dl, dr = nx - lx, rx - nx
    return float(min(1.0, abs(dr - dl) / (dl + dr + 1e-6)))


def open_camera(index, w, h):
    """macOS 上强制走原生 AVFoundation 后端（默认 FFMPEG 后端常打不开摄像头）。
    依次尝试: 指定后端+指定序号 -> 默认后端 -> 序号 0/1/2 兜底。"""
    attempts = [(index, cv2.CAP_AVFOUNDATION), (index, cv2.CAP_ANY)]
    for i in (0, 1, 2):
        if i != index:
            attempts.append((i, cv2.CAP_AVFOUNDATION))
    for idx, backend in attempts:
        cap = cv2.VideoCapture(idx, backend)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        if cap.isOpened():
            ok, _ = cap.read()                 # 真正读一帧才算成功（权限不足时 isOpened 也可能为真）
            if ok:
                bname = "AVFoundation" if backend == cv2.CAP_AVFOUNDATION else "default"
                print(f"[cam] 摄像头已打开: index={idx}, backend={bname}")
                return cap
        cap.release()
    return None


def open_vcam(w, h, fps):
    try:
        import pyvirtualcam
        cam = pyvirtualcam.Camera(width=w, height=h, fps=fps)
        print(f"[vcam] 虚拟摄像头已就绪: {cam.device}")
        print("[vcam] 在腾讯会议/Google Meet 的摄像头里选它即可")
        return cam
    except Exception as e:
        print(f"[vcam] 未启用虚拟摄像头({e}). 仅预览; 装好 OBS 后即可输出。")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--camera', type=int, default=config.CAM_INDEX)
    ap.add_argument('--width', type=int, default=config.WIDTH)
    ap.add_argument('--height', type=int, default=config.HEIGHT)
    ap.add_argument('--no-vcam', action='store_true')
    ap.add_argument('--theme', default=config.THEME, choices=['crystal', 'hacker'],
                    help='crystal=冰晶面具 / hacker=黑客数字雨面具')
    args = ap.parse_args()
    W, H = args.width, args.height
    config.apply_theme(args.theme)              # 必须在建 renderer/effects 之前

    cap = open_camera(args.camera, W, H)
    if cap is None:
        print("[err] 打不开摄像头。排查：")
        print("  1) 系统设置→隐私与安全性→摄像头，给你的终端(Terminal/iTerm)打开开关，然后【完全退出终端再重开】")
        print("  2) 关掉占用摄像头的程序(Zoom/腾讯会议/Photo Booth/浏览器标签)")
        print("  3) 外接摄像头试试别的序号: --camera 1 / --camera 2")
        return

    tracker = FaceTracker()
    ensure_model(config.CANON_OBJ, config.CANON_URL)        # 官方人脸网格(自动下载)
    canon_verts, canon_tris = load_canonical_model(config.CANON_OBJ)
    rend = CrystalRenderer(W, H)
    fx = EffectManager(W, H)
    trig = TriggerEngine()
    amp = ExpressionAmplifier()
    rain = MatrixRain(W, H) if config.MATRIX_RAIN else None
    vcam = None if args.no_vcam else open_vcam(W, H, config.FPS)

    trail = np.zeros((H, W, 3), np.float32)   # 残影累积缓冲
    prev_lms = None                            # 时域平滑用
    t0 = time.monotonic()
    last_ts = -1

    print("=" * 56)
    print(f"  CrystalMask v2  |  主题: {config.THEME}  |  {len(canon_tris)} 三角面")
    if config.THEME == "hacker":
        print("  数字雨 + 终端绿网格 + HEX节点 + CRT扫描线")
    else:
        print(f"  表情放大 x{config.EXPR_GAIN}  |  空心眼眶  |  侧脸停留炸裂")
    print("=" * 56)
    print("[run] 启动完成，按 q 退出 / n 重置表情基线")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)                      # 镜像，更自然
        frame = cv2.resize(frame, (W, H))
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        ts = int((time.monotonic() - t0) * 1000)
        if ts <= last_ts:
            ts = last_ts + 1
        last_ts = ts
        res = tracker.process(rgb, ts)

        canvas = np.zeros((H, W, 3), np.uint8)
        glow = np.zeros((H, W, 3), np.uint8)
        edge = np.zeros((H, W, 3), np.uint8)            # 锐利棱边（bloom 后叠加）
        if rain is not None:
            rain.update_draw(canvas, 1.0 / config.FPS)  # 黑客主题：数字雨背景
        else:
            fx.update_ambient(canvas, 1.0 / config.FPS) # 虚空尘埃打底

        info = {}
        if res is not None:
            lms, bs, mat = res
            lms = amp(lms)                              # 表情放大（更夸张的表现力）
            if prev_lms is not None:                    # 时域平滑 -> 丝滑不抖
                lms = config.SMOOTH_ALPHA * lms + (1 - config.SMOOTH_ALPHA) * prev_lms
            prev_lms = lms
            if not rend.ready:
                pts2d = np.stack([lms[:, 0] * W, lms[:, 1] * H], 1)
                rend.set_tri(canon_tris, pts2d, canon_verts)

            dt = 1.0 / config.FPS
            events, info = trig.update(bs, profile_amount(lms), dt)

            mc = lms[MOUTH_IDX].mean(0)
            mx, my = mc[0] * W, mc[1] * H
            fc = lms.mean(0)
            fxc, fyc = fc[0] * W, fc[1] * H

            for ev in events:
                if ev == 'mouth_energy':
                    fx.emit_mouth(mx, my, info['jaw'])
                elif ev == 'beam':
                    fx.burst_beam(mx, my)
                elif ev == 'aura':
                    fx.ring(fxc, fyc, (255, 200, 120), vr=270, life=0.9, th=2)
                elif ev == 'glitch':
                    fx.trigger_glitch()
                elif ev == 'shockwave':
                    fx.ring(mx, my, (255, 245, 230), vr=480, life=0.6, th=3)
                elif ev == 'shatter_start':
                    fx.emit_shards(fxc, fyc, W, H)

            rend.draw(canvas, glow, edge, lms, info.get('warm', 0.0),
                      info.get('shatter', 0.0), info.get('jaw', 0.0))
            if info.get('charge', 0) > 0.05:
                fx.draw_charge(glow, mx, my, info['charge'])

        fx.update(1.0 / config.FPS)
        fx.draw(glow)

        # 残影：转头越快保留越久 -> 晶体拖出流光
        decay = 0.0 if res is None else (0.85 if info.get('trail', 0) > 0.5 else 0.25)
        trail *= decay
        trail = np.maximum(trail, glow.astype(np.float32))
        glow_t = trail.astype(np.uint8)

        # 合成：实心晶面 + 粒子/残影(原样) + 软辉光 Bloom + 锐利棱边(最上层, 保清晰)
        bloom = cv2.GaussianBlur(glow_t, (0, 0), config.BLOOM_SIGMA)
        out = cv2.add(canvas, glow_t)                   # 粒子/光环 原样, 保持明亮
        out = cv2.add(out, (bloom * config.BLOOM_STRENGTH).astype(np.uint8))
        out = cv2.add(out, edge)                        # 锐利棱边压在最上层

        if fx.glitch_frames > 0:
            out = apply_glitch(out)
            fx.glitch_frames -= 1
        if config.SCANLINES:
            out = crt_post(out)                          # 黑客主题：CRT 扫描线+色散

        cv2.imshow(f'CrystalMask v2 [{config.THEME}]  (q quit / n recenter)', out)
        if vcam is not None:
            vcam.send(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
            vcam.sleep_until_next_frame()
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        if key == ord('n'):                             # 保持自然表情时按 n 重新校准基线
            amp.reset()
            print("[run] 表情基线已重置")

    cap.release()
    cv2.destroyAllWindows()
    if vcam is not None:
        vcam.close()


if __name__ == '__main__':
    main()
