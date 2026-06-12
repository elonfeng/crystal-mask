# Anonymous 面具摄像头 — 实时贴脸 / 转头 / 表情跟随

把一张 Anonymous（V 字仇杀队 / Guy Fawkes）面具实时贴到你脸上：跟随头部转动、张嘴露黑缝，**纯黑背景**，并输出成一个**虚拟摄像头**——这样腾讯会议 / Google Meet / Zoom / 飞书里直接把它当摄像头选，对面看到的就是面具。

> 平台：macOS（Apple Silicon / Intel）。面具渲染本身跨平台，但摄像头采集与虚拟摄像头流程是按 macOS 写的。

## 效果

- 面具贴合你的脸，**转头**时自然跟随（转走那侧柔和淡出，不是硬切）
- **张嘴**时嘴部实时露出黑缝
- 下巴/山羊须完整闭合，边缘有柔和阴影做出立体感
- 背景纯黑，只有一个面具

---

## 一、安装

需要 Python 3.9–3.12。

```bash
git clone https://github.com/elonfeng/crystal-mask.git
cd crystal-mask
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

人脸模型 `face_landmarker.task` 和人脸网格 `canonical_face_model.obj` 会在**首次运行时自动下载**，无需手动准备。

---

## 二、准备面具素材

仓库**不附带面具图**（版权原因）。自己准备一张面具照：**正脸、面具完整、背景偏暗**（背景越干净，自动抠出的外缘越准）。命名为 `assets/anon_src.png` 放进 `assets/`，然后：

```bash
python scripts/make_anon_asset.py
```

它会在面具图上检测 478 个人脸关键点当贴图坐标、套用官方人脸网格拓扑、沿脸轮廓向外量到面具真实边缘，生成绑定文件 `assets/anon_rig3d.npz`。换面具图就重跑这一步。

---

## 三、配置虚拟摄像头（OBS，只做一次）

虚拟摄像头借助 OBS 的「摄像头系统扩展」实现：**装一次、授权一次**之后，OBS 平时**不用开**，本程序会直接把画面灌进这个虚拟设备。

### 1. 安装 OBS

```bash
brew install --cask obs
```

或从 [obsproject.com](https://obsproject.com) 下载。**务必把 `OBS.app` 放进「/应用程序」**——OBS 只有在 `/应用程序` 里才能安装摄像头扩展。

### 2. 安装并授权摄像头扩展

1. 打开 OBS（首次的权限弹窗一路点「继续」，那些权限我们不需要）
2. 右下角「**控制**」面板 → 点 **「启动虚拟摄像机」**
3. 会提示要安装系统扩展 → 去 **系统设置 → 常规 → 登录项与扩展 → 摄像头扩展（相机扩展）**，把 **OBS** 的开关打开（输开机密码）
4. 回 OBS，重启 OBS 后再点一次「启动虚拟摄像机」，能成功就说明扩展装好了
5. **OBS 现在可以关掉**——扩展会常驻系统，本程序直接用它

验证扩展已激活（可选）：

```bash
systemextensionsctl list | grep mac-camera-extension
# 出现 [activated enabled] 即可
```

### 3. 给终端摄像头权限

第一次跑 `run.py` 时，macOS 会弹窗问「终端想访问摄像头」，点**允许**即可。
若没弹窗或点了没反应：**系统设置 → 隐私与安全性 → 摄像头**，打开你的终端（Terminal / iTerm）开关，然后 ⌘Q **完全退出终端再重开**。

---

## 四、运行

```bash
python run.py               # 输出虚拟摄像头 + 本地预览窗
python run.py --no-vcam     # 只看预览，不输出虚拟摄像头
python run.py --camera 1    # 指定摄像头序号
python run.py --width 800 --height 450   # 降分辨率（卡顿时）
```

启动成功的标志：弹出**面具预览窗** + 终端打印

```
[vcam] 虚拟摄像头就绪: OBS Virtual Camera
```

按 `q` 退出。**开会期间这个程序要一直开着**，关掉对面就黑屏。

---

## 五、在会议软件里选

先确保 `run.py` 正在运行，然后在会议软件的摄像头设置里选 **OBS Virtual Camera**：

- **腾讯会议**：进会议 → 左下「视频」旁的 `^` → 选「OBS Virtual Camera」
- **Google Meet**：会前预览页底部摄像头下拉，或会中「设置 → 视频 → 摄像头」→ 选「OBS Virtual Camera」
- **Zoom / 飞书**：视频设置 → 摄像头 → 选「OBS Virtual Camera」

> **列表里没有「OBS Virtual Camera」？** 多半是会议软件 / 浏览器在装扩展**之前**就开着了，没刷到新设备。**完全退出**该 App（⌘Q，不是关窗口/标签页）再重开就会出现。浏览器版（Meet）尤其要彻底退出 Chrome 再进。

---

## 六、排查

| 现象 | 处理 |
|---|---|
| 摄像头打不开 | 跑 `python scripts/probe_camera.py` 看可用序号；确认终端有摄像头权限并重开终端 |
| `[vcam] 未启用虚拟摄像头` | OBS 扩展没装好：确认 OBS 在 `/应用程序`、扩展已在「登录项与扩展」里打开、重启过 OBS |
| OBS 报「不在应用程序目录」/「虚拟摄像头未安装」 | 把 OBS 拖进 `/应用程序`（用访达拖，别用脚本拷），重启 OBS 再启动虚拟摄像机 |
| 会议里选不到 OBS Virtual Camera | 完全退出会议软件 / 浏览器再重开 |
| 画面卡顿 | 降分辨率：`--width 800 --height 450` |
| 面具没出现/乱跳 | 光线充足、正对摄像头；`make_anon_asset.py` 用的面具图要正脸清晰 |

---

## 原理

把面具图当**纹理**贴到官方人脸网格（canonical face mesh, 898 三角）上，用你的实时 478 关键点驱动顶点，逐三角 `warpAffine`：

- **跟随转头**：顶点跟着你的脸动；按每个三角的前缩程度（面积比）淡出——转走那侧自然消失，正对那侧清晰。
- **裙边补全下巴**：面具的塑料外沿在脸部关键点之外，沿脸轮廓底部中央向外延伸一圈「裙边」补出完整下巴/山羊须。用 smoothstep 平滑过渡（无硬边→不裂不钩），且避开下颌角点（否则转头会戳出白刺）。
- **立体阴影**：按「离面具外轮廓的距离」在下半张脸做羽化压暗，伪造下巴往后收的暗部，避免 2D 贴图的「纸片感」。（降采样计算，约 5ms）
- **张嘴露黑**：`jawOpen` 超过阈值即在嘴部盖一块黑 = 黑缝。

```
config.py                    摄像头/模型路径配置
run.py                       主程序：采集 → 追踪 → 渲染 → 虚拟摄像头
src/tracker.py               MediaPipe 人脸追踪（478 关键点 + blendshapes）
src/maskwarp.py              面具网格贴图渲染（转头淡出 / 下巴裙边 / 立体阴影 / 张嘴盖黑）
scripts/make_anon_asset.py   面具图 → 绑定文件（关键点 / 拓扑 / 轮廓外扩比例）
scripts/probe_camera.py      摄像头序号/权限排查
scripts/download_model.sh    手动下载人脸模型（一般无需，运行时会自动下载）
```

---

## 致谢 / 版权

- 人脸追踪：[MediaPipe Face Landmarker](https://ai.google.dev/edge/mediapipe)（Google，Apache-2.0）
- 虚拟摄像头：[OBS Studio](https://obsproject.com) + [pyvirtualcam](https://github.com/letmaik/pyvirtualcam)
- **面具图版权归原作者所有，本仓库不附带**；请自备素材并遵守其授权。

代码以 MIT 许可证开源。
