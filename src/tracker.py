# -*- coding: utf-8 -*-
"""人脸追踪：封装 MediaPipe FaceLandmarker，返回 478 个 3D 关键点、52 维表情系数、头姿矩阵。"""
import os
import urllib.request
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

import config


def ensure_model(path, url):
    """模型不存在就自动下载（约 4MB）。"""
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        print(f"[tracker] 正在下载人脸模型 -> {path} ...")
        urllib.request.urlretrieve(url, path)
        print("[tracker] 模型下载完成")


def yaw_from_matrix(mat):
    """从 4x4 头姿矩阵估个偏航角(度)，只用来判断转头方向/速率，不要求绝对精确。"""
    if mat is None:
        return 0.0
    r = mat[:3, :3]
    return float(np.degrees(np.arctan2(r[0, 2], r[2, 2])))


class FaceTracker:
    def __init__(self):
        ensure_model(config.MODEL_PATH, config.MODEL_URL)
        base = python.BaseOptions(model_asset_path=config.MODEL_PATH)
        opts = vision.FaceLandmarkerOptions(
            base_options=base,
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
        )
        self.landmarker = vision.FaceLandmarker.create_from_options(opts)

    def process(self, rgb, ts_ms):
        """输入 RGB 帧与毫秒时间戳。返回 (landmarks Nx3 归一化, blendshapes dict, 4x4矩阵) 或 None。"""
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        res = self.landmarker.detect_for_video(mp_img, ts_ms)
        if not res.face_landmarks:
            return None
        lms = res.face_landmarks[0]
        arr = np.array([[l.x, l.y, l.z] for l in lms], dtype=np.float32)
        bs = {}
        if res.face_blendshapes:
            for c in res.face_blendshapes[0]:
                bs[c.category_name] = c.score
        mat = None
        if res.facial_transformation_matrixes:
            mat = np.array(res.facial_transformation_matrixes[0]).reshape(4, 4)
        return arr, bs, mat
