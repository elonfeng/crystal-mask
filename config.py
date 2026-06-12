# -*- coding: utf-8 -*-
"""全局可调参数 —— 想换风格、调灵敏度，基本都在这里改。颜色一律 BGR（OpenCV 习惯）。"""

# ---------- 画面 ----------
WIDTH = 960            # 输出分辨率宽（卡顿就调到 800/640）
HEIGHT = 540           # 输出分辨率高
CAM_INDEX = 0          # 摄像头序号
FPS = 30

# ---------- 模型 ----------
MODEL_PATH = "assets/face_landmarker.task"
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/"
             "face_landmarker/face_landmarker/float16/1/face_landmarker.task")
# 官方标准人脸网格(干净三角拓扑 + 真实3D脸型), 用于渲染
CANON_OBJ = "assets/canonical_face_model.obj"
CANON_URL = ("https://raw.githubusercontent.com/google-ai-edge/mediapipe/master/"
             "mediapipe/modules/face_geometry/data/canonical_face_model.obj")

# ---------- 晶体外观（侧光雕塑感：一侧亮一侧暗，暗部要够暗才有立体）----------
COOL_LOW = (58, 24, 9)        # 阴影 深蓝（暗部）
COOL_HIGH = (242, 216, 170)   # 高光 冰青
WARM_LOW = (12, 30, 55)       # 暖金（微笑时切换）
WARM_HIGH = (95, 165, 215)
EDGE_COLOR = (255, 226, 175)  # 软棱边（进 bloom 做辉光）
EDGE_CRISP = (220, 238, 255)  # 锐利棱边
NODE_CRISP = (255, 250, 235)  # 节点亮心（"星点"）
NODE_GLOW = (140, 122, 90)    # 节点柔光halo（调暗，避免糊成一片）
FACET_JITTER = 0.07           # 每个晶面随机明暗扰动

# 光照模型：侧上方主光 + 横向键光梯度 + 玻璃高光
LIGHT_DIR = (-0.5, -0.45, 0.72)   # 主光方向(左上偏前)
AMBIENT = 0.07               # 环境光底
K_DIFFUSE = 0.42             # 漫反射(塑形)
K_KEY = 0.42                 # 横向键光梯度(左亮右暗的整体立体感)
K_SPEC = 0.40                # 玻璃高光强度
SPEC_POW = 11                # 高光收敛(越大越尖)

# ---------- 表情放大 / 平滑 ----------
EXPR_GAIN = 1.8      # 表情放大倍数(1=原样, 越大越夸张; 1.5~2.5 推荐)
EXPR_ADAPT = 0.04    # 基线自适应速度(越小, 夸张表情维持越久)
SMOOTH_ALPHA = 0.45  # 关键点时域平滑(越小越丝滑但越跟手延迟, 0.3~0.6)

# ---------- 辉光 / Bloom ----------
BLOOM_SIGMA = 5
BLOOM_STRENGTH = 0.5

# ---------- 触发阈值（0~1，blendshape 分值）----------
TH_JAW_OPEN = 0.30     # 张嘴喷粒子
TH_JAW_CHARGE = 0.48   # 张大蓄力
CHARGE_TIME = 0.85     # 保持多少秒后释放波束
TH_BROW_UP = 0.45      # 挑眉
TH_SMILE = 0.40        # 微笑
TH_BLINK = 0.55        # 眨眼
TH_PUCKER = 0.50       # 嘟嘴
TH_YAW_RATE = 40.0     # 头部偏航速率(度/秒)，超过出残影

# ---------- 转成侧脸并停留 -> 晶面炸裂 ----------
TH_PROFILE = 0.55      # 侧脸判定阈值(0正脸~1完全侧脸); 需转到接近侧脸
PROFILE_DWELL = 0.5    # 侧脸需停留多少秒才触发炸裂
SHATTER_PIXELS = 55    # 炸裂时晶面最大外扩像素
SHATTER_RAMP = 3.5     # 触发后散开速度(渐进, 不是瞬间)
SHATTER_RELEASE = 3.0  # 回正后回收速度
TH_YAW_RATE = 60.0     # 残影用的运动速率参考

# ---------- 冷却(秒) ----------
CD_AURA = 1.0
CD_GLITCH = 0.7
CD_SHOCK = 0.9

GLITCH_FRAMES = 7      # 故障特效持续帧数

# ---------- 主题 ----------
THEME = "crystal"      # crystal(冰晶) / hacker(黑客). 命令行 --theme 覆盖
MATRIX_RAIN = False    # 数字雨背景
SCANLINES = False      # CRT 扫描线 + 色散
CHAR_NODES = False     # 节点显示十六进制字符


def apply_theme(name):
    """切换主题：修改本模块的颜色/光照/开关。renderer 运行时读 config.*，故此处覆盖即生效。"""
    g = globals()
    if name == "hacker":
        g.update(
            COOL_LOW=(6, 26, 5), COOL_HIGH=(45, 200, 40),      # 终端绿(暗->亮)
            WARM_LOW=(25, 25, 70), WARM_HIGH=(70, 95, 255),    # 微笑=红色警报
            EDGE_COLOR=(45, 215, 45), EDGE_CRISP=(95, 255, 105),
            NODE_CRISP=(175, 255, 180), NODE_GLOW=(25, 110, 25),
            AMBIENT=0.11, K_DIFFUSE=0.34, K_KEY=0.30, K_SPEC=0.22, SPEC_POW=8,
            BLOOM_SIGMA=5, BLOOM_STRENGTH=0.55,
            MATRIX_RAIN=True, SCANLINES=True, CHAR_NODES=True, THEME="hacker",
        )
    # crystal 用文件里的默认值，无需改
