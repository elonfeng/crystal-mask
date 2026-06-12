# -*- coding: utf-8 -*-
"""表情/姿态 -> 特效事件状态机：上升沿触发 + 冷却防抖。
炸裂改为"转到侧脸并停留 0.5s"才触发（看绝对侧脸程度 profile，不再看转头速度）。"""
import config


class TriggerEngine:
    def __init__(self):
        self.warm = 0.0
        self.prev_brow = self.prev_blink = self.prev_pucker = False
        self.cd_aura = self.cd_glitch = self.cd_shock = 0.0
        self.charging = False
        self.charge_t = 0.0
        self.shatter = 0.0
        self.profile_t = 0.0          # 侧脸已停留时长
        self.shattered = False        # 是否已进入炸裂态(用于上升沿发碎屑)
        self.prev_profile = 0.0

    def update(self, bs, profile, dt):
        """profile: 侧脸程度 0(正脸)~1(完全侧脸)。返回 (events, info)。"""
        ev = []
        self.cd_aura = max(0.0, self.cd_aura - dt)
        self.cd_glitch = max(0.0, self.cd_glitch - dt)
        self.cd_shock = max(0.0, self.cd_shock - dt)

        jaw = bs.get('jawOpen', 0.0)
        if jaw > config.TH_JAW_CHARGE:
            self.charging = True
            self.charge_t += dt
        elif jaw < config.TH_JAW_OPEN:
            if self.charging and self.charge_t >= config.CHARGE_TIME:
                ev.append('beam')
            self.charging = False
            self.charge_t = 0.0
        if jaw > config.TH_JAW_OPEN:
            ev.append('mouth_energy')

        brow = max(bs.get('browInnerUp', 0.0),
                   bs.get('browOuterUpLeft', 0.0), bs.get('browOuterUpRight', 0.0))
        b = brow > config.TH_BROW_UP
        if b and not self.prev_brow and self.cd_aura <= 0:
            ev.append('aura')
            self.cd_aura = config.CD_AURA
        self.prev_brow = b

        smile = (bs.get('mouthSmileLeft', 0.0) + bs.get('mouthSmileRight', 0.0)) / 2
        self.warm += ((1.0 if smile > config.TH_SMILE else 0.0) - self.warm) * min(1.0, dt * 5)

        blink = min(bs.get('eyeBlinkLeft', 0.0), bs.get('eyeBlinkRight', 0.0)) > config.TH_BLINK
        if blink and not self.prev_blink and self.cd_glitch <= 0:
            ev.append('glitch')
            self.cd_glitch = config.CD_GLITCH
        self.prev_blink = blink

        puck = bs.get('mouthPucker', 0.0) > config.TH_PUCKER
        if puck and not self.prev_pucker and self.cd_shock <= 0:
            ev.append('shockwave')
            self.cd_shock = config.CD_SHOCK
        self.prev_pucker = puck

        # 侧脸停留 -> 炸裂（dwell 计时）
        if profile > config.TH_PROFILE:
            self.profile_t += dt
        else:
            self.profile_t = 0.0
        if self.profile_t >= config.PROFILE_DWELL:
            self.shatter = min(1.0, self.shatter + dt * config.SHATTER_RAMP)
            if not self.shattered:
                ev.append('shatter_start')      # 刚裂开 -> 喷一波碎晶
                self.shattered = True
        else:
            self.shatter = max(0.0, self.shatter - dt * config.SHATTER_RELEASE)
            if self.shatter <= 0.01:
                self.shattered = False

        # 残影：跟随侧脸变化的运动量（自然转头有拖影，但不炸）
        trail = min(1.0, abs(profile - self.prev_profile) / dt / 2.0) if dt > 0 else 0.0
        self.prev_profile = profile

        charge = min(1.0, self.charge_t / config.CHARGE_TIME) if self.charging else 0.0
        info = dict(warm=self.warm, jaw=jaw, charge=charge,
                    trail=trail, shatter=self.shatter)
        return ev, info
