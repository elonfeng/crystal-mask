# -*- coding: utf-8 -*-
"""晶体面具渲染：用 MediaPipe 官方人脸网格拓扑(干净均匀) + 真实3D深度做立体明暗，
空心眼眶/张嘴口腔，发光节点(星点)，棱边辉光，侧脸炸裂。"""
import numpy as np
import cv2

import config

# 官方网格的眼/唇轮廓顶点索引（用于挖空眼眶、张嘴时挖空口腔）
LEFT_EYE = [33, 246, 161, 160, 159, 158, 157, 173, 133, 155, 154, 153, 145, 144, 163, 7]
RIGHT_EYE = [263, 466, 388, 387, 386, 385, 384, 398, 362, 382, 381, 380, 374, 373, 390, 249]
INNER_LIP = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308, 415, 310, 311, 312, 13, 82, 81, 80, 191]
OUTER_LIP = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 40, 39, 185]


def load_canonical_model(path):
    """读取 canonical_face_model.obj -> (verts(468,3) 真实3D脸型, tris(898,3) 干净三角拓扑)。"""
    verts, tris = [], []
    with open(path) as f:
        for line in f:
            if line.startswith('v '):
                p = line.split()
                verts.append((float(p[1]), float(p[2]), float(p[3])))
            elif line.startswith('f '):
                idx = [int(tok.split('/')[0]) - 1 for tok in line.split()[1:4]]
                tris.append(idx)
    return np.array(verts, np.float32), np.array(tris, np.int32)


def _lerp(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def _inside(poly, pt):
    return cv2.pointPolygonTest(poly, (float(pt[0]), float(pt[1])), False) >= 0


class CrystalRenderer:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.light = np.array(config.LIGHT_DIR, np.float32)
        self.light /= np.linalg.norm(self.light)
        self.tri = None

    def set_tri(self, tris, pts2d, canon_verts):
        """tris: 官方三角拓扑; pts2d: 首帧2D点(预判眼/嘴/节点); canon_verts: 真实3D脸型。"""
        self.tri = tris
        self.canon_z = canon_verts[:, 2].copy()
        self.canon_w = float(np.ptp(canon_verts[:, 0])) + 1e-6
        seq = np.arange(len(tris)) * 12.9898
        rng = np.abs(np.sin(seq) * 43758.5453)
        self.jitter = ((rng - np.floor(rng)) - 0.5) * 2 * config.FACET_JITTER
        self.sfac = (self.jitter / config.FACET_JITTER) * 0.5 + 1.0 if config.FACET_JITTER > 0 \
            else np.ones(len(tris), np.float32)

        P = np.asarray(pts2d, np.float32)
        cen = P[tris].mean(axis=1)
        le, re = P[LEFT_EYE].astype(np.int32), P[RIGHT_EYE].astype(np.int32)
        self.eye_mask = np.array([_inside(le, c) or _inside(re, c) for c in cen], dtype=bool)
        ol = P[OUTER_LIP]
        mc, mr = ol.mean(0), np.linalg.norm(ol - ol.mean(0), axis=1).max() * 1.4
        self.mouth_cand = np.where(np.linalg.norm(cen - mc, axis=1) < mr)[0]
        used = np.unique(tris)
        keep = [i for i in used if not (_inside(le, P[i]) or _inside(re, P[i]))]
        self.node_idx = np.array(keep, np.int32)
        # 黑客主题：给部分节点固定一个十六进制字符
        if getattr(config, 'CHAR_NODES', False):
            hx = "0123456789ABCDEF"
            r = np.abs(np.sin(self.node_idx * 7.13) * 9301.0)
            self.node_chars = [hx[int((v - np.floor(v)) * 16) & 15] for v in r]
        else:
            self.node_chars = None

    @property
    def ready(self):
        return self.tri is not None

    def draw(self, canvas, glow, edge, lms3d, warm=0.0, shatter=0.0, jaw=0.0):
        w, h = self.w, self.h
        n = len(self.canon_z)
        lx = lms3d[:n, 0] * w
        ly = lms3d[:n, 1] * h
        # 2D 位置跟随实时脸；深度 z 用官方真实脸型(按当前脸宽缩放) -> 稳定的立体感
        scale = (lx.max() - lx.min() + 1e-6) / self.canon_w
        lz = (self.canon_z - self.canon_z.mean()) * scale
        V = np.stack([lx, ly, lz], 1)
        p2 = np.stack([lx, ly], 1).astype(np.int32)
        tri = self.tri
        a, b, c = V[tri[:, 0]], V[tri[:, 1]], V[tri[:, 2]]

        nrm = np.cross(b - a, c - a)
        nrm /= (np.linalg.norm(nrm, axis=1)[:, None] + 1e-6)
        if nrm[:, 2].mean() < 0:                 # 法线统一朝向相机
            nrm = -nrm
        diffuse = np.clip(nrm @ self.light, 0.0, 1.0)        # 漫反射塑形
        spec = diffuse ** config.SPEC_POW                    # 玻璃高光
        meanz = (a[:, 2] + b[:, 2] + c[:, 2]) / 3.0
        # 横向键光：脸左侧亮、右侧暗 -> 整体侧光立体感
        cx = (a[:, 0] + b[:, 0] + c[:, 0]) / 3.0
        key = 1.0 - (cx - lx.min()) / (lx.max() - lx.min() + 1e-6)
        shade = np.clip(config.AMBIENT + config.K_DIFFUSE * diffuse
                        + config.K_KEY * key + self.jitter, 0.03, 1.0)

        skip = self.eye_mask.copy()
        if jaw > 0.16 and len(self.mouth_cand):
            mpoly = p2[INNER_LIP]
            cc = (a[:, :2] + b[:, :2] + c[:, :2]) / 3.0
            for k in self.mouth_cand:
                if _inside(mpoly, cc[k]):
                    skip[k] = True

        offs = None
        if shatter > 0.01:
            centers = (a[:, :2] + b[:, :2] + c[:, :2]) / 3.0
            d = centers - p2.mean(0)
            d /= (np.linalg.norm(d, axis=1, keepdims=True) + 1e-6)
            offs = (d * (shatter * config.SHATTER_PIXELS * self.sfac)[:, None]).astype(np.int32)

        order = np.argsort(-meanz)
        polys = []
        for k in order:
            if skip[k]:
                continue
            poly = p2[tri[k]] if offs is None else p2[tri[k]] + offs[k]
            s = float(shade[k])
            col = _lerp(config.COOL_LOW, config.COOL_HIGH, s)
            if warm > 0.01:
                col = _lerp(col, _lerp(config.WARM_LOW, config.WARM_HIGH, s), warm)
            sp = float(spec[k]) * config.K_SPEC               # 玻璃高光 -> 提白
            if sp > 0.01:
                col = _lerp(col, (255, 255, 255), min(1.0, sp))
            cv2.fillConvexPoly(canvas, poly, col, lineType=cv2.LINE_AA)
            polys.append(poly)

        soft = tuple(int(v * 0.62) for v in _lerp(config.EDGE_COLOR, (255, 255, 255), warm * 0.5))
        crisp = _lerp(config.EDGE_CRISP, (255, 255, 255), warm * 0.3)
        cv2.polylines(glow, polys, True, soft, 1, cv2.LINE_AA)
        cv2.polylines(edge, polys, True, crisp, 1, cv2.LINE_AA)

        node_a = max(0.0, 1.0 - shatter * 1.3)
        if node_a > 0.05:
            nc = tuple(int(v * node_a) for v in config.NODE_CRISP)
            ng = tuple(int(v * node_a) for v in config.NODE_GLOW)
            for j, i in enumerate(self.node_idx):
                x, y = int(p2[i, 0]), int(p2[i, 1])
                if self.node_chars is not None and j % 3 == 0:
                    cv2.putText(edge, self.node_chars[j], (x - 3, y + 3),
                                cv2.FONT_HERSHEY_PLAIN, 0.7, nc, 1, cv2.LINE_AA)
                    cv2.circle(glow, (x, y), 2, ng, -1, cv2.LINE_AA)
                else:
                    cv2.circle(glow, (x, y), 2, ng, -1, cv2.LINE_AA)
                    cv2.circle(edge, (x, y), 1, nc, -1, cv2.LINE_AA)
