# -*- coding: utf-8 -*-
"""表情放大：把你相对"基线脸"的形变放大，跟随你的表情但表现力更夸张。

原理(运动放大 motion magnification)：
  维护一条缓慢自适应的基线脸 B(慢速 EMA)；当前帧 C 相对 B 的形变 delta=C-B
  里，整体平移(刚性头动)保留原样，剩下的局部形变(=表情)按 gain 放大。
  这样头怎么动都稳，只有表情被放大；夸张表情能维持一两秒。
"""
import numpy as np

import config


class ExpressionAmplifier:
    def __init__(self, gain=None, adapt=None):
        self.gain = config.EXPR_GAIN if gain is None else gain
        self.adapt = config.EXPR_ADAPT if adapt is None else adapt
        self.base = None

    def reset(self):
        self.base = None

    def __call__(self, lms):
        """lms: (N,3) 归一化关键点。返回放大后的 (N,3)。"""
        if self.gain <= 1.001:
            return lms
        if self.base is None or self.base.shape != lms.shape:
            self.base = lms.copy()
            return lms
        # 慢速基线自适应
        self.base += self.adapt * (lms - self.base)
        delta = lms - self.base
        glob = delta.mean(axis=0)          # 刚性平移(头动) -> 保留
        local = delta - glob               # 非刚性形变(表情) -> 放大
        # 限幅：单点放大形变不超过脸宽的 25%，防止抽搐/炸裂
        face_w = np.ptp(self.base[:, 0]) + 1e-6
        local = np.clip(local, -0.25 * face_w, 0.25 * face_w)
        return self.base + glob + self.gain * local
