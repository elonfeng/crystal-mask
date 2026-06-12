# CrystalMask — 虚空中的晶体面具

纯黑虚空里漂浮一张随你表情实时变形的低多边形**水晶面具**，棱边发光，特定表情触发酷炫特效。
输出到**虚拟摄像头**，可在腾讯会议 / Google Meet / Zoom / 飞书里当摄像头用。

```
摄像头 → MediaPipe 人脸追踪(478点+表情+头姿)
       → Delaunay 三角化成晶面 → 法线着色 + 棱边辉光 + Bloom
       → 表情驱动特效 → 合成 → 虚拟摄像头 + 预览窗
```

## 一、安装（macOS）

需要 Python 3.9–3.12（mediapipe 限制）。

```bash
cd crystal-mask
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

虚拟摄像头依赖 **OBS Studio** 提供后端设备：
1. 安装 OBS（`brew install --cask obs` 或官网下载）。
2. 打开 OBS 一次，点「启动虚拟摄像机」再关掉——让系统注册好虚拟摄像头设备。
3. 首次运行系统会在「系统设置 → 隐私与安全性」请求摄像头/系统扩展权限，放行。

## 二、运行

```bash
python run.py            # 预览窗 + 虚拟摄像头（默认冰晶主题）
python run.py --no-vcam  # 先只看预览（没装 OBS 时用这个验证效果）

# 主题切换
python run.py --theme hacker --no-vcam   # 黑客面具：数字雨+终端绿网格+HEX节点+CRT扫描线
python run.py --theme crystal            # 冰晶面具（默认）
```

### Anonymous(V字仇杀队)面具 — 真实贴图叠加

把一张正脸面具照贴合并跟随你的头（刚性，像真戴塑料面具）：

```bash
# 1) 准备素材：把你的面具照(正脸、暗背景)命名为 assets/anon_src.png
#    （仓库未附第三方面具图，请自备）
python scripts/make_anon_asset.py        # 抠透明背景 + 自动定位眼洞锚点

# 2) 运行
python anon.py --no-vcam                 # 黑底·面具浮在虚空
python anon.py --camera-bg --no-vcam     # 戴在脸上·背景为真实画面
```

原理：抠出面具透明剪影 → 检测面具两只眼洞当锚点 → 每帧用你的眼睛位置算相似变换(缩放+旋转+平移)把面具贴上，跟随头部移动/远近/转动/歪头，并做时域平滑。

- 首次运行自动下载两个模型：`face_landmarker.task`(追踪,约4MB) 和 `canonical_face_model.obj`(网格)。
- 卡顿就降分辨率：`python run.py --width 800 --height 450`
- 操作键：`q` 退出；**`n` 重置表情基线**（保持自然表情时按一下，校准更准）。

## 三、在会议软件里使用

启动 `run.py` 后，去会议软件的摄像头设置里选 **「OBS Virtual Camera」**：
- **Google Meet**（浏览器，最稳）：设置 → 视频 → 摄像头 → 选 OBS Virtual Camera。
- **腾讯会议 / Zoom / 飞书**（桌面端）：设置 → 视频 → 摄像头 里选同一个。
- 个别 macOS 原生 app 对未签名虚拟设备挑剔，认不到就退用浏览器版 Meet。

> 提示：会议软件那头什么都不用改，它只是读「摄像头设备」。所有效果都在本地这条管线里。

## 四、表情 → 特效

| 动作 | 特效 |
|---|---|
| 张嘴 | 嘴部持续喷射能量粒子 |
| 张大保持 ~1 秒后闭嘴 | 蓄力光球 → 能量爆发波束 |
| 挑眉 | 面具外扩一圈光环 |
| 微笑 | 晶体由冰蓝转暖金 + 火花 |
| 双眼眨眼 | 故障特效（色散撕裂 + 扫描线） |
| 嘟嘴 | 嘴部冲击波环 |
| **转成完全侧脸并停留约 0.5 秒** | 晶面炸裂散开成碎晶；转回正脸自动重组 |

> - 面具有**空心眼眶 + 立体五官**（鼻梁/眉骨/下巴），网格交点是发光"星点"。
> - 表情会被**放大**（默认 1.8 倍）：你做的表情更夸张、更有表现力。
> - 炸裂只在**转到侧脸并停住**时发生，正常小幅转头不会炸（避免动不动就裂）。

## 五、调参

全在 `config.py`：
- 颜色：`COOL_LOW/HIGH`、`WARM_*`、`EDGE_COLOR`、`EDGE_CRISP`（BGR）
- 晶体宝石感：`FACET_JITTER`、光照 `LIGHT_DIR`
- 表情夸张程度：`EXPR_GAIN`（调大更夸张）、`EXPR_ADAPT`（调小夸张维持更久）
- 清晰度：`BLOOM_SIGMA` / `BLOOM_STRENGTH` 调小 = 更锐利不糊
- 转头炸裂：`SHATTER_PIXELS`（散开幅度）、`TH_TURN_RATE`（多快算转头）、`SHATTER_RELEASE`（回收速度）
- 触发灵敏度：`TH_*` 阈值、`CHARGE_TIME`、冷却 `CD_*`

## 结构

```
config.py          全局参数
run.py             主循环 / 合成
src/tracker.py     MediaPipe 人脸追踪
src/amplify.py     表情放大（运动放大算法）
src/renderer.py    晶体面渲染（官方网格拓扑+真实3D深度+空心眼眶+发光节点+炸裂）
src/effects.py     粒子/光环/冲击波/碎晶/尘埃/故障
src/triggers.py    表情→事件 状态机
assets/canonical_face_model.obj  官方人脸网格(干净拓扑+真实脸型, 自动下载)
```
