# Anonymous 面具 — 实时贴脸（可转头 / 表情跟随）

把一张 Anonymous(V字仇杀队) 面具图实时贴到你脸上，跟随头部转动、张嘴露黑缝，纯黑背景，
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

仓库未附带面具图（版权）。把你的面具照（**正脸、暗背景**）命名为 `assets/anon_src.png`，然后：

```bash
python scripts/make_anon_asset.py
```

会检测面具关键点、用官方人脸网格拓扑、沿轮廓测面具外缘，生成 `assets/anon_rig3d.npz`。

## 三、运行

```bash
python run.py --no-vcam     # 只看预览
python run.py               # 同时输出虚拟摄像头（需 OBS）
python run.py --camera 1    # 换摄像头序号
```

- 人脸模型 `face_landmarker.task` 与人脸网格 `canonical_face_model.obj` 首次运行自动下载。
- 卡顿就降分辨率：`python run.py --width 800 --height 450`
- 摄像头打不开就先跑 `python scripts/probe_camera.py` 排查权限/序号。
- 按 `q` 退出。

## 四、在会议里用

启动后去会议软件摄像头设置里选 **OBS Virtual Camera** 即可。

## 原理

把面具图当**纹理**贴到官方人脸网格(canonical face mesh)上，用你的实时 478 关键点驱动顶点：

- 顶点随你的脸 → 面具贴合你的脸、跟着**转头**（背面剔除让侧脸自然消失，边缘按前缩程度淡出）。
- 沿脸轮廓向外补一圈"裙边"到面具真实边缘 → 完整闭合的面具（额头/两颊/下巴补全）。
- 轮廓内先用面具白色打底 → 网格没盖到的边角显示白色而非黑洞。
- `jawOpen`(张嘴) → 实时嘴部盖黑 = 露黑缝。

```
config.py                       摄像头/模型配置
run.py                          主程序：追踪 + 渲染 + 虚拟摄像头
src/tracker.py                  MediaPipe 人脸追踪
src/maskwarp.py                 面具网格贴图渲染（转头/裙边/白底/张嘴）
scripts/make_anon_asset.py      面具图 -> 网格绑定(关键点/拓扑/轮廓比例)
scripts/probe_camera.py         摄像头排查
```
