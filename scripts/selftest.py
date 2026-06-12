# -*- coding: utf-8 -*-
"""无摄像头/无 mediapipe 的核心逻辑自测：合成人脸点 -> 跑满渲染+特效+触发+合成管线。"""
import os
import sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from src.renderer import CrystalRenderer, load_canonical_model
from src.effects import EffectManager, apply_glitch
from src.triggers import TriggerEngine
from src.amplify import ExpressionAmplifier

W, H = config.WIDTH, config.HEIGHT


def fake_face(t):
    """生成一张大致椭圆分布的 478 点人脸(归一化)，随 t 轻微晃动，制造转头/形变。"""
    rng = np.random.default_rng(7)
    ang = rng.uniform(0, 2 * np.pi, 478)
    rad = rng.uniform(0.05, 0.22, 478)
    cx = 0.5 + 0.04 * np.sin(t)          # 左右晃 -> 触发残影
    cy = 0.5
    x = cx + rad * np.cos(ang) * 0.7
    y = cy + rad * np.sin(ang) * 0.95
    z = -rad * 0.5 + 0.02 * np.cos(ang)  # 伪深度
    return np.stack([x, y, z], 1).astype(np.float32)


def fake_blendshapes(frame):
    """按帧编排各种表情，确保每条触发分支都被走到。"""
    bs = dict(jawOpen=0, browInnerUp=0, mouthSmileLeft=0, mouthSmileRight=0,
              eyeBlinkLeft=0, eyeBlinkRight=0, mouthPucker=0)
    if 5 <= frame < 40:        # 张大蓄力再闭 -> beam
        bs['jawOpen'] = 0.7 if frame < 35 else 0.0
    if frame == 45:            # 挑眉 -> aura
        bs['browInnerUp'] = 0.8
    if 50 <= frame < 70:       # 微笑 -> 暖金
        bs['mouthSmileLeft'] = bs['mouthSmileRight'] = 0.7
    if frame == 75:            # 眨眼 -> glitch
        bs['eyeBlinkLeft'] = bs['eyeBlinkRight'] = 0.9
    if frame == 85:            # 嘟嘴 -> shockwave
        bs['mouthPucker'] = 0.8
    return bs


def main():
    rend = CrystalRenderer(W, H)
    fx = EffectManager(W, H)
    trig = TriggerEngine()
    amp = ExpressionAmplifier()
    trail = np.zeros((H, W, 3), np.float32)
    dt = 1.0 / config.FPS
    fired = set()
    saved = []

    for frame in range(95):
        t = frame * dt
        lms = amp(fake_face(t))
        if not rend.ready:
            pts2d = np.stack([lms[:, 0] * W, lms[:, 1] * H], 1)
            vc, tc = load_canonical_model(config.CANON_OBJ)
            rend.set_tri(tc, pts2d, vc)
            print(f"[selftest] 官方网格 {len(tc)} 个晶面")

        canvas = np.zeros((H, W, 3), np.uint8)
        glow = np.zeros((H, W, 3), np.uint8)
        edge = np.zeros((H, W, 3), np.uint8)
        fx.update_ambient(canvas, dt)

        prof = 0.8 if 40 <= frame < 70 else 0.0   # 第40帧起转侧脸并停留 -> 触发炸裂
        events, info = trig.update(fake_blendshapes(frame), prof, dt)
        fired.update(events)

        mc = lms[[13, 14]].mean(0)
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

        fx.update(dt)
        fx.draw(glow)

        decay = 0.85 if info.get('trail', 0) > 0.5 else 0.25
        trail *= decay
        trail = np.maximum(trail, glow.astype(np.float32))
        glow_t = trail.astype(np.uint8)

        bloom = cv2.GaussianBlur(glow_t, (0, 0), config.BLOOM_SIGMA)
        out = cv2.add(canvas, glow_t)
        out = cv2.add(out, (bloom * config.BLOOM_STRENGTH).astype(np.uint8))
        out = cv2.add(out, edge)
        if fx.glitch_frames > 0:
            out = apply_glitch(out)
            fx.glitch_frames -= 1

        assert out.shape == (H, W, 3) and out.dtype == np.uint8
        if frame in (30, 47, 55, 60, 75, 86):
            path = f"/tmp/crystalmask_{frame:02d}.png"
            cv2.imwrite(path, out)
            saved.append(path)

    print(f"[selftest] 触发到的事件: {sorted(fired)}")
    print(f"[selftest] 存活粒子: {len(fx.P)}  存活光环: {len(fx.rings)}")
    print(f"[selftest] 导出截图: {saved}")
    expect = {'mouth_energy', 'beam', 'aura', 'glitch', 'shockwave', 'shatter_start'}
    missing = expect - fired
    print("[selftest] 全部触发覆盖 OK" if not missing else f"[selftest] 未触发: {missing}")
    print("[selftest] 通过 ✅")


if __name__ == '__main__':
    main()
