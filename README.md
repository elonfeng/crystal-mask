# Anonymous 面具 — 实时贴脸

把一张 Anonymous(V字仇杀队) 面具图实时贴到你脸上并跟随头部（刚性，像真戴塑料面具），
可输出到虚拟摄像头，在腾讯会议 / Google Meet / Zoom / 飞书里当摄像头用。

## 一、安装（macOS）

需要 Python 3.9–3.12。

```bash
cd crystal-mask
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

虚拟摄像头依赖 OBS：安装 OBS → 打开一次点「启动虚拟摄像机」再关掉（注册设备）。
首次运行系统会请求摄像头权限，去「系统设置→隐私与安全性→摄像头」给终端授权，然后完全退出终端再重开。

## 二、准备面具素材

仓库未附带面具图（版权）。把你的面具照（正脸、暗背景）命名为 `assets/anon_src.png`，然后：

```bash
python scripts/make_anon_asset.py    # 抠透明背景 + 自动定位眼洞锚点
```

生成 `assets/anon_mask.png` 和 `assets/anon_anchors.json`。

## 三、运行

```bash
python run.py --no-vcam     # 预览：面具贴在你真实画面上
python run.py               # 同时输出虚拟摄像头（需 OBS）
python run.py --void        # 黑底，面具浮在虚空
python run.py --camera 1    # 换摄像头序号
```

- 人脸模型 `face_landmarker.task` 首次运行自动下载（约 4MB）。
- 卡顿就降分辨率：`python run.py --width 800 --height 450`
- 摄像头打不开就先跑 `python scripts/probe_camera.py` 排查权限/序号。
- 按 `q` 退出。

## 四、在会议里用

启动后去会议软件摄像头设置里选 **OBS Virtual Camera** 即可。

## 原理

抠出面具透明剪影 → 检测面具两只眼洞当锚点 → 每帧用你的眼睛位置算相似变换
（缩放+旋转+平移）把面具贴上，跟随头部移动/远近/转动/歪头，并做时域平滑。

```
config.py                       摄像头/模型配置
run.py                          主程序：追踪 + 贴合 + 虚拟摄像头
src/tracker.py                  MediaPipe 人脸追踪
scripts/make_anon_asset.py      面具图抠像 + 眼洞锚点
scripts/probe_camera.py         摄像头排查
```
