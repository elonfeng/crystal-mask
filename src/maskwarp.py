# -*- coding: utf-8 -*-
"""贴合人脸网格(可转头) + 沿整张脸轮廓向外补全面具外沿 -> 完整闭合的面具。

- 顶点 = 你的实时 478 关键点(前468) + 沿脸轮廓向外延伸的"裙边"点(补全白色塑料外沿)。
- 裙边点 = 轮廓点沿"脸心->该点"方向按面具实际边缘比例(ratios)外延 -> 跟随你的脸, 完整闭合。
- 纹理 = 面具图; 逐三角 warp。朝向渐隐(转头边缘柔和淡出)。张嘴(jawOpen)实时嘴部盖黑。
"""
import numpy as np
import cv2

INNER_LIP = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308, 415, 310, 311, 312, 13, 82, 81, 80, 191]
N_FACE = 468


class MaskWarper:
    def __init__(self, tex_path, rig_path):
        self.tex = cv2.imread(tex_path)                          # BGR 纹理
        rig = np.load(rig_path)
        uv = rig['uv'][:N_FACE].astype(np.float32)
        tris = rig['tris'].astype(np.int32)
        self.oval = rig['oval'].astype(np.int32)
        self.ratios = rig['ratios'].astype(np.float32)[:, None]

        cen_uv = uv.mean(0)
        rim_uv = cen_uv + (uv[self.oval] - cen_uv) * self.ratios   # 裙边贴图坐标(面具外缘)
        self.uv = np.vstack([uv, rim_uv]).astype(np.float32)
        n = len(self.oval)
        skirt = []
        for i in range(n):                                        # 绕轮廓一圈连成裙边(闭环)
            a, b = self.oval[i], self.oval[(i + 1) % n]
            ea, eb = N_FACE + i, N_FACE + (i + 1) % n
            skirt += [[a, b, eb], [a, eb, ea]]
        self.tris = np.vstack([tris, np.array(skirt, np.int32)])
        # 每三角在面具图上的原始有向面积(用于按"前缩程度"渐隐, 而非绝对大小)
        ua, ub, uc = self.uv[self.tris[:, 0]], self.uv[self.tris[:, 1]], self.uv[self.tris[:, 2]]
        self.src_area = ((ub[:, 0] - ua[:, 0]) * (uc[:, 1] - ua[:, 1])
                         - (ub[:, 1] - ua[:, 1]) * (uc[:, 0] - ua[:, 0]))

    def render(self, lms, jaw, W, H):
        """lms: 实时 478 关键点(归一化); jaw: jawOpen(0~1)。返回黑底完整面具。"""
        Sf = lms[:N_FACE, :2] * [W, H]
        zf = lms[:N_FACE, 2]
        cen = Sf.mean(0)
        rim = cen + (Sf[self.oval] - cen) * self.ratios          # 裙边实时位置(跟随脸)
        S = np.vstack([Sf, rim])
        z = np.concatenate([zf, zf[self.oval]])

        tri = self.tris
        a, b, c = S[tri[:, 0]], S[tri[:, 1]], S[tri[:, 2]]
        area = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
        ratio = area / (self.src_area + 1e-6)                   # 前缩程度(正对≈s², 转走那侧->0)
        pos = ratio[ratio > 0]
        med = float(np.median(pos)) if pos.size else 1.0
        a_tri = np.clip(ratio / (0.45 * med), 0.0, 1.0)        # 只在真转走那侧淡出, 不动正对的小三角
        meanz = (z[tri[:, 0]] + z[tri[:, 1]] + z[tri[:, 2]]) / 3.0
        order = np.argsort(-meanz)

        out = np.zeros((H, W, 3), np.uint8)
        tex = self.tex
        for k in order:
            av = float(a_tri[k])
            if av <= 0.02:
                continue
            uvt, sct = self.uv[tri[k]], S[tri[k]]
            sx, sy, sw, sh = cv2.boundingRect(uvt)
            dx, dy, dw, dh = cv2.boundingRect(sct.astype(np.float32))
            if min(sw, sh, dw, dh) == 0:
                continue
            x0, y0 = max(0, dx), max(0, dy)
            x1, y1 = min(W, dx + dw), min(H, dy + dh)
            if x1 <= x0 or y1 <= y0:
                continue
            A = cv2.getAffineTransform((uvt - [sx, sy]).astype(np.float32),
                                       (sct - [dx, dy]).astype(np.float32))
            warped = cv2.warpAffine(tex[sy:sy + sh, sx:sx + sw], A, (dw, dh),
                                    flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            tm = np.zeros((dh, dw), np.uint8)
            cv2.fillConvexPoly(tm, (sct - [dx, dy]).astype(np.int32), 255, cv2.LINE_AA)
            tm = tm[y0 - dy:y1 - dy, x0 - dx:x1 - dx] > 0
            roi = out[y0:y1, x0:x1]
            sub = warped[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
            if av >= 0.99:
                roi[tm] = sub[tm]
            else:
                roi[tm] = (sub[tm] * av + roi[tm] * (1.0 - av)).astype(np.uint8)

        if jaw > 0.07:                                          # 轻微张嘴即盖黑
            poly = (lms[INNER_LIP, :2] * [W, H]).astype(np.int32)
            cen2 = poly.mean(0)
            poly = (cen2 + (poly - cen2) * 1.25).astype(np.int32)
            cv2.fillPoly(out, [poly], (0, 0, 0), cv2.LINE_AA)
        return out
