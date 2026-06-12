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
        ratios = rig['ratios'].astype(np.float32)
        # 裙边在"下半张脸"(下巴/下颌弧)平滑外扩, 向两边/上方 smoothstep 渐变到不外扩
        # -> 没有硬边(不裂/不缺), 不到下颌角/额头(不钩、无halo); 较宽 -> 下巴圆润不尖
        ox, oy = uv[self.oval][:, 0], uv[self.oval][:, 1]
        cx = float(uv[:, 0].mean())
        fw = float(uv[:, 0].max() - uv[:, 0].min())
        ytop, ybot = float(uv[:, 1].min()), float(uv[:, 1].max())
        yfac = np.clip((oy - (ytop + 0.48 * (ybot - ytop))) / (0.30 * (ybot - ytop)), 0.0, 1.0)
        xfac = np.clip(1.0 - np.abs(ox - cx) / (0.32 * fw), 0.0, 1.0)   # 不含下颌角点(转头戳刺)
        ss = lambda t: t * t * (3.0 - 2.0 * t)                  # smoothstep, 顶部平缓 -> 圆
        wch = ss(yfac) * ss(xfac)                               # 下方中央=1, 向外平滑->0
        ratios = 1.0 + (ratios - 1.0) * wch * 0.88
        self.ratios = ratios[:, None]

        cen_uv = uv.mean(0)
        rim_uv = cen_uv + (uv[self.oval] - cen_uv) * self.ratios
        self.uv = np.vstack([uv, rim_uv]).astype(np.float32)
        n = len(self.oval)
        skirt = []
        for i in range(n):
            a, b = self.oval[i], self.oval[(i + 1) % n]
            ea, eb = N_FACE + i, N_FACE + (i + 1) % n
            skirt += [[a, b, eb], [a, eb, ea]]
        self.n_face_tris = len(tris)                            # 之后的都是裙边三角
        self.tris = np.vstack([tris, np.array(skirt, np.int32)])
        ua, ub, uc = self.uv[self.tris[:, 0]], self.uv[self.tris[:, 1]], self.uv[self.tris[:, 2]]
        self.src_area = ((ub[:, 0] - ua[:, 0]) * (uc[:, 1] - ua[:, 1])
                         - (ub[:, 1] - ua[:, 1]) * (uc[:, 0] - ua[:, 0]))

    def render(self, lms, jaw, W, H):
        """lms: 实时 478 关键点(归一化); jaw: jawOpen(0~1)。返回黑底完整面具。"""
        Sf = lms[:N_FACE, :2] * [W, H]
        zf = lms[:N_FACE, 2]
        cen = Sf.mean(0)
        rim = cen + (Sf[self.oval] - cen) * self.ratios          # 裙边(仅底部外扩)
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

        out = self._rim_shadow(out)                            # 下巴/下颌边缘柔和压暗 -> 立体感

        if jaw > 0.035:                                        # 微张即盖黑(阈值放低), 范围放大盖住白唇
            poly = (lms[INNER_LIP, :2] * [W, H]).astype(np.float32)
            cen2 = poly.mean(0)
            poly = (cen2 + (poly - cen2) * 1.32).astype(np.int32)
            cv2.fillPoly(out, [poly], (0, 0, 0), cv2.LINE_AA)
        return out

    @staticmethod
    def _rim_shadow(img, strength=0.45, sc=3):
        """按"离面具外轮廓的距离"在下半张脸做羽化压暗, 伪造下巴往后收的阴影(立体感)。
        只取最外轮廓填充 -> 内部黑块(眼/须)不算边缘, 不冒黑晕。
        阴影是低频的, 在 1/sc 降采样上算再放大 -> 几乎无损但快 ~10x。"""
        H, W = img.shape[:2]
        h, w = H // sc, W // sc
        small = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
        silh = (small.max(2) > 12).astype(np.uint8)
        cnts, _ = cv2.findContours(silh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return img
        filled = np.zeros((h, w), np.uint8)
        cv2.drawContours(filled, cnts, -1, 1, -1)
        ys = np.where(filled.any(1))[0]
        if ys.size == 0:
            return img
        y0, y1 = int(ys[0]), int(ys[-1])
        mh = max(1, y1 - y0)
        feather = float(np.clip(0.09 * mh, 4, 30))
        dist = cv2.distanceTransform(filled, cv2.DIST_L2, 3)
        prox = np.clip(1.0 - dist / feather, 0, 1)
        prox = cv2.GaussianBlur(prox, (0, 0), feather * 0.25)
        lo = y0 + 0.46 * mh                                    # 阴影只作用在下半脸
        yv = np.clip((np.arange(h) - lo) / (0.14 * mh), 0, 1)[:, None]
        fac = cv2.resize((1.0 - strength * prox * yv).astype(np.float32),
                         (W, H), interpolation=cv2.INTER_LINEAR)[:, :, None]
        return (img.astype(np.float32) * fac).clip(0, 255).astype(np.uint8)
