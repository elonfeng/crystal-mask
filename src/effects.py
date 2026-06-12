# -*- coding: utf-8 -*-
"""特效层：粒子、光环/冲击波、蓄力光球、虚空尘埃、故障特效。全部画在 glow 发光层上。"""
import numpy as np
import cv2

import config


_RAIN_CHARS = "0123456789ABCDEF<>*/|=+#$%"


class MatrixRain:
    """黑客主题背景：一列列下落的绿色字符(数字雨)。"""
    def __init__(self, w, h):
        self.w, self.h, self.cw = w, h, 16
        self.n = w // self.cw
        self.y = np.random.uniform(-h, 0, self.n).astype(np.float32)
        self.sp = np.random.uniform(140, 340, self.n).astype(np.float32)
        self.trail = 10

    def update_draw(self, canvas, dt):
        self.y += self.sp * dt
        for i in range(self.n):
            if self.y[i] > self.h + self.cw:
                self.y[i] = np.random.uniform(-300, -20)
                self.sp[i] = np.random.uniform(140, 340)
            x = i * self.cw
            hy = int(self.y[i])
            for j in range(self.trail):
                yy = hy - j * self.cw
                if 0 <= yy < self.h:
                    ch = _RAIN_CHARS[np.random.randint(len(_RAIN_CHARS))]
                    if j == 0:
                        col = (190, 255, 190)                     # 头部亮白绿
                    else:
                        gv = int(35 + 150 * (1 - j / self.trail))
                        col = (18, gv, 18)
                    cv2.putText(canvas, ch, (x, yy), cv2.FONT_HERSHEY_PLAIN,
                                1.0, col, 1, cv2.LINE_AA)


def crt_post(img):
    """CRT 质感：1px 色散 + 扫描线压暗。"""
    out = img.copy()
    out[:, :, 2] = np.roll(img[:, :, 2], 1, axis=1)    # R 右移
    out[:, :, 0] = np.roll(img[:, :, 0], -1, axis=1)   # B 左移
    out[::2] = (out[::2] * 0.72).astype(np.uint8)       # 隔行扫描线
    return out


def apply_glitch(img):
    """故障特效：色散(RGB 错位) + 随机水平切片撕裂 + 扫描线压暗。"""
    h, w = img.shape[:2]
    out = img.copy()
    sh = 6
    out[:, :, 2] = np.roll(img[:, :, 2], sh, axis=1)    # R 右移 (BGR 的索引2)
    out[:, :, 0] = np.roll(img[:, :, 0], -sh, axis=1)   # B 左移
    for _ in range(6):
        y = np.random.randint(0, max(1, h - 20))
        hh = np.random.randint(4, 20)
        out[y:y + hh] = np.roll(out[y:y + hh], np.random.randint(-25, 25), axis=1)
    out[::3] = (out[::3] * 0.6).astype(np.uint8)
    return out


class EffectManager:
    # 粒子列: 0x 1y 2vx 3vy 4life 5maxlife 6size 7b 8g 9r
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.P = np.zeros((0, 10), np.float32)
        self.rings = []
        self.glitch_frames = 0
        # 虚空尘埃（常驻、缓慢漂浮）: 0x 1y 2vx 3vy 4bright
        n = 130
        self.amb = np.zeros((n, 5), np.float32)
        self.amb[:, 0] = np.random.uniform(0, w, n)
        self.amb[:, 1] = np.random.uniform(0, h, n)
        self.amb[:, 2] = np.random.uniform(-5, 5, n)
        self.amb[:, 3] = np.random.uniform(-5, 5, n)
        self.amb[:, 4] = np.random.uniform(18, 60, n)

    # ---------- 发射器 ----------
    def _add(self, rows):
        self.P = rows if len(self.P) == 0 else np.vstack([self.P, rows])

    def emit_mouth(self, x, y, jaw):
        """张嘴持续喷射的能量粒子。"""
        n = int(3 + jaw * 9)
        ang = np.random.uniform(0, 2 * np.pi, n)
        sp = np.random.uniform(40, 170, n) * (0.5 + jaw)
        r = np.zeros((n, 10), np.float32)
        r[:, 0] = x + np.random.uniform(-6, 6, n)
        r[:, 1] = y + np.random.uniform(-4, 4, n)
        r[:, 2] = np.cos(ang) * sp
        r[:, 3] = np.sin(ang) * sp - 35           # 略微上扬/外喷
        r[:, 4] = r[:, 5] = np.random.uniform(0.4, 0.9, n)
        r[:, 6] = np.random.uniform(1.5, 3.5, n)
        r[:, 7], r[:, 8], r[:, 9] = 255, 205, 130  # 冰青
        self._add(r)

    def burst_beam(self, x, y):
        """蓄力释放：全向高速粒子爆发 + 一圈强闪光。"""
        n = 80
        ang = np.random.uniform(0, 2 * np.pi, n)
        sp = np.random.uniform(220, 540, n)
        r = np.zeros((n, 10), np.float32)
        r[:, 0], r[:, 1] = x, y
        r[:, 2] = np.cos(ang) * sp
        r[:, 3] = np.sin(ang) * sp
        r[:, 4] = r[:, 5] = np.random.uniform(0.5, 1.1, n)
        r[:, 6] = np.random.uniform(2, 5, n)
        r[:, 7], r[:, 8], r[:, 9] = 255, 238, 195
        self._add(r)
        self.ring(x, y, (255, 238, 195), vr=640, life=0.5, th=3)

    def emit_shards(self, x, y, w, h):
        """侧脸炸裂瞬间：四散的冰晶碎屑（慢速、长寿命，配合面具裂开）。"""
        n = 90
        ang = np.random.uniform(0, 2 * np.pi, n)
        sp = np.random.uniform(60, 320, n)
        r = np.zeros((n, 10), np.float32)
        r[:, 0] = x + np.random.uniform(-0.12, 0.12, n) * w
        r[:, 1] = y + np.random.uniform(-0.16, 0.16, n) * h
        r[:, 2] = np.cos(ang) * sp
        r[:, 3] = np.sin(ang) * sp
        r[:, 4] = r[:, 5] = np.random.uniform(0.6, 1.4, n)
        r[:, 6] = np.random.uniform(1.5, 4.0, n)
        r[:, 7], r[:, 8], r[:, 9] = 255, 235, 195
        self._add(r)

    def emit_turn(self, x, y, dirx, h):
        """转头方向流光：沿转头方向(dirx=±1)横向喷出一道高速冰晶粒子。"""
        n = 40
        base = 0.0 if dirx >= 0 else np.pi
        ang = base + np.random.uniform(-0.45, 0.45, n)
        sp = np.random.uniform(220, 560, n)
        r = np.zeros((n, 10), np.float32)
        r[:, 0] = x + np.random.uniform(-20, 20, n)
        r[:, 1] = y + np.random.uniform(-0.35, 0.35, n) * h   # 沿脸纵向铺开
        r[:, 2] = np.cos(ang) * sp
        r[:, 3] = np.sin(ang) * sp * 0.5
        r[:, 4] = r[:, 5] = np.random.uniform(0.35, 0.8, n)
        r[:, 6] = np.random.uniform(1.5, 4.0, n)
        r[:, 7], r[:, 8], r[:, 9] = 255, 228, 175
        self._add(r)

    def ring(self, x, y, col, vr, life, th=2):
        self.rings.append(dict(x=x, y=y, r=6.0, vr=vr, life=life, maxlife=life, col=col, th=th))

    def trigger_glitch(self):
        self.glitch_frames = config.GLITCH_FRAMES

    # ---------- 更新 / 绘制 ----------
    def update(self, dt):
        if len(self.P):
            self.P[:, 0] += self.P[:, 2] * dt
            self.P[:, 1] += self.P[:, 3] * dt
            self.P[:, 2:4] *= (1.0 - 1.2 * dt)        # 阻力，无重力 -> 太空漂浮感
            self.P[:, 4] -= dt
            self.P = self.P[self.P[:, 4] > 0]
        for rg in self.rings:
            rg['r'] += rg['vr'] * dt
            rg['life'] -= dt
        self.rings = [r for r in self.rings if r['life'] > 0]

    def draw(self, glow):
        for p in self.P:
            a = p[4] / max(p[5], 1e-3)
            cv2.circle(glow, (int(p[0]), int(p[1])), int(p[6]),
                       (int(p[7] * a), int(p[8] * a), int(p[9] * a)), -1, cv2.LINE_AA)
        for rg in self.rings:
            a = rg['life'] / rg['maxlife']
            col = tuple(int(c * a) for c in rg['col'])
            cv2.circle(glow, (int(rg['x']), int(rg['y'])), int(rg['r']), col, rg['th'], cv2.LINE_AA)

    def draw_charge(self, glow, x, y, c):
        """蓄力中：嘴前的光球随蓄力比例 c 膨胀。"""
        r = int(6 + c * 42)
        col = (int(255 * c), int(238 * c), int(195 * c))
        cv2.circle(glow, (int(x), int(y)), r, col, 2, cv2.LINE_AA)
        cv2.circle(glow, (int(x), int(y)), max(1, int(r * 0.4)), col, -1, cv2.LINE_AA)

    def update_ambient(self, canvas, dt):
        self.amb[:, 0] = (self.amb[:, 0] + self.amb[:, 2] * dt) % self.w
        self.amb[:, 1] = (self.amb[:, 1] + self.amb[:, 3] * dt) % self.h
        for p in self.amb:
            b = int(p[4])
            cv2.circle(canvas, (int(p[0]), int(p[1])), 1,
                       (b, int(b * 0.8), int(b * 0.5)), -1)
