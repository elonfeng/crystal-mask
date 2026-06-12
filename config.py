# -*- coding: utf-8 -*-
"""全局配置。"""

# ---------- 画面 ----------
WIDTH = 960            # 输出分辨率宽（卡顿就调小）
HEIGHT = 540           # 输出分辨率高
CAM_INDEX = 0          # 摄像头序号
FPS = 30

# ---------- 人脸追踪模型（首次运行自动下载，约 4MB）----------
MODEL_PATH = "assets/face_landmarker.task"
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/"
             "face_landmarker/face_landmarker/float16/1/face_landmarker.task")
