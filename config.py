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
# 官方人脸网格拓扑(干净三角), 用于把面具贴成可转头的网格
CANON_OBJ = "assets/canonical_face_model.obj"
CANON_URL = ("https://raw.githubusercontent.com/google-ai-edge/mediapipe/master/"
             "mediapipe/modules/face_geometry/data/canonical_face_model.obj")
