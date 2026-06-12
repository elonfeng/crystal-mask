#!/usr/bin/env bash
# 手动下载 MediaPipe 人脸模型（run.py 首次运行也会自动下载，这个脚本备用）
set -e
cd "$(dirname "$0")/.."
URL="https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
curl -L "$URL" -o assets/face_landmarker.task
echo "已保存到 assets/face_landmarker.task"
